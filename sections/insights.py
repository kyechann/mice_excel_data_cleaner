# sections/insights.py
import re
import plotly.express as px


def _safe_key(s: str) -> str:
    s = str(s).strip().lower()
    s = re.sub(r"[^a-z0-9가-힣_]+", "_", s)
    return s[:50]

def build_insight_figs(display_df, sheet_name: str, max_cols: int = 6):
    if display_df.empty:
        return {}

    excluded_keywords = [
        "이름", "name", "이메일", "email", "phone",
        "전화", "비고", "check", "no", "메시지",
        "리뷰", "review", "comment", "의견", "코멘트",
        "평점", "rating", "score", "점수"
    ]
    potential = [c for c in display_df.columns if not any(k in str(c).lower() for k in excluded_keywords)]
    if not potential:
        return {}

    figs = {}
    for col_name in potential[:max_cols]:
        c_data = display_df[col_name].fillna("미입력").value_counts().reset_index()
        c_data.columns = [col_name, "Count"]

        if len(c_data) <= 5:
            fig = px.pie(c_data, values="Count", names=col_name, title=f"{col_name} 비율", hole=0.3, template="plotly_dark")
            fig.update_traces(textposition="inside", textinfo="percent+label")
        else:
            top = c_data.head(10)
            fig = px.bar(top, x=col_name, y="Count", title=f"{col_name} TOP 10", text="Count", template="plotly_dark")
            fig.update_layout(xaxis_tickangle=-45)

        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=380,
        )

        key = f"ins_{_safe_key(col_name)}"
        figs[key] = {
            "title": f"인사이트: {col_name}",
            "fig": fig,
            "pdf_title": f"{sheet_name} - 인사이트({col_name})",
        }

    return figs

def render_detail_table(display_df, sheet_name: str):
    
    import streamlit as st
    from core.pdf_assets import pdf_add_table

    st.markdown("---")
    st.markdown("#### 📋 상세 데이터")
    st.dataframe(display_df, use_container_width=True, hide_index=True, height=650)
    pdf_add_table(display_df, f"{sheet_name} - 상세 데이터", head=80)