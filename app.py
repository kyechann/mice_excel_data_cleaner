import streamlit as st
import pandas as pd
import io
import plotly.express as px
import time
from modules import cleaner, database, reporter, mailer
import os
from dotenv import load_dotenv

# ==========================================
# 0. 환경 변수 로드
# ==========================================
load_dotenv()
ADMIN_ID = os.getenv("ADMIN_ID", "admin")
ADMIN_PW = os.getenv("ADMIN_PW", "1234")

# ==========================================
# 1. 페이지 설정 및 세션 상태
# ==========================================
st.set_page_config(
    page_title="Data Cleaner Pro",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="collapsed"
)

if 'page' not in st.session_state:
    st.session_state['page'] = 'dashboard'
if 'analyzed_data' not in st.session_state:
    st.session_state['analyzed_data'] = None
if 'admin_logged_in' not in st.session_state:
    st.session_state['admin_logged_in'] = False
if 'mail_df' not in st.session_state:
    st.session_state['mail_df'] = None
if 'current_sheet' not in st.session_state:
    st.session_state['current_sheet'] = None


def navigate_to(page: str):
    st.session_state['page'] = page
    st.rerun()


def reset_analysis():
    st.session_state['analyzed_data'] = None
    st.session_state['mail_df'] = None
    st.rerun()


def logout():
    st.session_state['admin_logged_in'] = False
    st.toast("로그아웃 되었습니다.", icon="👋")
    navigate_to('dashboard')


# ==========================================
# 2. 글로벌 스타일 (CSS)
# ==========================================
st.markdown("""
<style>
    @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.8/dist/web/static/pretendard.css");
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    
    /* ===================== 공통 배경 ===================== */
    .stApp {
        background-color: #09090b;
        background-image: 
            radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.15) 0px, transparent 50%),
            radial-gradient(at 100% 100%, rgba(168, 85, 247, 0.15) 0px, transparent 50%);
    }

    /* ===================================================== */
    /* [0] 모든 버튼 기본값: 박스/테두리 제거 (아이콘용 베이스) */
    /*     - 아래 [A]에서 필요한 버튼만 다시 스타일 입힘       */
    /* ===================================================== */
    .stButton > button {
        background: transparent !important;
        background-color: transparent !important;
        background-image: none !important;
        border: none !important;
        box-shadow: none !important;
        outline: none !important;

        padding: 0.35rem 0.75rem !important;
        border-radius: 0.5rem !important;
        font-size: 0.95rem !important;
        color: #e5e7eb !important;
    }

    /* ===================================================== */
    /* [A] 4번째 컬럼 이후 버튼 (실제 작업 버튼) 디자인        */
    /*      - 다운로드, PDF, DB 저장 같은 애들만 이 스타일   */
    /* ===================================================== */

    /* 공통 크기/레이아웃 */
    div[data-testid="column"]:nth-of-type(n+4) .stButton > button {
        height: 52px !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        width: 100%;
        margin-top: 0px !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        backdrop-filter: blur(10px);
    }

    /* Primary 버튼 (예: 주요 액션) */
    div[data-testid="column"]:nth-of-type(n+4) .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #6366f1, #8b5cf6, #ec4899) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        box-shadow: 0 0 15px rgba(139, 92, 246, 0.4) !important;
    }
    div[data-testid="column"]:nth-of-type(n+4) .stButton > button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 0 30px rgba(139, 92, 246, 0.7) !important;
    }

    /* Secondary 버튼 (예: 보조 액션) */
    div[data-testid="column"]:nth-of-type(n+4) .stButton > button[kind="secondary"] {
        background: rgba(255, 255, 255, 0.03) !important;
        color: #e2e8f0 !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
    }
    div[data-testid="column"]:nth-of-type(n+4) .stButton > button[kind="secondary"]:hover {
        border-color: #38bdf8 !important;
        background: rgba(255, 255, 255, 0.1) !important;
        box-shadow: 0 0 15px rgba(56, 189, 248, 0.3) !important;
        transform: translateY(-2px);
    }

    /* ===================================================== */
    /* [B] 상단 네비게이션 아이콘 버튼 (페이지 상단 첫 3개 버튼) */
    /* ===================================================== */

    /* 페이지에서 처음 등장하는 3개의 stButton 래퍼를 전부 투명 처리 */
    div.stButton:nth-of-type(-n+3),
    div.stButton:nth-of-type(-n+3) * {
        background: transparent !important;
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }

    /* 그 3개 버튼의 아이콘 스타일만 별도로 지정 */
    div.stButton:nth-of-type(-n+3) > button {
        padding: 0 !important;
        margin: 0 8px !important;
        width: auto !important;
        height: auto !important;
        border-radius: 0 !important;

        display: flex !important;
        align-items: center !important;
        justify-content: center !important;

        font-size: clamp(3.0rem, 4.0vw, 3.6rem) !important;
        line-height: 1 !important;
        color: #e5e7eb !important;
        cursor: pointer;
    }

    div.stButton:nth-of-type(-n+3) > button:hover {
        color: #60a5fa !important;
        transform: scale(1.08);
        transition: transform 0.15s ease;
    }

    div.stButton:nth-of-type(-n+3) > button:active,
    div.stButton:nth-of-type(-n+3) > button:focus,
    div.stButton:nth-of-type(-n+3) > button:focus-visible {
        color: #3b82f6 !important;
        outline: none !important;
        box-shadow: none !important;
    }
    
    
    /* ===================== 나머지 공통 UI ===================== */
    .hero-title {
        font-size: clamp(3rem, 6vw, 4.5rem); 
        font-weight: 800;
        margin-top: 5px;
        margin-bottom: 5px;
        background: linear-gradient(90deg, #fff, #94a3b8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1.1;
    }
    .hero-subtitle {
        color: #64748b;
        font-size: 1.2rem;
        margin-bottom: 40px;
    }

    .kpi-card {
        background: rgba(30, 41, 59, 0.4);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 20px;
        padding: 24px;
        text-align: center;
        transition: 0.3s;
    }
    .kpi-card:hover {
        background: rgba(30, 41, 59, 0.6);
        border-color: rgba(99, 102, 241, 0.5);
        box-shadow: 0 10px 40px -10px rgba(99, 102, 241, 0.3);
    }
    .kpi-value {
        font-size: clamp(2.5rem, 5vw, 4rem);
        font-weight: 800;
        margin: 0;
        line-height: 1.1;
    }
    .val-clean { color: #22d3ee; text-shadow: 0 0 20px rgba(34, 211, 238, 0.3); }
    .val-trash { color: #fb7185; text-shadow: 0 0 20px rgba(251, 113, 133, 0.3); }
    .val-speed { color: #a78bfa; text-shadow: 0 0 20px rgba(167, 139, 250, 0.3); }

    .stTextInput input,
    .stTextArea textarea,
    .stSelectbox div[data-baseweb="select"] {
        background-color: rgba(0, 0, 0, 0.3) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        color: white !important;
        border-radius: 10px !important;
    }
    
    .qna-input-container {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
    }
    .qna-box {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
    }
    .badge-pending {
        background: rgba(100, 116, 139, 0.2);
        color: #cbd5e1;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        border: 1px solid rgba(100, 116, 139, 0.4);
    }
    .badge-done {
        background: rgba(16, 185, 129, 0.2);
        color: #6ee7b7;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        border: 1px solid rgba(16, 185, 129, 0.4);
    }
    .badge-err {
        background: rgba(239, 68, 68, 0.2);
        color: #fca5a5;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        border: 1px solid rgba(239, 68, 68, 0.4);
    }
    .badge-idea {
        background: rgba(245, 158, 11, 0.2);
        color: #fcd34d;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        border: 1px solid rgba(245, 158, 11, 0.4);
    }

    .stCheckbox label {
        color: #cbd5e1;
        font-weight: 500;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(255,255,255,0.02);
        padding: 5px;
        border-radius: 12px;
        border: none;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        background-color: transparent;
        border: none;
        color: #64748b;
        border-radius: 8px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: rgba(255,255,255,0.1) !important;
        color: white !important;
    }
    
    .nav-row .stButton {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    
    .nav-row .stButton > button {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

/* ================================================= */
/* nav-row 안의 아이콘 버튼에서 박스/테두리 완전 제거 */
/* ================================================= */
.nav-row .stButton,
.nav-row .stButton > button {
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
}
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 상단 네비게이션
# ==========================================
st.markdown('<div class="nav-row">', unsafe_allow_html=True)

col_nav1, col_nav2, col_nav3, col_title, col_reset = st.columns(
    [1, 1, 1, 20, 3],   # 아이콘 3개는 좁게, 타이틀/리셋은 넓게
    gap="small"
)

with col_nav1:
    if st.button("🏠", help="메인 대시보드", key="nav_home"):
        navigate_to('dashboard')

with col_nav2:
    if st.button("💬", help="문의/오류 제보", key="nav_qna"):
        navigate_to('qna')

with col_nav3:
    if st.button("⚙️", help="관리자 설정", key="nav_admin"):
        navigate_to('admin')

st.markdown('</div>', unsafe_allow_html=True)   # nav-row 끝

# 타이틀 영역
with st.container():
    if st.session_state['page'] == 'dashboard':
        st.markdown(
            '<div class="hero-title">Mice Excel Data Cleaner Pro</div>',
            unsafe_allow_html=True
        )
        st.markdown(
            '<div class="hero-subtitle">복잡한 명단 정리, AI 자동화로 1초 만에 해결하세요.</div>',
            unsafe_allow_html=True
        )
    elif st.session_state['page'] == 'qna':
        st.markdown(
            '<div class="hero-title">💬 Q&A Board</div>',
            unsafe_allow_html=True
        )
        st.markdown(
            '<div class="hero-subtitle">서비스 이용 중 궁금한 점이나 건의사항을 남겨주세요.</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div class="hero-title" style="color:#94a3b8;">⚙️ Admin Settings</div>',
            unsafe_allow_html=True
        )
        st.markdown(
            '<div class="hero-subtitle">관리자 전용 설정 페이지입니다.</div>',
            unsafe_allow_html=True
        )

# 새 파일 분석 버튼 (타이틀 우측)
with col_reset:
    if st.session_state['analyzed_data'] is not None and st.session_state['page'] == 'dashboard':
        st.write("")
        if st.button("🔄 새 파일 분석", key="reset_btn_top", type="secondary", use_container_width=True):
            reset_analysis()

st.write("")

# ==========================================
# 4. 페이지 라우팅
# ==========================================

# -------------------------------
# Q&A 페이지
# -------------------------------
if st.session_state['page'] == 'qna':
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
            st.write("")
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
        st.markdown('</div>', unsafe_allow_html=True)

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
                if row['status'] == '답변완료'
                else '<span class="badge-pending">대기중</span>'
            )
            cat_badge = (
                '<span class="badge-err">오류</span>'
                if row['category'] == '오류'
                else '<span class="badge-idea">건의</span>'
            )
            ans_html = ""
            if row['answer']:
                ans_html = f'''
                <div class="qna-answer" style="margin-top:15px; padding-top:10px;
                    border-top:1px solid rgba(255,255,255,0.1);">
                    ↳ 👨‍💻 <b>관리자:</b> {row["answer"]}
                </div>
                '''

            st.markdown(f"""
            <div class="qna-box">
                <div style="display:flex; justify-content:space-between; margin-bottom:8px;
                            color:#94a3b8; font-size:0.85rem;">
                    <span>{cat_badge} &nbsp; {row['writer']} · {row['created_at']}</span>
                    {status_badge}
                </div>
                <div style="color:#fff; font-weight:700; font-size:1.1rem; margin-bottom:5px;">
                    {row['title']}
                </div>
                <div style="color:#cbd5e1; font-weight:400; line-height:1.6;">
                    {row['content']}
                </div>
                {ans_html}
            </div>
            """, unsafe_allow_html=True)

    with t_err:
        if not qna_df.empty:
            render_list(qna_df[qna_df['category'] == '오류'])
        else:
            st.info("등록된 오류 제보가 없습니다.")

    with t_idea:
        if not qna_df.empty:
            render_list(qna_df[qna_df['category'] == '건의사항'])
        else:
            st.info("등록된 건의사항이 없습니다.")

# -------------------------------
# Admin 페이지
# -------------------------------
elif st.session_state['page'] == 'admin':
    if not st.session_state['admin_logged_in']:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.markdown(
                "<br><br><h2 style='text-align:center;'>🔒 관리자 로그인</h2>",
                unsafe_allow_html=True
            )
            with st.form("admin_login"):
                uid = st.text_input("ID")
                upw = st.text_input("PW", type="password")
                if st.form_submit_button("Login", type="primary", use_container_width=True):
                    if uid == ADMIN_ID and upw == ADMIN_PW:
                        st.session_state['admin_logged_in'] = True
                        st.rerun()
                    else:
                        st.error("정보가 일치하지 않습니다.")
    else:
        col_dummy, col_out = st.columns([9, 1])
        with col_out:
            if st.button("로그아웃", key="logout_btn"):
                logout()

        st.markdown("---")
        tab_map, tab_qna, tab_sys = st.tabs(["🧩 매핑 관리", "📝 Q&A 답변", "⚠️ 시스템"])

        # 매핑 관리
        with tab_map:
            c_map = cleaner.load_mapping()
            df = pd.DataFrame(list(c_map.items()), columns=['입력', '변환'])
            edit = st.data_editor(
                df,
                num_rows="dynamic",
                use_container_width=True,
                height=500,
                hide_index=True
            )
            if st.button("규칙 저장", key="map_save", type="primary"):
                cleaner.save_mapping(dict(zip(edit['입력'], edit['변환'])))
                st.toast("저장됨!", icon="✅")

        # Q&A 답변
        with tab_qna:
            st.subheader("📬 답변 대기 중인 질문")
            qna_df = database.get_qna_list()
            if not qna_df.empty:
                pending = qna_df[qna_df['status'] == '대기중']
                if not pending.empty:
                    q_opts = {
                        f"[{row['category']}] {row['title']} ({row['writer']})": row['id']
                        for _, row in pending.iterrows()
                    }
                    sel_label = st.selectbox("질문 선택", list(q_opts.keys()))
                    sel_id = q_opts[sel_label]
                    target = pending[pending['id'] == sel_id].iloc[0]
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

        # 시스템
        with tab_sys:
            st.error("⚠️ 데이터 초기화")
            if st.button("전체 삭제", key="db_del"):
                database.clear_database()
                st.toast("삭제 완료", icon="💥")

# -------------------------------
# Dashboard 페이지
# -------------------------------
else:
    # 분석 전 상태
    if st.session_state['analyzed_data'] is None:
        uploaded_file = st.file_uploader(
            "분석할 엑셀 파일을 드래그하거나 선택하세요",
            type=['xlsx']
        )
        if uploaded_file:
            with st.spinner("⚡ AI 엔진 구동 중..."):
                try:
                    s = time.time()
                    buf, clean, trash, msg = cleaner.run_cleaning_pipeline(uploaded_file)
                    e = time.time()
                    if msg == "Success":
                        st.session_state['analyzed_data'] = {
                            'excel_buffer': buf,
                            'cleaned_data': clean,
                            'trash_data': trash,
                            'filename': uploaded_file.name,
                            'elapsed': f"{e - s:.2f}s"
                        }
                        st.rerun()
                    else:
                        st.error(msg)
                except Exception as e:
                    st.error(f"Error: {e}")

    # 분석 후 상태
    else:
        data = st.session_state['analyzed_data']
        cleaned_data = data['cleaned_data']
        trash_data = data['trash_data']
        excel_buffer = data['excel_buffer']
        filename = data['filename']

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

        st.markdown('<div style="margin-bottom: 10px;">', unsafe_allow_html=True)
        mask_check = st.checkbox("🔒 개인정보 마스킹 (이름/번호 가리기)", value=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # 상단 작업 버튼 3개
        with st.container():
            col_act1, col_act2, col_act3 = st.columns(3, gap="medium")

            # 엑셀 다운로드
            with col_act1:
                final_buffer = excel_buffer
                if mask_check:
                    masked_dict = {
                        k: cleaner.mask_personal_info(v)
                        for k, v in cleaned_data.items()
                    }
                    final_buffer = io.BytesIO()
                    with pd.ExcelWriter(final_buffer, engine='xlsxwriter') as w:
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
                stats = {
                    'total_rows': t_clean + t_trash,
                    'removed_rows': t_trash,
                    'missing_info_rows': 0
                }
                f_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    'fonts',
                    'NanumGothic.ttf'
                )
                if st.button("📄 PDF 리포트 생성", use_container_width=True, key="btn_pdf"):
                    if not os.path.exists(f_path):
                        st.error("폰트 없음")
                    else:
                        try:
                            pdf = reporter.create_pdf_report(stats, cleaned_data)
                            st.download_button(
                                "📥 PDF 받기",
                                pdf,
                                "report.pdf",
                                "application/pdf",
                                use_container_width=True
                            )
                        except Exception:
                            st.error("실패")

            # DB 저장
            with col_act3:
                if st.button("🗄️ DB에 저장하기", use_container_width=True, key="btn_db"):
                    suc, m = database.save_to_db(cleaned_data, filename)
                    if suc:
                        st.toast("저장 완료!", icon="✅")
                    else:
                        st.error(m)

        st.markdown("---")
        t1, t2, t3 = st.tabs(["📊 인사이트 & 필터", "🗑️ 휴지통 (복구)", "💾 DB 히스토리"])

        # -------------------------------
        # Tab 1: 인사이트 & 필터
        # -------------------------------
        with t1:
            if cleaned_data:
                c_sel1, _ = st.columns([1, 4])
                with c_sel1:
                    sh = st.selectbox("분석 시트", list(cleaned_data.keys()))

                if st.session_state['current_sheet'] != sh:
                    st.session_state['current_sheet'] = sh
                    st.session_state['mail_df'] = None

                df = cleaned_data[sh]

                # 상세 검색
                with st.expander("🔍 상세 검색", expanded=False):
                    cols = st.multiselect("필터 컬럼", df.columns)
                    conds = {c: st.text_input(f"'{c}' 검색") for c in cols}
                    view_df = df.copy()
                    for c, val in conds.items():
                        if val:
                            view_df = view_df[
                                view_df[c].astype(str).str.contains(val, case=False)
                            ]
                # 메일/문자 템플릿 & 발송
                with st.expander("📧 메일/문자 템플릿 & 발송", expanded=False):
                    st.info(
                        "사용 가능 변수: "
                        + ", ".join([f'{{{c}}}' for c in df.columns])
                    )
                    default_msg = """[MICE 2025 컨퍼런스] 사전등록 확정 안내

안녕하세요, {이름}님.
신청해주신 내용으로 등록이 정상적으로 완료되었습니다.

▶ 소속: {소속}
▶ 연락처: {전화번호}

행사 당일, 등록데스크에서 본 메시지를 보여주시면 명찰을 수령하실 수 있습니다.
감사합니다."""
                    c_tmpl, c_mail = st.columns([1, 1])

                    with c_tmpl:
                        st.write("###### 📝 템플릿 작성")
                        tmpl = st.text_area(
                            "템플릿 내용",
                            default_msg,
                            height=200
                        )
                        if st.button("템플릿 적용 (표에 추가)", key="apply_tmpl"):
                            try:
                                view_df = cleaner.generate_message_column(
                                    view_df, tmpl
                                )
                                st.session_state['mail_df'] = view_df
                                st.success("생성 완료! (아래 표 확인)")
                            except Exception as e:
                                st.error(f"생성 실패: {e}")

                    display_df = (
                        st.session_state['mail_df']
                        if st.session_state['mail_df'] is not None
                        else view_df
                    )

                    with c_mail:
                        st.write("###### 🚀 이메일 발송 (SMTP)")
                        smtp_host = st.text_input("SMTP 서버", "smtp.gmail.com")
                        smtp_port = st.number_input("포트", value=465)

                        st.markdown("*보내는 메일 주소 (예: `myname@gmail.com`)*")
                        sender_email = st.text_input(
                            "보내는 메일",
                            label_visibility="collapsed"
                        )

                        st.markdown("*앱 비밀번호 (일반 비밀번호 아님!)*")
                        sender_pw = st.text_input(
                            "앱 비밀번호",
                            type="password",
                            label_visibility="collapsed"
                        )

                        mail_subject = st.text_input(
                            "메일 제목",
                            "[MICE 2025] 등록 안내"
                        )

                        mail_cols = [
                            c for c in display_df.columns
                            if '이메일' in str(c)
                            or 'email' in str(c).lower()
                        ]
                        idx = (
                            list(display_df.columns).index(mail_cols[0])
                            if mail_cols else 0
                        )
                        target_email_col = st.selectbox(
                            "받는 사람 이메일 컬럼",
                            display_df.columns,
                            index=idx
                        )

                        st.markdown("---")
                        st.write("###### 🧪 테스트 발송")
                        test_receiver = st.text_input(
                            "테스트 받는 사람 이메일",
                            placeholder="me@example.com"
                        )

                        if st.button("테스트 발송 (1건만)", key="test_mail_btn"):
                            if not test_receiver:
                                st.warning("테스트 이메일을 입력하세요.")
                            elif '생성된_메시지' not in display_df.columns:
                                st.error("먼저 템플릿을 적용해주세요.")
                            else:
                                test_df = display_df.head(1).copy().reset_index(drop=True)
                                test_df[target_email_col] = test_receiver
                                suc, s_cnt, f_cnt, logs = mailer.send_bulk_emails(
                                    test_df,
                                    sender_email,
                                    sender_pw,
                                    target_email_col,
                                    mail_subject,
                                    '생성된_메시지',
                                    smtp_host,
                                    smtp_port
                                )
                                if suc:
                                    st.success(f"테스트 발송 성공! ({test_receiver})")
                                else:
                                    st.error(f"실패: {logs[0]}")

                        st.markdown("---")
                        if st.button("전체 발송 시작 (주의)", type="primary", key="send_mail_real"):
                            if '생성된_메시지' not in display_df.columns:
                                st.error("먼저 '템플릿 적용' 버튼을 눌러 메시지를 생성해주세요.")
                            elif not sender_email or not sender_pw:
                                st.error("이메일 계정 정보를 입력해주세요.")
                            else:
                                send_df = display_df.reset_index(drop=True)
                                suc, s_cnt, f_cnt, logs = mailer.send_bulk_emails(
                                    send_df,
                                    sender_email,
                                    sender_pw,
                                    target_email_col,
                                    mail_subject,
                                    '생성된_메시지',
                                    smtp_host,
                                    smtp_port
                                )
                                if suc:
                                    st.success(f"발송 완료! (성공: {s_cnt}, 실패: {f_cnt})")
                                else:
                                    st.error(f"발송 실패: {logs[0]}")

                # 시각화 & 데이터 테이블
                if not display_df.empty:
                    potential = [
                        c for c in display_df.columns
                        if not any(
                            k in str(c).lower()
                            for k in [
                                '이름', 'name', '이메일', 'email', 'phone',
                                '전화', '비고', 'check', 'no', '메시지'
                            ]
                        )
                    ]
                    if potential:
                        st.markdown(f"##### 📈 **{sh}** 시각화")
                        cols_ui = st.columns(2)
                        for i, col_name in enumerate(potential):
                            with cols_ui[i % 2]:
                                c_data = (
                                    display_df[col_name]
                                    .fillna('미입력')
                                    .value_counts()
                                    .reset_index()
                                )
                                c_data.columns = [col_name, 'Count']
                                if len(c_data) <= 5:
                                    fig = px.pie(
                                        c_data,
                                        values='Count',
                                        names=col_name,
                                        title=f"{col_name} 비율",
                                        hole=0.3,
                                        template="plotly_dark"
                                    )
                                    fig.update_traces(
                                        textposition='inside',
                                        textinfo='percent+label'
                                    )
                                else:
                                    top = c_data.head(10)
                                    fig = px.bar(
                                        top,
                                        x=col_name,
                                        y='Count',
                                        title=f"{col_name} TOP 10",
                                        text='Count',
                                        template="plotly_dark"
                                    )
                                    fig.update_layout(xaxis_tickangle=-45)

                                fig.update_layout(
                                    paper_bgcolor="rgba(0,0,0,0)",
                                    plot_bgcolor="rgba(0,0,0,0)",
                                    height=400
                                )
                                st.plotly_chart(fig, use_container_width=True)

                    st.markdown("#### 📋 상세 데이터")
                    st.dataframe(
                        display_df,
                        use_container_width=True,
                        hide_index=True,
                        height=500
                    )
                else:
                    st.warning("데이터 없음")
            else:
                st.info("데이터 없음")

        # -------------------------------
        # Tab 2: 휴지통 (복구)
        # -------------------------------
        with t2:
            if trash_data:
                full_trash = pd.concat(trash_data)
                sheets = full_trash['[원본시트]'].unique()
                sel = st.selectbox("확인할 시트", sheets)
                subset = full_trash[full_trash['[원본시트]'] == sel].dropna(axis=1, how='all')
                st.warning(f"🚨 {len(subset)}건 중복 제거됨")

                restore_df = subset.copy()
                restore_df.insert(0, "선택", False)
                edited_trash = st.data_editor(
                    restore_df,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "선택": st.column_config.CheckboxColumn(required=True)
                    }
                )

                if st.button("♻️ 선택 항목 복구", type="primary", key="restore_btn"):
                    to_restore = edited_trash[edited_trash['선택'] == True]
                    if not to_restore.empty:
                        rows = to_restore.drop(columns=['선택'])
                        if '[원본시트]' in rows.columns:
                            rows = rows.drop(columns=['[원본시트]'])
                        cur = st.session_state['analyzed_data']['cleaned_data'][sel]
                        st.session_state['analyzed_data']['cleaned_data'][sel] = pd.concat(
                            [cur, rows],
                            ignore_index=True
                        )

                        rem = edited_trash[edited_trash['선택'] == False].drop(columns=['선택'])
                        oth = full_trash[full_trash['[원본시트]'] != sel]
                        new_trash = []
                        if not rem.empty:
                            new_trash.append(rem)
                        if not oth.empty:
                            new_trash.append(oth)
                        st.session_state['analyzed_data']['trash_data'] = new_trash
                        st.toast("복구 완료!", icon="✅")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.warning("항목 선택 필요")
            else:
                st.success("중복 없음")

        # -------------------------------
        # Tab 3: DB 히스토리
        # -------------------------------
        with t3:
            tbls = database.get_table_names()
            if tbls:
                target = st.selectbox("테이블 선택", tbls)
                q = st.text_area("SQL 쿼리", f"SELECT * FROM {target} LIMIT 50")
                if st.button("쿼리 실행", use_container_width=True, key="sql_run"):
                    d, m = database.execute_query(q)
                    if d is not None:
                        st.dataframe(d)
                    else:
                        st.error(m)
            else:
                st.info("데이터 없음")