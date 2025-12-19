import streamlit as st
import pandas as pd
from modules import reporter

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