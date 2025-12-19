import streamlit as st
import os
from dotenv import load_dotenv

from ui.styles import apply_global_styles
from core.state import init_session_state, navigate_to, reset_analysis, logout
from views.dashboard import render_dashboard
from views.qna import render_qna
from views.admin import render_admin

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

init_session_state()
apply_global_styles()

# ==========================================
# 2. 상단 네비게이션
# ==========================================
col_nav1, col_nav2, col_nav3, col_title, col_reset = st.columns(
    [1, 1, 1, 20, 3],
    gap="small"
)

with col_nav1:
    if st.button("🏠", help="메인 대시보드", key="nav_home"):
        navigate_to("dashboard")

with col_nav2:
    if st.button("💬", help="문의/오류 제보", key="nav_qna"):
        navigate_to("qna")

with col_nav3:
    if st.button("⚙️", help="관리자 설정", key="nav_admin"):
        navigate_to("admin")

with st.container():
    if st.session_state["page"] == "dashboard":
        st.markdown('<div class="hero-title">Mice Excel Data Cleaner Pro</div>', unsafe_allow_html=True)
        st.markdown('<div class="hero-subtitle">복잡한 명단 정리, AI 자동화로 단계별로 안전하게 처리하세요.</div>', unsafe_allow_html=True)
    elif st.session_state["page"] == "qna":
        st.markdown('<div class="hero-title">💬 Q&A Board</div>', unsafe_allow_html=True)
        st.markdown('<div class="hero-subtitle">서비스 이용 중 궁금한 점이나 건의사항을 남겨주세요.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="hero-title" style="color:#94a3b8;">⚙️ Admin Settings</div>', unsafe_allow_html=True)
        st.markdown('<div class="hero-subtitle">관리자 전용 설정 페이지입니다.</div>', unsafe_allow_html=True)

with col_reset:
    if st.session_state.get("analyzed_data") is not None and st.session_state["page"] == "dashboard":
        if st.button("🔄 새 파일 분석", key="reset_btn_top", type="secondary", use_container_width=True):
            reset_analysis()

st.markdown("<div style='height:0px'></div>", unsafe_allow_html=True)

# ==========================================
# 3. 페이지 라우팅
# ==========================================
page = st.session_state["page"]

if page == "qna":
    render_qna()
elif page == "admin":
    render_admin(ADMIN_ID, ADMIN_PW, logout)
else:
    render_dashboard()