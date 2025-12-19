import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.mime.base import MIMEBase
from email import encoders
import mimetypes
import time
import streamlit as st
import pandas as pd
import unicodedata

def force_clean_input(text):
    if not text:
        return ""
    text = str(text)
    text = unicodedata.normalize('NFKC', text)
    text = text.replace('\xa0', '')
    return text.strip()

def _attach_files(msg: MIMEMultipart, attachments):
    """
    attachments: List[Dict] or List[Tuple]
      - dict: {"filename": str, "data": bytes, "mime": "type/subtype"(optional)}
      - tuple: (filename, data, mime_optional)
    """
    if not attachments:
        return

    for item in attachments:
        if isinstance(item, dict):
            filename = item.get("filename", "attachment")
            data = item.get("data", b"")
            mime = item.get("mime")
        else:
            filename = item[0]
            data = item[1]
            mime = item[2] if len(item) > 2 else None

        if not data:
            continue

        if not mime:
            mime, _ = mimetypes.guess_type(filename)
        if not mime:
            mime = "application/octet-stream"

        maintype, subtype = mime.split("/", 1)

        part = MIMEBase(maintype, subtype)
        part.set_payload(data)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)

def send_bulk_emails(
    df,
    sender_email,
    sender_pw,
    email_col,
    subject,
    body_col,
    smtp_server,
    smtp_port,
    attachments=None,          # ✅ 추가
):
    success_count = 0
    fail_count = 0
    error_log = []

    total_emails = len(df)
    progress_bar = st.progress(0) if total_emails > 1 else None
    status_text = st.empty()

    clean_sender_email = force_clean_input(sender_email)
    clean_sender_pw = force_clean_input(sender_pw)
    clean_subject = force_clean_input(subject)

    try:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(clean_sender_email, clean_sender_pw)

        for i, (_, row) in enumerate(df.iterrows()):
            recipient = force_clean_input(row.get(email_col, ""))

            if not recipient or "@" not in recipient:
                fail_count += 1
                continue

            try:
                # ✅ mixed 로 만들어야 첨부 안정적
                msg = MIMEMultipart("mixed")
                msg["Subject"] = Header(clean_subject, "utf-8")
                msg["From"] = clean_sender_email
                msg["To"] = recipient

                raw_body = row.get(body_col, "")
                clean_body = unicodedata.normalize("NFKC", str(raw_body))

                # 본문 파트
                text_part = MIMEText(clean_body, "plain", "utf-8")
                msg.attach(text_part)

                # ✅ 첨부 추가
                _attach_files(msg, attachments)

                server.send_message(msg)
                success_count += 1

            except Exception as e:
                fail_count += 1
                error_log.append(f"{recipient}: {str(e)}")

            if progress_bar:
                progress_bar.progress(min((i + 1) / total_emails, 1.0))
            status_text.text(f"발송 중... ({i + 1}/{total_emails})")
            time.sleep(0.2)

        server.quit()
        status_text.text("발송 작업이 종료되었습니다.")
        return True, success_count, fail_count, error_log

    except Exception as e:
        return False, 0, 0, [f"SMTP 오류: {str(e)}"]