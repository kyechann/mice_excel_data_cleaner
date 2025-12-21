# sections/email_sender.py
import streamlit as st
import pandas as pd
import io

from modules import cleaner, mailer


def _is_valid_email(x) -> bool:
    s = "" if x is None else str(x).strip()
    return ("@" in s) and ("." in s.split("@")[-1])


def _df_to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "selected") -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
        df.to_excel(w, sheet_name=sheet_name[:31], index=False)
    return buf.getvalue()


def render_email_sender(view_df: pd.DataFrame, base_df: pd.DataFrame, key_prefix: str = "MAIL"):
    """
    좌: 템플릿 작성 + '템플릿 적용(표에 추가)'
    우: SMTP/계정/첨부/테스트/전체발송
    아래: 발송 대상 표(체크 가능) + 선택 발송/선택 다운로드
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
        # RIGHT: SMTP & 계정 & 발송
        # -------------------------
        with right:
            st.markdown("#### SMTP 서버")
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
                type=None,
                accept_multiple_files=True,
                key=f"{kp}_attachments",
            )

            attachments_payload = []
            if uploaded_attachments:
                for f in uploaded_attachments:
                    attachments_payload.append((f.name, f.getvalue(), f.type))
                st.caption(f"첨부 {len(attachments_payload)}개 준비됨")

            st.markdown("---")
            st.markdown("#### ✅ 테스트 발송 (최대 5명)")
            test_receivers_text = st.text_area(
                "테스트 받는 사람 이메일들 (줄바꿈/쉼표로 여러 개 가능)",
                key=f"{kp}_TEST_RECEIVERS",
                placeholder="a@example.com\nb@example.com\nc@example.com",
                height=90,
            )

            st.caption(
                f"DEBUG: sender_email={'OK' if (sender_email or '').strip() else 'EMPTY'} / "
                f"pw_len={len(sender_pw or '')} / "
                f"msg_col={'YES' if '생성된_메시지' in send_df.columns else 'NO'}"
            )

            if "생성된_메시지" not in send_df.columns:
                st.info("먼저 좌측에서 **[템플릿 적용 (표에 추가)]** 를 눌러 메시지를 생성해주세요.")
            else:
                if st.button("테스트 발송 (최대 5명)", key=f"{kp}_TEST_SEND", use_container_width=True):
                    if not (sender_email or "").strip() or not (sender_pw or "").strip():
                        st.warning("보내는 계정 정보를 입력하세요.")
                    else:
                        raw = (test_receivers_text or "").replace(",", "\n")
                        receivers = [x.strip() for x in raw.splitlines() if x.strip()]
                        receivers = receivers[:5]

                        if not receivers:
                            st.warning("테스트 받는 사람 이메일을 1개 이상 입력하세요.")
                        else:
                            base_row = send_df.head(1).copy().reset_index(drop=True)
                            test_df = pd.concat([base_row] * len(receivers), ignore_index=True)
                            test_df[target_email_col] = receivers

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

        # -------------------------
        # 하단: 체크 가능한 표 + 선택 발송/다운로드
        # -------------------------
        st.markdown("---")
        st.markdown("#### 📋 발송 대상 데이터 (체크해서 선택 발송 가능)")

        preview = send_df.copy()
        if "선택" not in preview.columns:
            preview.insert(0, "선택", False)

        edited_df = st.data_editor(
            preview,
            use_container_width=True,
            hide_index=True,
            height=420,
            key=f"{kp}_EDITOR",
            column_config={"선택": st.column_config.CheckboxColumn("선택", required=True)},
        )

        # ✅ 선택 인원 표시
        selected_raw = edited_df[edited_df["선택"] == True].copy()
        selected_count = int(len(selected_raw))
        st.caption(f"✅ 현재 선택됨: **{selected_count}명** (선택 발송은 최대 5명)")

        # 선택된 DF(발송/다운로드용)
        selected_df = selected_raw.drop(columns=["선택"], errors="ignore").reset_index(drop=True)

        btn1, btn2, btn3 = st.columns([1.2, 1.2, 2], gap="small")

        # ✅ 선택된 사람만 엑셀 다운로드
        with btn1:
            if selected_df.empty:
                st.download_button(
                    "⬇️ 선택 엑셀 다운로드",
                    data=b"",
                    file_name="selected.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    disabled=True,
                    use_container_width=True,
                    key=f"{kp}_DL_SELECTED_DISABLED",
                )
            else:
                xlsx_bytes = _df_to_xlsx_bytes(selected_df, sheet_name="selected")
                st.download_button(
                    "⬇️ 선택 엑셀 다운로드",
                    data=xlsx_bytes,
                    file_name="selected.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key=f"{kp}_DL_SELECTED",
                )

        # ✅ 선택 발송 (이메일 검증 + 제외 로그)
        with btn2:
            send_selected = st.button(
                "✉️ 선택 발송 (최대 5명)",
                type="secondary",
                use_container_width=True,
                key=f"{kp}_SEND_SELECTED",
            )

        with btn3:
            st.caption("선택 발송은 아래 규칙으로 안전하게 처리됩니다.")
            st.write("- 선택 0명: 발송 안 함\n- 6명 이상 선택: 제한 경고\n- 이메일 비어있음/형식 이상: 자동 제외 + 로그")

        if send_selected:
            # 기본 검증
            if "생성된_메시지" not in send_df.columns:
                st.error("먼저 **[템플릿 적용]** 으로 '생성된_메시지'를 만든 뒤 사용하세요.")
            elif not (st.session_state.get("SMTP_SENDER_EMAIL") or "").strip() or not (st.session_state.get("SMTP_SENDER_PW") or "").strip():
                st.error("오른쪽에서 이메일 계정 정보를 입력해주세요.")
            elif selected_df.empty:
                st.warning("선택된 행이 없습니다. 위 표에서 체크하세요.")
            elif len(selected_df) > 5:
                st.warning("선택 발송은 최대 5명까지 가능합니다. 5명 이하로 선택해 주세요.")
            else:
                # 이메일 유효성 검사
                invalid_rows = []
                valid_rows = []
                for idx, r in selected_df.iterrows():
                    em = r.get(target_email_col, None)
                    if _is_valid_email(em):
                        valid_rows.append(r)
                    else:
                        name_hint = ""
                        for cand in ["이름", "성명", "name", "Name"]:
                            if cand in selected_df.columns:
                                name_hint = str(r.get(cand, "")).strip()
                                break
                        invalid_rows.append(f"- row#{idx+1} / {name_hint} / email='{em}'")

                if not valid_rows:
                    st.error("선택된 행들의 이메일이 전부 비어있거나 형식이 올바르지 않습니다.")
                    with st.expander("제외된 대상(이메일 이상)"):
                        st.write("\n".join(invalid_rows) if invalid_rows else "없음")
                else:
                    run_df = pd.DataFrame(valid_rows).reset_index(drop=True)

                    suc, s_cnt, f_cnt, logs = mailer.send_bulk_emails(
                        run_df,
                        st.session_state.get("SMTP_SENDER_EMAIL"),
                        st.session_state.get("SMTP_SENDER_PW"),
                        target_email_col,
                        mail_subject,
                        "생성된_메시지",
                        smtp_host,
                        int(smtp_port),
                        attachments=attachments_payload,
                    )

                    if suc:
                        st.success(f"선택 발송 완료! (성공: {s_cnt}, 실패: {f_cnt})")
                    else:
                        st.error(f"선택 발송 실패: {logs[0] if logs else 'Unknown'}")

                    # ✅ 제외/실패 로그 모아보기
                    if invalid_rows or logs:
                        with st.expander("선택 발송 로그(제외/실패)"):
                            if invalid_rows:
                                st.markdown("**[제외됨: 이메일 형식 이상]**")
                                st.write("\n".join(invalid_rows))
                            if logs:
                                st.markdown("**[발송 실패 로그]**")
                                st.write("\n".join(logs[:200]))