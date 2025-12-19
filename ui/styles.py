import streamlit as st

def apply_global_styles():
    st.markdown(
        """
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
        """,
        unsafe_allow_html=True
    )