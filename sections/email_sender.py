# sections/email_sender.py
import re
import streamlit as st
import pandas as pd

from modules import cleaner, mailer


def _parse_test_receivers(raw: str, limit: int = 5) -> list[str]:
    """
    콤마/줄바꿈/세미콜론/공백으로 구분된 이메일 목록 파싱
    - 최대 limit개
    - 중복 제거(순서 유지)
    """
    if not raw:
        return []
    parts = re.split(r"[\n,; ]+", raw.strip())
    seen = set()
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if "@" not in p:
            continue
        if p.lower() in seen:
            continue
        seen.add(p.lower())
        out.append(p)
        if len(out) >= limit:
            break
    return out


def _make_test_df(send_df: pd.DataFrame, email_col: str, receivers: list[str]) -> pd.DataFrame:
    """
    receivers 수만큼 DF를 만들고, email_col에 receivers를 주입.
    - send_df 행이 부족하면 첫 행을 복제해서 채움
    """
    n = len(receivers)
    if n <= 0:
        return send_df.head(0).copy()

    if len(send_df) >= n:
        df = send_df.head(n).copy().reset_index(drop=True)
    else:
        # 부족하면 1행을 복제해서 채움
        base = send_df.head(1).copy()
        if base.empty:
            # 데이터가 아예 없을 때는 빈 DF 반환
            return send_df.head(0).copy()
        df = pd.concat([base] * n, ignore_index=True)

    df[email_col] = receivers
    return df


def render_email_sender(view_df: pd.DataFrame, base_df: pd.DataFrame, key_prefix: str = "MAIL"):
    """
    좌: 템플릿 작성 + '템플릿 적용(표에 추가)'
    우: SMTP/계정/첨부/테스트(최대 5명)/전체발송
    아래: 발송 대상 표 미리보기
    """
    kp = key_prefix or "MAIL"

    with st.expander("📧 메일/문자 템플릿 & 발송", expanded=False):
        st.info(f"사용 가능 변수: {', '.join([f'{{{c}}}' for c in base_df.columns])}")

        default_msg = """[MICE 2025 컨퍼런스] 사전등록 확정 안내

안녕하세요, {이름}님.
신청해주신 내용으로 등록이 정상적으로 완료되었습니다.

▶ 소속: {소속}
▶ 연락처: {전화번호}

행사 당일, 등록데스크에서 본 메시지를 보여주시면 명찰을 수령하실 수 있습니다.
감사합니다."""

        # 템플릿은 시트별로 보관
        tmpl_key = f"{kp}_TEMPLATE"
        if tmpl_key not in st.session_state:
            st.session_state[tmpl_key] = default_msg

        left, right = st.columns([1.25, 1], gap="large")

        # -------------------------
        # LEFT: 템플릿 작성
        # -------------------------
        with left:
            st.markdown("#### 🧾 템플릿 내용")
            tmpl = st.text_area(
                "템플릿 내용",
                value=st.session_state[tmpl_key],
                height=240,
                label_visibility="collapsed",
                key=f"{kp}_TEMPLATE_TEXTAREA",
            )
            st.session_state[tmpl_key] = tmpl

            if st.button("템플릿 적용 (표에 추가)", key=f"{kp}_APPLY_TEMPLATE", use_container_width=True):
                try:
                    view_df2 = cleaner.generate_message_column(view_df, tmpl)
                    st.session_state["mail_df"] = view_df2
                    st.success("생성 완료! (아래 표/발송에 반영됨)")
                    st.rerun()
                except Exception as e:
                    st.error(f"생성 실패: {e}")

        # 발송/미리보기 대상 DF
        send_df = st.session_state.get("mail_df")
        if send_df is None:
            send_df = view_df

        # -------------------------
        # RIGHT: SMTP & 계정 & 첨부 & 발송
        # -------------------------
        with right:
            st.markdown("#### SMTP 서버")
            # SMTP/계정은 "고정 key" (시트 바뀌어도 유지)
            smtp_host = st.text_input("SMTP 서버", value="smtp.gmail.com", key="SMTP_HOST")
            smtp_port = st.number_input("포트", value=465, step=1, key="SMTP_PORT")

            st.markdown("---")
            st.markdown("#### 📨 계정 설정")
            st.caption("💡 Gmail은 **앱 비밀번호(16자리)** 를 사용해야 합니다.")

            sender_email = st.text_input("보내는 메일 주소", key="SMTP_SENDER_EMAIL", placeholder="myname@gmail.com")
            sender_pw = st.text_input("앱 비밀번호(16자리)", type="password", key="SMTP_SENDER_PW")
            mail_subject = st.text_input("메일 제목", value="[MICE 2025] 등록 안내", key=f"{kp}_MAIL_SUBJECT")

            # 이메일 컬럼 선택
            mail_cols = [c for c in send_df.columns if ("이메일" in str(c)) or ("email" in str(c).lower())]
            if not mail_cols:
                st.warning("⚠️ 이메일 컬럼을 찾지 못했습니다. (컬럼명에 '이메일' 또는 'email' 포함 필요)")
                return

            default_idx = list(send_df.columns).index(mail_cols[0])
            target_email_col = st.selectbox(
                "받는 사람 이메일 컬럼",
                options=list(send_df.columns),
                index=default_idx,
                key=f"{kp}_EMAIL_COL",
            )

            st.markdown("---")
            st.markdown("#### 📎 첨부파일")
            uploaded_attachments = st.file_uploader(
                "첨부파일 업로드 (여러 개 가능)",
                accept_multiple_files=True,
                key=f"{kp}_ATTACHMENTS",
            )

            # mailer.py가 (filename, bytes, mime) 튜플도 받도록 되어 있으니 그대로 전달
            attachments_payload = []
            if uploaded_attachments:
                for f in uploaded_attachments:
                    attachments_payload.append((f.name, f.getvalue(), f.type))
                st.caption(f"첨부 {len(attachments_payload)}개 준비됨")

            st.markdown("---")
            st.markdown("#### ✅ 테스트 발송 (최대 5명)")
            st.caption("콤마(,), 줄바꿈, 세미콜론(;)으로 여러 명 입력 가능 / 최대 5명까지만 발송")

            test_receivers_raw = st.text_area(
                "테스트 받는 사람 이메일들",
                key=f"{kp}_TEST_RECEIVERS",
                placeholder="me1@example.com, me2@example.com\nme3@example.com",
                height=80,
                label_visibility="collapsed",
            )
            test_receivers = _parse_test_receivers(test_receivers_raw, limit=5)

            # 디버그(원인 바로 보이게)
            st.caption(
                f"DEBUG: sender_email={'OK' if (sender_email or '').strip() else 'EMPTY'} / "
                f"pw_len={len(sender_pw or '')} / "
                f"msg_col={'YES' if '생성된_메시지' in send_df.columns else 'NO'} / "
                f"test_receivers={len(test_receivers)} / "
                f"attachments={len(attachments_payload)}"
            )

            if "생성된_메시지" not in send_df.columns:
                st.info("먼저 좌측에서 **[템플릿 적용 (표에 추가)]** 를 눌러 메시지를 생성해주세요.")
            else:
                if st.button("테스트 발송 (최대 5명)", key=f"{kp}_TEST_SEND", use_container_width=True):
                    if not (sender_email or "").strip() or not (sender_pw or "").strip():
                        st.warning("보내는 계정 정보를 입력하세요.")
                    elif not test_receivers:
                        st.warning("테스트 받는 사람 이메일을 1명 이상 입력하세요. (최대 5명)")
                    else:
                        test_df = _make_test_df(send_df, target_email_col, test_receivers)

                        suc, s_cnt, f_cnt, logs = mailer.send_bulk_emails(
                            test_df,
                            sender_email,
                            sender_pw,
                            target_email_col,
                            mail_subject,
                            "생성된_메시지",
                            smtp_host,
                            int(smtp_port),
                            attachments=attachments_payload,
                        )
                        if suc:
                            st.success(f"테스트 발송 완료! (성공: {s_cnt}, 실패: {f_cnt})")
                            if logs:
                                with st.expander("실패 로그 보기"):
                                    st.write("\n".join(logs[:200]))
                        else:
                            st.error(f"실패: {logs[0] if logs else 'Unknown'}")

                st.markdown("---")
                st.markdown("#### 🚀 전체 발송")
                st.caption(f"현재 발송 대상: **{len(send_df):,}명** (필터 적용 기준)")

                if st.button("전체 발송 시작 (주의)", type="primary", key=f"{kp}_SEND_ALL", use_container_width=True):
                    if not (sender_email or "").strip() or not (sender_pw or "").strip():
                        st.error("이메일 계정 정보를 입력해주세요.")
                    else:
                        run_df = send_df.reset_index(drop=True)
                        suc, s_cnt, f_cnt, logs = mailer.send_bulk_emails(
                            run_df,
                            sender_email,
                            sender_pw,
                            target_email_col,
                            mail_subject,
                            "생성된_메시지",
                            smtp_host,
                            int(smtp_port),
                            attachments=attachments_payload,
                        )
                        if suc:
                            st.success(f"발송 완료! (성공: {s_cnt}, 실패: {f_cnt})")
                            if logs:
                                with st.expander("실패 로그 보기"):
                                    st.write("\n".join(logs[:200]))
                        else:
                            st.error(f"발송 실패: {logs[0] if logs else 'Unknown'}")

        st.markdown("---")
        st.markdown("#### 📋 발송 대상 데이터 (미리보기)")
        st.dataframe(send_df, use_container_width=True, hide_index=True, height=420)