import streamlit as st
import pandas as pd
import io
import time
import os

from modules import cleaner, database, reporter
from core.db_schema import build_db_payload, DB_SCHEMA_COLS
from core.pdf_assets import pdf_assets_reset

from sections.satisfaction import render_satisfaction_and_review
from sections.registration import render_registration_charts
from sections.insights import render_insights_dashboard
from sections.email_sender import render_email_sender

def render_dashboard():
    # ----------------------------
    # 분석 전 상태
    # ----------------------------
    if st.session_state.get("analyzed_data") is None:
        uploaded_file = st.file_uploader(
            "분석할 엑셀 파일을 드래그하거나 선택하세요",
            type=["xlsx"]
        )
        if uploaded_file:
            with st.spinner("⚡ AI 엔진 구동 중..."):
                try:
                    s = time.time()
                    buf, clean, trash, msg = cleaner.run_cleaning_pipeline(uploaded_file)
                    e = time.time()

                    if msg == "Success":
                        st.session_state["analyzed_data"] = {
                            "excel_buffer": buf,
                            "cleaned_data": clean,
                            "trash_data": trash,
                            "filename": uploaded_file.name,
                            "elapsed": f"{e - s:.2f}s"
                        }
                        st.session_state["pdf_assets"] = []
                        st.session_state["pdf_bytes"] = None
                        st.session_state["mail_df"] = None
                        st.session_state["current_sheet"] = None
                        st.rerun()
                    else:
                        st.error(msg)
                except Exception as e:
                    st.error(f"Error: {e}")
        return

    # ----------------------------
    # 분석 후 상태
    # ----------------------------
    data = st.session_state["analyzed_data"]
    cleaned_data = data["cleaned_data"]
    trash_data = data["trash_data"]
    excel_buffer = data["excel_buffer"]
    filename = data["filename"]

    t_clean = sum(len(df) for df in cleaned_data.values())
    t_trash = sum(len(df) for df in trash_data) if trash_data else 0

    # KPI 카드
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">✨ 정제된 데이터</div>
                <div class="kpi-value val-clean">{t_clean:,}</div>
                <div class="kpi-delta">Clean Rows</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">🗑️ 중복 데이터</div>
                <div class="kpi-value val-trash">{t_trash:,}</div>
                <div class="kpi-delta">- Duplicates</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with c3:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-title">🚀 처리 속도</div>
                <div class="kpi-value val-speed">{data['elapsed']}</div>
                <div class="kpi-delta">Ultra Fast</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("🛠️ 작업 컨트롤 패널")

    mask_check = st.checkbox("🔒 개인정보 마스킹 (이름/번호 가리기)", value=True)

    col_act1, col_act2, col_act3 = st.columns(3, gap="medium")

    # 엑셀 다운로드
    with col_act1:
        final_buffer = excel_buffer
        if mask_check:
            masked_dict = {k: cleaner.mask_personal_info(v) for k, v in cleaned_data.items()}
            final_buffer = io.BytesIO()
            with pd.ExcelWriter(final_buffer, engine="xlsxwriter") as w:
                for k, v in masked_dict.items():
                    v.to_excel(w, sheet_name=k, index=False)

        st.download_button(
            "💾 엑셀 다운로드",
            data=final_buffer.getvalue(),
            file_name=f"Cleaned_{filename}",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
            key="dn_excel"
        )

    # PDF 리포트
    with col_act2:
        stats = {"total_rows": t_clean + t_trash, "removed_rows": t_trash, "missing_info_rows": 0}
        f_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts", "NanumGothic.ttf")
        f_path = os.path.abspath(f_path)

        if st.button("📄 PDF 리포트 생성", use_container_width=True, key="btn_pdf"):
            if not os.path.exists(f_path):
                st.error("폰트 없음")
            else:
                try:
                    pdf_assets = st.session_state.get("pdf_assets", [])

                    if mask_check:
                        masked_assets = []
                        for kind, title, payload in pdf_assets:
                            if kind == "table" and isinstance(payload, pd.DataFrame):
                                try:
                                    masked_assets.append((kind, title, cleaner.mask_personal_info(payload)))
                                except Exception:
                                    masked_assets.append((kind, title, payload))
                            else:
                                masked_assets.append((kind, title, payload))
                        pdf_assets = masked_assets

                    pdf = reporter.create_pdf_report(
                        stats,
                        cleaned_data,
                        assets=pdf_assets,
                        title=f"Mice Excel Data Cleaner Pro - Report ({filename})",
                        font_path=f_path
                    )
                    st.session_state["pdf_bytes"] = pdf
                    st.toast("PDF 생성 완료!", icon="✅")
                except Exception as e:
                    st.error(f"실패: {e}")

        if st.session_state.get("pdf_bytes"):
            st.download_button(
                "📥 PDF 받기",
                st.session_state["pdf_bytes"],
                f"report_{os.path.splitext(filename)[0]}.pdf",
                "application/pdf",
                use_container_width=True,
                key="dn_pdf"
            )

    # DB 저장
    with col_act3:
        if st.button("🗄️ DB에 저장하기", use_container_width=True, key="btn_db"):
            db_payload = build_db_payload(cleaned_data)

            with st.expander("🔎 DB에 저장될 데이터 미리보기 (DB 고정규격만 저장)", expanded=False):
                st.caption("DB 저장 규격 컬럼: " + ", ".join(DB_SCHEMA_COLS))
                preview_sheet = st.session_state.get("current_sheet") or list(db_payload.keys())[0]
                st.write(f"미리보기 시트: **{preview_sheet}**")
                st.dataframe(db_payload[preview_sheet].head(50), use_container_width=True, hide_index=True)

            suc, m = database.save_to_db(db_payload, filename)
            if suc:
                st.toast("저장 완료! (DB에는 고정 규격 컬럼만 저장됨)", icon="✅")
            else:
                st.error(m)

    st.markdown("---")

    # ==========================================
    # ✅ (공통) 시트 선택 + 상세 검색(필터)
    #   - 인사이트 탭 / 메일링 탭이 같은 대상(view_df)을 공유
    # ==========================================
    if cleaned_data:
        pdf_assets_reset()

        c_sel1, _ = st.columns([1, 4])
        with c_sel1:
            sh = st.selectbox("분석 시트", list(cleaned_data.keys()), key="sheet_select")

        # 시트 변경 시 메일 관련 상태 초기화
        if st.session_state.get("current_sheet") != sh:
            st.session_state["current_sheet"] = sh
            st.session_state["mail_df"] = None
            st.session_state["pdf_bytes"] = None

        df = cleaned_data[sh]

        with st.expander("🔍 상세 검색", expanded=False):
            cols = st.multiselect("필터 컬럼", df.columns, key=f"filter_cols_{sh}")
            conds = {c: st.text_input(f"'{c}' 검색", key=f"filter_{sh}_{c}") for c in cols}

        # ✅ 필터 적용 결과(view_df)
        view_df = df.copy()
        for c, val in conds.items():
            if val:
                view_df = view_df[view_df[c].astype(str).str.contains(val, case=False, na=False)]

        # 메일 템플릿 적용된 DF가 있으면 그걸 우선 사용
        display_df = st.session_state["mail_df"] if st.session_state.get("mail_df") is not None else view_df

        # ==========================================
        # ✅ 탭 구성: 인사이트 / 메일링 / 휴지통 / DB
        # ==========================================
        t_insight, t_mail, t_trash, t_db = st.tabs(
            ["📊 인사이트 & 필터", "📧 메일링", "🗑️ 휴지통 (복구)", "💾 DB 히스토리"]
        )

        # -------------------------------
        # Tab 1: 인사이트
        # -------------------------------
        with t_insight:
            # (1) 만족도/리뷰
            render_satisfaction_and_review(display_df, sheet_name=sh)

            # (2) 등록일
            render_registration_charts(display_df, sheet_name=sh)

            # (3) 인사이트(차트+표)
            render_insights_dashboard(display_df, sheet_name=sh)

        # -------------------------------
        # Tab 2: 메일링 (사진처럼 좌/우 + 미리보기)
        # -------------------------------
        with t_mail:
            # ✅ 메일링 UI는 여기서만 보이도록 분리
            render_email_sender(view_df=view_df, base_df=df, key_prefix=f"mail_{sh}")

        # -------------------------------
        # Tab 3: 휴지통 (복구)
        # -------------------------------
        with t_trash:
            if trash_data:
                full_trash = pd.concat(trash_data)
                sheets = full_trash["[원본시트]"].unique()
                sel = st.selectbox("확인할 시트", sheets, key="trash_sheet")
                subset = full_trash[full_trash["[원본시트]"] == sel].dropna(axis=1, how="all")
                st.warning(f"🚨 {len(subset)}건 중복 제거됨")

                restore_df = subset.copy()
                restore_df.insert(0, "선택", False)
                edited_trash = st.data_editor(
                    restore_df,
                    hide_index=True,
                    use_container_width=True,
                    column_config={"선택": st.column_config.CheckboxColumn(required=True)},
                    key="trash_editor"
                )

                if st.button("♻️ 선택 항목 복구", type="primary", key="restore_btn"):
                    to_restore = edited_trash[edited_trash["선택"] == True]
                    if not to_restore.empty:
                        rows = to_restore.drop(columns=["선택"])
                        if "[원본시트]" in rows.columns:
                            rows = rows.drop(columns=["[원본시트]"])
                        cur = st.session_state["analyzed_data"]["cleaned_data"][sel]
                        st.session_state["analyzed_data"]["cleaned_data"][sel] = pd.concat([cur, rows], ignore_index=True)

                        rem = edited_trash[edited_trash["선택"] == False].drop(columns=["선택"])
                        oth = full_trash[full_trash["[원본시트]"] != sel]
                        new_trash = []
                        if not rem.empty:
                            new_trash.append(rem)
                        if not oth.empty:
                            new_trash.append(oth)
                        st.session_state["analyzed_data"]["trash_data"] = new_trash
                        st.toast("복구 완료!", icon="✅")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.warning("항목 선택 필요")
            else:
                st.success("중복 없음")

        # -------------------------------
        # Tab 4: DB 히스토리
        # -------------------------------
        with t_db:
            tbls = database.get_table_names()
            if tbls:
                target = st.selectbox("테이블 선택", tbls, key="db_table")
                q = st.text_area("SQL 쿼리", f"SELECT * FROM {target} LIMIT 50", key="sql_text")
                if st.button("쿼리 실행", use_container_width=True, key="sql_run"):
                    d, m = database.execute_query(q)
                    if d is not None:
                        st.dataframe(d)
                    else:
                        st.error(m)
            else:
                st.info("데이터 없음")