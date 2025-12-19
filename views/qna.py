import streamlit as st
import pandas as pd
import time
from modules import database

def render_qna():
    with st.container():
        st.markdown('<div class="qna-input-container">', unsafe_allow_html=True)

        c_cat, c_writer, c_title = st.columns([1.5, 1.5, 7])
        with c_cat:
            category = st.selectbox("분류", ["🚨 오류", "💡 건의사항"], label_visibility="collapsed")
        with c_writer:
            writer = st.text_input("작성자", placeholder="작성자명", label_visibility="collapsed")
        with c_title:
            title_input = st.text_input("제목", placeholder="제목을 입력하세요", label_visibility="collapsed")

        content_input = st.text_area(
            "내용",
            placeholder="상세 내용을 입력하세요...",
            height=200,
            label_visibility="collapsed"
        )

        _, c_btn = st.columns([8.5, 1.5])
        with c_btn:
            if st.button("등록하기", key="qna_reg", type="primary", use_container_width=True):
                if writer and title_input and content_input:
                    clean_cat = "오류" if "오류" in category else "건의사항"
                    if database.add_question(writer, clean_cat, title_input, content_input):
                        st.toast("게시글이 등록되었습니다!", icon="✅")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("저장 실패")
                else:
                    st.warning("모든 항목을 입력해주세요.")

        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()
    st.subheader("📋 문의 내역")

    t_err, t_idea = st.tabs(["🚨 오류 제보", "💡 건의사항"])
    qna_df = database.get_qna_list()

    def render_list(df: pd.DataFrame):
        if df.empty:
            st.info("등록된 게시글이 없습니다.")
            return

        for _, row in df.iterrows():
            status_badge = (
                '<span class="badge-done">답변완료</span>'
                if row["status"] == "답변완료"
                else '<span class="badge-pending">대기중</span>'
            )
            cat_badge = (
                '<span class="badge-err">오류</span>'
                if row["category"] == "오류"
                else '<span class="badge-idea">건의</span>'
            )
            ans_html = ""
            if row["answer"]:
                ans_html = f'''
                <div class="qna-answer" style="margin-top:15px; padding-top:10px;
                    border-top:1px solid rgba(255,255,255,0.1);">
                    ↳ 👨‍💻 <b>관리자:</b> {row["answer"]}
                </div>
                '''

            st.markdown(
                f"""
                <div class="qna-box">
                    <div style="display:flex; justify-content:space-between; margin-bottom:8px;
                                color:#94a3b8; font-size:0.85rem;">
                        <span>{cat_badge} &nbsp; {row["writer"]} · {row["created_at"]}</span>
                        {status_badge}
                    </div>
                    <div style="color:#fff; font-weight:700; font-size:1.1rem; margin-bottom:5px;">
                        {row["title"]}
                    </div>
                    <div style="color:#cbd5e1; font-weight:400; line-height:1.6;">
                        {row["content"]}
                    </div>
                    {ans_html}
                </div>
                """,
                unsafe_allow_html=True,
            )

    with t_err:
        if not qna_df.empty:
            render_list(qna_df[qna_df["category"] == "오류"])
        else:
            st.info("등록된 오류 제보가 없습니다.")

    with t_idea:
        if not qna_df.empty:
            render_list(qna_df[qna_df["category"] == "건의사항"])
        else:
            st.info("등록된 건의사항이 없습니다.")