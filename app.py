import streamlit as st
import pandas as pd
import io
import plotly.express as px
import time
from modules import cleaner, database, reporter, mailer
import os
import re
from collections import Counter
from dotenv import load_dotenv

try:
    from wordcloud import WordCloud
    import matplotlib.pyplot as plt
except ImportError:
    WordCloud = None
    plt = None


# ==========================================
# 0. 환경 변수 로드
# ==========================================
load_dotenv()
ADMIN_ID = os.getenv("ADMIN_ID", "admin")
ADMIN_PW = os.getenv("ADMIN_PW", "1234")

# ==========================================
# [DB 저장 전용] 고정 규격(컬럼) + alias 매핑
# ==========================================
DB_SCHEMA_COLS = ["이름", "소속", "직함", "전화번호", "이메일", "참가구분", "등록일", "평점", "리뷰", "비고"]

DB_COL_ALIASES = {
    "이름": ["이름", "성명", "name", "full name", "이름(name)", "이름 (name)", "이름 (Name)", "이름(Name)"],
    "소속": ["소속", "회사", "기관", "부서", "company", "organization", "organisation",
           "소속(company)", "소속 (company)", "소속 (Company)", "소속(Company)"],
    "직함": ["직함", "직급", "직책", "job", "job title", "position", "title", "role"],
    "전화번호": ["전화번호", "휴대폰", "연락처", "phone", "mobile", "tel", "contact", "contact no", "contact no.",
             "휴대폰 (Phone)", "휴대폰(Phone)", "Contact No.", "Contact No", "Contact"],
    "이메일": ["이메일", "e-mail", "email", "email address", "mail",
            "이메일 (E-mail)", "이메일(E-mail)", "Email Address", "Email"],
    "참가구분": ["참가구분", "구분", "참가 유형", "참가유형", "type", "attendee type", "category", "registration type"],
    "등록일": ["등록일", "신청일", "접수일", "date", "registration date", "registered at", "created at", "created_at"],

    "평점": ["평점", "rating", "score", "점수", "평점(0-10)", "평점(0~10)", "nps", "satisfaction", "만족도"],
    "리뷰": ["리뷰", "review", "comment", "comments", "의견", "코멘트", "후기", "리뷰(코멘트)", "만족도_리뷰"],
    "비고": ["비고", "메모", "note", "notes", "remark", "remarks", "etc", "기타"],
}


def _norm_col(x: str) -> str:
    """컬럼명 비교를 위해 정규화: 소문자/공백제거/괄호 등 제거"""
    if x is None:
        return ""
    s = str(x).strip().lower()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[()\[\]{}<>]", "", s)
    s = s.replace(".", "").replace("-", "").replace("_", "")
    return s


def _build_alias_lookup():
    lookup = {}
    for canonical, aliases in DB_COL_ALIASES.items():
        for a in aliases:
            lookup[_norm_col(a)] = canonical
    for c in DB_SCHEMA_COLS:
        lookup[_norm_col(c)] = c
    return lookup


_ALIAS_LOOKUP = _build_alias_lookup()


def project_df_to_db_schema(df: pd.DataFrame) -> pd.DataFrame:
    """
    df를 DB_SCHEMA_COLS로 투영:
    - alias 매핑으로 컬럼명 정규화
    - 없는 컬럼은 None 생성
    - 나머지 컬럼은 버림(=DB에 저장 안 함)
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=DB_SCHEMA_COLS)

    rename_map = {}
    for col in df.columns:
        key = _norm_col(col)
        if key in _ALIAS_LOOKUP:
            canonical = _ALIAS_LOOKUP[key]
            if canonical not in rename_map.values():
                rename_map[col] = canonical

    df2 = df.rename(columns=rename_map).copy()

    out = pd.DataFrame()
    for c in DB_SCHEMA_COLS:
        out[c] = df2[c] if c in df2.columns else None

    out["전화번호"] = out["전화번호"].astype(str).str.strip().replace({"nan": None, "None": None})
    out["이메일"] = out["이메일"].astype(str).str.strip().str.lower().replace({"nan": None, "none": None})
    out["등록일"] = out["등록일"].astype(str).str.strip().replace({"nan": None, "None": None})

    out["평점"] = pd.to_numeric(out["평점"], errors="coerce")
    out["리뷰"] = out["리뷰"].astype(str).str.strip().replace({"nan": None, "None": None, "none": None})

    return out


def build_db_payload(cleaned_data: dict) -> dict:
    payload = {}
    for sheet_name, df in cleaned_data.items():
        payload[sheet_name] = project_df_to_db_schema(df)
    return payload


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

if "pdf_assets" not in st.session_state:
    st.session_state["pdf_assets"] = []
if "pdf_bytes" not in st.session_state:
    st.session_state["pdf_bytes"] = None


def navigate_to(page: str):
    st.session_state['page'] = page
    st.rerun()


def reset_analysis():
    st.session_state['analyzed_data'] = None
    st.session_state['mail_df'] = None
    st.session_state['current_sheet'] = None
    st.session_state["pdf_assets"] = []
    st.session_state["pdf_bytes"] = None
    st.rerun()


def logout():
    st.session_state['admin_logged_in'] = False
    st.toast("로그아웃 되었습니다.", icon="👋")
    navigate_to('dashboard')


# ==========================================
# PDF assets helpers
# ==========================================
def pdf_assets_reset():
    st.session_state["pdf_assets"] = []


def pdf_add_plotly(fig, title: str):
    try:
        png = reporter.plotly_to_png_bytes(fig)  # kaleido 필요
        if png:
            st.session_state["pdf_assets"].append(("img", title, png))
    except Exception:
        pass


def pdf_add_mpl(fig, title: str):
    try:
        png = reporter.mpl_to_png_bytes(fig)
        if png:
            st.session_state["pdf_assets"].append(("img", title, png))
    except Exception:
        pass


def pdf_add_table(df: pd.DataFrame, title: str, head: int = 80):
    try:
        if df is not None and not df.empty:
            st.session_state["pdf_assets"].append(("table", title, df.head(head)))
    except Exception:
        pass


# ==========================================
# 등록일 분석 차트 (key 추가로 DuplicateElementId 방지)
# ==========================================
def render_registration_charts(display_df: pd.DataFrame, sheet_name: str = ""):
    date_col = None
    for c in display_df.columns:
        if str(c) == "등록일":
            date_col = c
            break
    if date_col is None:
        for c in display_df.columns:
            low = str(c).lower()
            if any(k in low for k in ["등록일", "신청일", "접수일", "date", "created", "registered"]):
                date_col = c
                break
    if date_col is None:
        return

    tmp = display_df.copy()
    tmp[date_col] = pd.to_datetime(tmp[date_col], errors="coerce")
    tmp = tmp.dropna(subset=[date_col])
    if tmp.empty:
        return

    st.markdown("---")
    st.subheader("📅 등록일 분석")

    daily = tmp.groupby(tmp[date_col].dt.date).size().reset_index(name="Count")
    daily.columns = ["등록일", "Count"]
    daily["등록일"] = pd.to_datetime(daily["등록일"])

    if len(daily) > 120:
        weekly = daily.set_index("등록일").resample("W-MON")["Count"].sum().reset_index()
        fig_trend = px.line(
            weekly, x="등록일", y="Count", markers=True,
            title="📈 등록 추이 (주별)", template="plotly_dark"
        )
    else:
        fig_trend = px.line(
            daily, x="등록일", y="Count", markers=True,
            title="📈 등록 추이 (일별)", template="plotly_dark"
        )

    fig_trend.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_trend, use_container_width=True, key=f"reg_trend_{sheet_name}")
    pdf_add_plotly(fig_trend, f"{sheet_name} - 등록 추이")

    daily_sorted = daily.sort_values("등록일").copy()
    daily_sorted["Cumulative"] = daily_sorted["Count"].cumsum()
    fig_cum = px.area(daily_sorted, x="등록일", y="Cumulative", title="📈 누적 등록 수", template="plotly_dark")
    fig_cum.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_cum, use_container_width=True, key=f"reg_cum_{sheet_name}")
    pdf_add_plotly(fig_cum, f"{sheet_name} - 누적 등록")

    type_col = "참가구분" if "참가구분" in tmp.columns else None
    if type_col:
        tmp3 = tmp.copy()
        tmp3["등록월"] = tmp3[date_col].dt.to_period("M").astype(str)
        g = tmp3.groupby(["등록월", type_col]).size().reset_index(name="Count")
        fig_stack = px.bar(g, x="등록월", y="Count", color=type_col, title="📊 참가구분별 등록 (월별)", template="plotly_dark")
        fig_stack.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis_tickangle=-45
        )
        st.plotly_chart(fig_stack, use_container_width=True, key=f"reg_stack_{sheet_name}")
        pdf_add_plotly(fig_stack, f"{sheet_name} - 참가구분별 월별 등록")

    tmp2 = tmp.copy()
    tmp2["등록월"] = tmp2[date_col].dt.to_period("M").astype(str)
    tmp2["요일"] = tmp2[date_col].dt.day_name()

    dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    tmp2["요일"] = pd.Categorical(tmp2["요일"], categories=dow_order, ordered=True)

    heat = tmp2.groupby(["요일", "등록월"]).size().reset_index(name="Count")
    heat_pivot = heat.pivot(index="요일", columns="등록월", values="Count").fillna(0)

    fig_heat = px.imshow(
        heat_pivot,
        aspect="auto",
        title="🗓️ 등록 패턴 히트맵 (월 × 요일)",
        template="plotly_dark"
    )
    fig_heat.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_heat, use_container_width=True, key=f"reg_heat_{sheet_name}")
    pdf_add_plotly(fig_heat, f"{sheet_name} - 등록 히트맵(월×요일)")


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
/* [0] 버튼 기본값: 박스/테두리 제거 (기본은 투명)          */
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
/* ===================================================== */
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

/* Primary 버튼 */
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

/* Secondary 버튼 */
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
    margin-bottom: 22px;
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

/* 상단 3개 아이콘 버튼 박스 제거 */
div[data-testid="stHorizontalBlock"]:nth-of-type(1)
  div[data-testid="column"]:nth-of-type(-n+3)
  div[data-testid="stButton"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
}

div[data-testid="stHorizontalBlock"]:nth-of-type(1)
  div[data-testid="column"]:nth-of-type(-n+3)
  div[data-testid="stButton"] > button,
div[data-testid="stHorizontalBlock"]:nth-of-type(1)
  div[data-testid="column"]:nth-of-type(-n+3)
  div[data-testid="stButton"] > button[data-testid^="baseButton"] {
    background: transparent !important;
    background-color: transparent !important;
    background-image: none !important;
    border: 0 !important;
    box-shadow: none !important;
    outline: none !important;

    padding: 0 !important;
    margin: 0 10px !important;
    width: auto !important;
    height: auto !important;
    min-height: 0 !important;
    border-radius: 0 !important;

    display: flex !important;
    align-items: center !important;
    justify-content: center !important;

    font-size: clamp(3.0rem, 4.0vw, 3.6rem) !important;
    line-height: 1 !important;
    color: #e5e7eb !important;
    cursor: pointer;
}

div[data-testid="stHorizontalBlock"]:nth-of-type(1)
  div[data-testid="column"]:nth-of-type(-n+3)
  div[data-testid="stButton"] > button:hover,
div[data-testid="stHorizontalBlock"]:nth-of-type(1)
  div[data-testid="column"]:nth-of-type(-n+3)
  div[data-testid="stButton"] > button:focus,
div[data-testid="stHorizontalBlock"]:nth-of-type(1)
  div[data-testid="column"]:nth-of-type(-n+3)
  div[data-testid="stButton"] > button:focus-visible {
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
    outline: none !important;
    color: #60a5fa !important;
    transform: scale(1.08);
    transition: transform 0.15s ease;
}

div[data-testid="stFileUploader"] { margin-top: 8px !important; }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 3. 상단 네비게이션
# ==========================================
col_nav1, col_nav2, col_nav3, col_title, col_reset = st.columns(
    [1, 1, 1, 20, 3],
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

with st.container():
    if st.session_state['page'] == 'dashboard':
        st.markdown('<div class="hero-title">Mice Excel Data Cleaner Pro</div>', unsafe_allow_html=True)
        st.markdown('<div class="hero-subtitle">복잡한 명단 정리, AI 자동화로 단계별로 안전하게 처리하세요.</div>', unsafe_allow_html=True)
    elif st.session_state['page'] == 'qna':
        st.markdown('<div class="hero-title">💬 Q&A Board</div>', unsafe_allow_html=True)
        st.markdown('<div class="hero-subtitle">서비스 이용 중 궁금한 점이나 건의사항을 남겨주세요.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="hero-title" style="color:#94a3b8;">⚙️ Admin Settings</div>', unsafe_allow_html=True)
        st.markdown('<div class="hero-subtitle">관리자 전용 설정 페이지입니다.</div>', unsafe_allow_html=True)

with col_reset:
    if st.session_state['analyzed_data'] is not None and st.session_state['page'] == 'dashboard':
        if st.button("🔄 새 파일 분석", key="reset_btn_top", type="secondary", use_container_width=True):
            reset_analysis()

st.markdown("<div style='height:0px'></div>", unsafe_allow_html=True)


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

    def render_list(df_: pd.DataFrame):
        if df_.empty:
            st.info("등록된 게시글이 없습니다.")
            return

        for _, row in df_.iterrows():
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
            st.markdown("<br><br><h2 style='text-align:center;'>🔒 관리자 로그인</h2>", unsafe_allow_html=True)
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

        with tab_map:
            c_map = cleaner.load_mapping()
            df_map = pd.DataFrame(list(c_map.items()), columns=['입력', '변환'])
            edit = st.data_editor(
                df_map,
                num_rows="dynamic",
                use_container_width=True,
                height=500,
                hide_index=True
            )
            if st.button("규칙 저장", key="map_save", type="primary"):
                cleaner.save_mapping(dict(zip(edit['입력'], edit['변환'])))
                st.toast("저장됨!", icon="✅")

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

        with tab_sys:
            st.error("⚠️ 데이터 초기화")
            if st.button("전체 삭제", key="db_del"):
                database.clear_database()
                st.toast("삭제 완료", icon="💥")


# -------------------------------
# Dashboard 페이지
# -------------------------------
else:
    # 분석 전
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
                        st.session_state["pdf_assets"] = []
                        st.session_state["pdf_bytes"] = None
                        st.rerun()
                    else:
                        st.error(msg)
                except Exception as e:
                    st.error(f"Error: {e}")

    # 분석 후
    else:
        data = st.session_state['analyzed_data']
        cleaned_data = data['cleaned_data']
        trash_data = data['trash_data']
        excel_buffer = data['excel_buffer']
        filename = data['filename']

        t_clean = sum(len(df_) for df_ in cleaned_data.values())
        t_trash = sum(len(df_) for df_ in trash_data) if trash_data else 0

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
            stats = {'total_rows': t_clean + t_trash, 'removed_rows': t_trash, 'missing_info_rows': 0}
            f_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'NanumGothic.ttf')

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
        t1, t2, t3 = st.tabs(["📊 인사이트 & 필터", "🗑️ 휴지통 (복구)", "💾 DB 히스토리"])

        # =====================================================
        # Tab 1: 인사이트 & 필터  (⭐️ 순서 고정 핵심 영역)
        # =====================================================
        with t1:
            if cleaned_data:
                pdf_assets_reset()

                c_sel1, c_sel2 = st.columns([1, 4])
                with c_sel1:
                    sh = st.selectbox("분석 시트", list(cleaned_data.keys()), key="sheet_select")

                if st.session_state['current_sheet'] != sh:
                    st.session_state['current_sheet'] = sh
                    st.session_state['mail_df'] = None
                    st.session_state["pdf_bytes"] = None

                df = cleaned_data[sh]

                with st.expander("🔍 상세 검색", expanded=False):
                    cols = st.multiselect("필터 컬럼", df.columns, key="filter_cols")
                    conds = {c: st.text_input(f"'{c}' 검색", key=f"cond_{c}") for c in cols}
                    view_df = df.copy()
                    for c, val in conds.items():
                        if val:
                            view_df = view_df[view_df[c].astype(str).str.contains(val, case=False, na=False)]
                display_df = st.session_state['mail_df'] if st.session_state['mail_df'] is not None else view_df

                # -------------------------------------------------
                # (1) 만족도 & 리뷰 분석  ✅✅✅ 가장 먼저!
                # -------------------------------------------------
                st.markdown("---")
                st.subheader("📊 만족도 및 리뷰 분석")

                rating_cols = [
                    c for c in display_df.columns
                    if any(k in str(c).lower() for k in ['평점', 'rating', 'score', '점수', 'nps', 'satisfaction', '만족도'])
                ]
                review_cols = [
                    c for c in display_df.columns
                    if any(k in str(c).lower() for k in ['리뷰', 'review', 'comment', 'comments', '의견', '코멘트', '후기'])
                ]

                if not rating_cols and not review_cols:
                    st.info("평점/리뷰 컬럼을 찾지 못했습니다. (컬럼명에 '평점' 또는 '리뷰'가 포함되어야 자동 분석됩니다.)")

                # 1) 평점 분포 & NPS
                if rating_cols:
                    rating_col = rating_cols[0]

                    try:
                        scores = pd.to_numeric(display_df[rating_col], errors='coerce').dropna()
                        if not scores.empty:
                            promoters = len(scores[scores >= 9])
                            neutrals = len(scores[(scores >= 7) & (scores <= 8)])
                            detractors = len(scores[scores <= 6])
                            total_res = len(scores)
                            nps = ((promoters - detractors) / total_res) * 100

                            m1, m2, m3 = st.columns(3)
                            with m1:
                                st.markdown(f"""
                                <div class="kpi-card" style="padding: 15px;">
                                    <div class="kpi-title">😊 긍정 고객 (9-10점)</div>
                                    <div class="kpi-value val-clean" style="font-size: 2.5rem;">{promoters:,}명</div>
                                    <div class="kpi-delta">{promoters/total_res*100:.1f}%</div>
                                </div>""", unsafe_allow_html=True)
                            with m2:
                                st.markdown(f"""
                                <div class="kpi-card" style="padding: 15px;">
                                    <div class="kpi-title">😐 중립 고객 (7-8점)</div>
                                    <div class="kpi-value" style="font-size: 2.5rem; color: #cbd5e1;">{neutrals:,}명</div>
                                    <div class="kpi-delta" style="color: #64748b;">{neutrals/total_res*100:.1f}%</div>
                                </div>""", unsafe_allow_html=True)
                            with m3:
                                st.markdown(f"""
                                <div class="kpi-card" style="padding: 15px;">
                                    <div class="kpi-title">😡 부정 고객 (0-6점)</div>
                                    <div class="kpi-value val-trash" style="font-size: 2.5rem;">{detractors:,}명</div>
                                    <div class="kpi-delta">NPS: {nps:.1f}</div>
                                </div>""", unsafe_allow_html=True)
                    except Exception as e:
                        st.warning(f"점수 계산 중 오류: {e}")

                    fig_hist = px.histogram(
                        display_df, x=rating_col, nbins=11,
                        title=f"📈 {rating_col} 분포 (0~10점)",
                        template="plotly_dark",
                    )
                    fig_hist.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis_title="평점",
                        yaxis_title="인원 수",
                        bargap=0.1
                    )
                    st.plotly_chart(fig_hist, use_container_width=True, key=f"hist_{sh}_{rating_col}")
                    pdf_add_plotly(fig_hist, f"{sh} - {rating_col} 분포(히스토그램)")

                # 2) 리뷰 키워드 분석
                if review_cols:
                    review_col = review_cols[0]
                    st.markdown("---")
                    st.subheader(f"🗣️ '{review_col}' 키워드 분석")

                    text_list = display_df[review_col].dropna().astype(str).tolist()
                    full_text_all = " ".join(text_list)

                    wc_col, bar_col = st.columns(2)

                    with wc_col:
                        st.write("###### ☁️ 워드 클라우드")
                        if WordCloud is None or plt is None:
                            st.info("wordcloud 또는 matplotlib이 설치되어 있지 않습니다.")
                        else:
                            try:
                                font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'NanumGothic.ttf')
                                if os.path.exists(font_path) and full_text_all.strip():
                                    wc = WordCloud(
                                        font_path=font_path, width=600, height=400,
                                        background_color='#0f1117', colormap='cool'
                                    ).generate(full_text_all)
                                    fig, ax = plt.subplots(figsize=(8, 5))
                                    ax.imshow(wc, interpolation='bilinear')
                                    ax.axis('off')
                                    fig.patch.set_facecolor('#0f1117')
                                    st.pyplot(fig)
                                    pdf_add_mpl(fig, f"{sh} - 워드클라우드({review_col})")
                                else:
                                    st.warning("텍스트가 없거나 폰트 파일이 없습니다.")
                            except Exception as e:
                                st.warning(f"워드클라우드 생성 실패: {e}")

                    with bar_col:
                        st.write("###### 🧠 평점별 핵심 키워드 (불용어 제거)")

                        if rating_cols:
                            target_rating_col = rating_cols[0]
                            try:
                                try:
                                    from kiwipiepy import Kiwi
                                    kiwi = Kiwi()
                                    has_kiwi = True
                                except Exception:
                                    has_kiwi = False

                                STOPWORDS = {
                                    '행사','참가','진짜','정말','너무','매우','역시','부분','관련','내용',
                                    '시간','사람','생각','정도','참석','진행','운영','전반','개최',
                                    'great','good','event','session','conference','meeting'
                                }

                                def get_sentiment(score):
                                    try:
                                        s = float(score)
                                        if s >= 9: return "1. 긍정(9-10점)"
                                        elif s >= 7: return "2. 중립(7-8점)"
                                        else: return "3. 부정(0-6점)"
                                    except Exception:
                                        return "4. 기타"

                                sent_df = display_df[[target_rating_col, review_col]].dropna().copy()
                                sent_df['Sentiment'] = sent_df[target_rating_col].apply(get_sentiment)

                                all_keywords = []
                                for sentiment in ['1. 긍정(9-10점)', '2. 중립(7-8점)', '3. 부정(0-6점)']:
                                    texts = sent_df[sent_df['Sentiment'] == sentiment][review_col].astype(str).tolist()
                                    full_text = " ".join(texts)
                                    if not full_text.strip():
                                        continue

                                    words = []
                                    if has_kiwi:
                                        tokens = kiwi.tokenize(full_text)
                                        words = [
                                            t.form for t in tokens
                                            if t.tag in ['NNG','NNP','SL']
                                            and len(t.form) > 1
                                            and t.form.lower() not in STOPWORDS
                                        ]
                                    else:
                                        raw_words = full_text.split()
                                        for w in raw_words:
                                            clean_w = re.sub(r'[^\w]', '', w)
                                            if len(clean_w) > 1 and clean_w.lower() not in STOPWORDS:
                                                words.append(clean_w)

                                    if words:
                                        common = Counter(words).most_common(15)
                                        for word, count in common:
                                            all_keywords.append({'Sentiment': sentiment, 'Word': word, 'Count': count})

                                if all_keywords:
                                    df_treemap = pd.DataFrame(all_keywords)

                                    fig_tree = px.treemap(
                                        df_treemap,
                                        path=['Sentiment','Word'],
                                        values='Count',
                                        color='Sentiment'
                                    )
                                    fig_tree.update_layout(
                                        paper_bgcolor="rgba(0,0,0,0)",
                                        plot_bgcolor="rgba(0,0,0,0)",
                                        font=dict(family="Pretendard", size=14),
                                        margin=dict(t=20, l=0, r=0, b=0)
                                    )
                                    fig_tree.data[0].textinfo = "label+value"
                                    st.plotly_chart(fig_tree, use_container_width=True, key=f"tree_{sh}_{review_col}")
                                    pdf_add_plotly(fig_tree, f"{sh} - 평점별 핵심키워드(Treemap)")
                                    pdf_add_table(df_treemap, f"{sh} - 키워드 요약표", head=80)
                                else:
                                    st.info("유의미한 키워드를 찾지 못했습니다.")
                            except Exception as e:
                                st.error(f"분석 중 오류: {e}")
                        else:
                            st.info("평점 데이터가 없어 평점별 분류는 생략됩니다.")

                # -------------------------------------------------
                # (2) 등록일 분석 ✅ 만족도/리뷰 다음!
                # -------------------------------------------------
                render_registration_charts(display_df, sheet_name=sh)

                # -------------------------------------------------
                # (3) 메일/문자 템플릿
                # -------------------------------------------------
                with st.expander("📧 메일/문자 템플릿 & 발송", expanded=False):
                    st.info(f"사용 가능 변수: {', '.join([f'{{{c}}}' for c in df.columns])}")
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
                        tmpl = st.text_area("템플릿 내용", default_msg, height=200, key="tmpl_text")
                        if st.button("템플릿 적용 (표에 추가)", key="apply_tmpl"):
                            try:
                                view_df2 = cleaner.generate_message_column(view_df, tmpl)
                                st.session_state['mail_df'] = view_df2
                                st.success("생성 완료! (아래 표 확인)")
                                st.rerun()
                            except Exception as e:
                                st.error(f"생성 실패: {e}")

                    display_df2 = st.session_state['mail_df'] if st.session_state['mail_df'] is not None else view_df

                    with c_mail:
                        st.write("###### 🚀 이메일 발송 (SMTP)")
                        smtp_host = st.text_input("SMTP 서버", "smtp.gmail.com", key="smtp_host")
                        smtp_port = st.number_input("포트", value=465, key="smtp_port")
                        st.markdown("*보내는 메일 주소 (예: `myname@gmail.com`)*")
                        sender_email = st.text_input("보내는 메일", label_visibility="collapsed", key="sender_email")
                        st.markdown("*앱 비밀번호 (일반 비밀번호 아님!)*")
                        sender_pw = st.text_input("앱 비밀번호", type="password", label_visibility="collapsed", key="sender_pw")
                        mail_subject = st.text_input("메일 제목", "[MICE 2025] 등록 안내", key="mail_subject")

                        mail_cols = [c for c in display_df2.columns if '이메일' in str(c) or 'email' in str(c).lower()]
                        idx = list(display_df2.columns).index(mail_cols[0]) if mail_cols else 0
                        target_email_col = st.selectbox("받는 사람 이메일 컬럼", display_df2.columns, index=idx, key="target_email_col")

                        st.markdown("---")
                        st.write("###### 🧪 테스트 발송")
                        test_receiver = st.text_input("테스트 받는 사람 이메일", placeholder="me@example.com", key="test_receiver")

                        if st.button("테스트 발송 (1건만)", key="test_mail_btn"):
                            if not test_receiver:
                                st.warning("테스트 이메일을 입력하세요.")
                            elif '생성된_메시지' not in display_df2.columns:
                                st.error("먼저 템플릿을 적용해주세요.")
                            else:
                                test_df = display_df2.head(1).copy().reset_index(drop=True)
                                test_df[target_email_col] = test_receiver
                                suc, s_cnt, f_cnt, logs = mailer.send_bulk_emails(
                                    test_df, sender_email, sender_pw,
                                    target_email_col, mail_subject,
                                    '생성된_메시지',
                                    smtp_host, smtp_port
                                )
                                if suc:
                                    st.success(f"테스트 발송 성공! ({test_receiver})")
                                else:
                                    st.error(f"실패: {logs[0] if logs else 'Unknown'}")

                        st.markdown("---")
                        if st.button("전체 발송 시작 (주의)", type="primary", key="send_mail_real"):
                            if '생성된_메시지' not in display_df2.columns:
                                st.error("먼저 '템플릿 적용' 버튼을 눌러 메시지를 생성해주세요.")
                            elif not sender_email or not sender_pw:
                                st.error("이메일 계정 정보를 입력해주세요.")
                            else:
                                send_df = display_df2.reset_index(drop=True)
                                suc, s_cnt, f_cnt, logs = mailer.send_bulk_emails(
                                    send_df, sender_email, sender_pw,
                                    target_email_col, mail_subject,
                                    '생성된_메시지',
                                    smtp_host, smtp_port
                                )
                                if suc:
                                    st.success(f"발송 완료! (성공: {s_cnt}, 실패: {f_cnt})")
                                else:
                                    st.error(f"발송 실패: {logs[0] if logs else 'Unknown'}")

                # -------------------------------------------------
                # (4) 주요 인사이트 대시보드
                # -------------------------------------------------
                st.markdown("---")
                st.markdown("#### 📊 인사이트 대시보드")

                if not display_df.empty:
                    excluded_keywords = [
                        '이름', 'name', '이메일', 'email', 'phone',
                        '전화', '비고', 'check', 'no', '메시지',
                        '리뷰', 'review', 'comment', '의견', '코멘트',
                        '평점', 'rating', 'score', '점수'
                    ]
                    potential = [c for c in display_df.columns if not any(k in str(c).lower() for k in excluded_keywords)]

                    if potential:
                        st.markdown(f"##### 📈 **{sh}** 주요 대시보드")
                        cols_ui = st.columns(2)
                        for i, col_name in enumerate(potential[:6]):
                            with cols_ui[i % 2]:
                                c_data = display_df[col_name].fillna('미입력').value_counts().reset_index()
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
                                    fig.update_traces(textposition='inside', textinfo='percent+label')
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
                                st.plotly_chart(fig, use_container_width=True, key=f"ins_{sh}_{col_name}_{i}")
                                pdf_add_plotly(fig, f"{sh} - 인사이트({col_name})")
                    else:
                        st.info("대시보드를 만들 수 있는 적절한 컬럼이 없습니다.")

                    # -------------------------------------------------
                    # (5) 상세 데이터 테이블
                    # -------------------------------------------------
                    st.markdown("---")
                    st.markdown("#### 📋 상세 데이터")
                    st.dataframe(display_df, use_container_width=True, hide_index=True, height=500)
                    pdf_add_table(display_df, f"{sh} - 상세 데이터", head=80)
                else:
                    st.warning("데이터 없음")

        # -------------------------------
        # Tab 2: 휴지통 (복구)
        # -------------------------------
        with t2:
            if trash_data:
                full_trash = pd.concat(trash_data)
                sheets = full_trash['[원본시트]'].unique()
                sel = st.selectbox("확인할 시트", sheets, key="trash_sheet")
                subset = full_trash[full_trash['[원본시트]'] == sel].dropna(axis=1, how='all')
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
                    to_restore = edited_trash[edited_trash['선택'] == True]
                    if not to_restore.empty:
                        rows = to_restore.drop(columns=['선택'])
                        if '[원본시트]' in rows.columns:
                            rows = rows.drop(columns=['[원본시트]'])
                        cur = st.session_state['analyzed_data']['cleaned_data'][sel]
                        st.session_state['analyzed_data']['cleaned_data'][sel] = pd.concat(
                            [cur, rows], ignore_index=True
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