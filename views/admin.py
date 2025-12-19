import streamlit as st
import pandas as pd
from modules import cleaner, database

def render_admin(admin_id: str, admin_pw: str, logout_fn):
    if not st.session_state["admin_logged_in"]:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.markdown("<br><br><h2 style='text-align:center;'>🔒 관리자 로그인</h2>", unsafe_allow_html=True)
            with st.form("admin_login"):
                uid = st.text_input("ID")
                upw = st.text_input("PW", type="password")
                if st.form_submit_button("Login", type="primary", use_container_width=True):
                    if uid == admin_id and upw == admin_pw:
                        st.session_state["admin_logged_in"] = True
                        st.rerun()
                    else:
                        st.error("정보가 일치하지 않습니다.")
        return

    col_dummy, col_out = st.columns([9, 1])
    with col_out:
        if st.button("로그아웃", key="logout_btn"):
            logout_fn()

    st.markdown("---")
    tab_map, tab_qna, tab_sys = st.tabs(["🧩 매핑 관리", "📝 Q&A 답변", "⚠️ 시스템"])

    with tab_map:
        c_map = cleaner.load_mapping()
        df = pd.DataFrame(list(c_map.items()), columns=["입력", "변환"])
        edit = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            height=500,
            hide_index=True
        )
        if st.button("규칙 저장", key="map_save", type="primary"):
            cleaner.save_mapping(dict(zip(edit["입력"], edit["변환"])))
            st.toast("저장됨!", icon="✅")

    with tab_qna:
        st.subheader("📬 답변 대기 중인 질문")
        qna_df = database.get_qna_list()
        if not qna_df.empty:
            pending = qna_df[qna_df["status"] == "대기중"]
            if not pending.empty:
                q_opts = {
                    f"[{row['category']}] {row['title']} ({row['writer']})": row["id"]
                    for _, row in pending.iterrows()
                }
                sel_label = st.selectbox("질문 선택", list(q_opts.keys()))
                sel_id = q_opts[sel_label]
                target = pending[pending["id"] == sel_id].iloc[0]
                st.info(f"Q. {target['content']}")
                ans = st.text_area("답변 입력")
                if st.button("답변 등록", key="ans_reg", type="primary"):
                    database.add_answer(sel_id, ans)
                    st.success("등록 완료")
                    st.rerun()
            else:
                st.success("대기 중인 질문이 없습니다.")

            with st.expander("전체 문의 기록 보기"):
                st.dataframe(qna_df, use_container_width=True)
        else:
            st.info("문의 내역이 없습니다.")

    with tab_sys:
        st.error("⚠️ 데이터 초기화")
        if st.button("전체 삭제", key="db_del"):
            database.clear_database()
            st.toast("삭제 완료", icon="💥")