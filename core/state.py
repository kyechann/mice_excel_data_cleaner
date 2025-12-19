import streamlit as st

def init_session_state():
    defaults = {
        "page": "dashboard",
        "analyzed_data": None,
        "admin_logged_in": False,
        "mail_df": None,
        "current_sheet": None,
        "pdf_assets": [],
        "pdf_bytes": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def navigate_to(page: str):
    st.session_state["page"] = page
    st.rerun()

def reset_analysis():
    st.session_state["analyzed_data"] = None
    st.session_state["mail_df"] = None
    st.session_state["current_sheet"] = None
    st.session_state["pdf_assets"] = []
    st.session_state["pdf_bytes"] = None
    st.rerun()

def logout():
    st.session_state["admin_logged_in"] = False
    st.toast("로그아웃 되었습니다.", icon="👋")
    navigate_to("dashboard")