import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import time
import streamlit as st
import pandas as pd
import unicodedata

def force_clean_input(text):
    """
    [긴급 패치] 사용자 입력값(이메일, 비번 등)에 섞인 유령 문자(\xa0) 박멸
    """
    if not text:
        return ""
    
    text = str(text)
    
    # 1. 유니코드 정규화 (이상한 문자를 표준으로)
    text = unicodedata.normalize('NFKC', text)
    
    # 2. 문제의 원인 \xa0 (Non-breaking space) 제거
    text = text.replace('\xa0', '')
    
    # 3. 앞뒤 일반 공백 제거
    return text.strip()

def send_bulk_emails(df, sender_email, sender_pw, email_col, subject, body_col, smtp_server, smtp_port):
    success_count = 0
    fail_count = 0
    error_log = []

    total_emails = len(df)
    if total_emails > 1:
        progress_bar = st.progress(0)
    status_text = st.empty()
    
    # [핵심 수정] 로그인 전에 계정 정보부터 강제 세탁
    # (여기서 \xa0가 섞여 있으면 server.login에서 바로 터집니다)
    clean_sender_email = force_clean_input(sender_email)
    clean_sender_pw = force_clean_input(sender_pw) # 비밀번호에도 공백이 묻어올 수 있음
    clean_subject = force_clean_input(subject)

    try:
        # SMTP 서버 연결
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        
        # 세탁된 정보로 로그인 시도
        server.login(clean_sender_email, clean_sender_pw)
        
        for i, (index, row) in enumerate(df.iterrows()):
            raw_recipient = row[email_col]
            raw_body = row[body_col]
            
            # [핵심 수정] 받는 사람 이메일도 강제 세탁
            recipient = force_clean_input(raw_recipient)
            
            # 이메일 유효성 체크
            if not recipient or "@" not in recipient:
                fail_count += 1
                continue

            try:
                msg = MIMEMultipart()
                
                # 헤더 설정 (UTF-8 명시)
                msg['Subject'] = Header(clean_subject, 'utf-8')
                msg['From'] = clean_sender_email
                msg['To'] = recipient 
                
                # 본문 설정 (UTF-8 명시)
                # 본문에도 혹시 모를 특수문자가 있을 수 있으니 정규화 한번 수행
                clean_body = unicodedata.normalize('NFKC', str(raw_body))
                msg.attach(MIMEText(clean_body, 'plain', 'utf-8')) 

                server.send_message(msg)
                success_count += 1
                
            except Exception as e:
                fail_count += 1
                error_log.append(f"{recipient}: {str(e)}")
            
            # 진행률 업데이트
            if total_emails > 1:
                progress = min((i + 1) / total_emails, 1.0)
                progress_bar.progress(progress)
            
            status_text.text(f"발송 중... ({i + 1}/{total_emails})")
            time.sleep(0.5)

        server.quit()
        status_text.text("발송 작업이 종료되었습니다.")
        return True, success_count, fail_count, error_log

    except Exception as e:
        # 로그인 실패 등 치명적 오류
        return False, 0, 0, [f"SMTP 오류: {str(e)}"]