import streamlit as st
import pandas as pd
import plotly.express as px

from core.pdf_assets import pdf_add_plotly

def render_satisfaction_and_review(display_df: pd.DataFrame, sheet_name: str):
    BLUE  = "#3b82f6"
    GREEN = "#22c55e"
    RED   = "#ef4444"
    st.markdown("---")
    st.subheader("📊 만족도 및 리뷰 분석")

    rating_cols = [
        c for c in display_df.columns
        if any(k in str(c).lower() for k in ["평점", "rating", "score", "점수", "nps", "satisfaction", "만족도"])
    ]
    if not rating_cols:
        st.info("평점/만족도 컬럼을 찾지 못했습니다.")
        return

    rating_col = rating_cols[0]
    scores = pd.to_numeric(display_df[rating_col], errors="coerce").dropna()
    if scores.empty:
        st.info("평점 데이터가 비어있습니다.")
        return

    promoters = int((scores >= 9).sum())
    neutrals  = int(((scores >= 7) & (scores <= 8)).sum())
    detractors = int((scores <= 6).sum())

    total_res = len(scores)
    nps = ((promoters - detractors) / total_res) * 100

    m1, m2, m3 = st.columns(3)

    with m1:
        st.markdown(
            f"""
            <div class="kpi-card" style="padding: 15px;">
                <div class="kpi-title" style="color:{BLUE}; font-weight:700;">😊 긍정(9-10점)</div>
                <div class="kpi-value" style="font-size:2.3rem; color:{BLUE}; font-weight:800;">{promoters:,}명</div>
                <div class="kpi-delta" style="color:{BLUE}; opacity:0.85;">{promoters/total_res*100:.1f}%</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with m2:
        st.markdown(
            f"""
            <div class="kpi-card" style="padding: 15px;">
                <div class="kpi-title" style="color:{GREEN}; font-weight:700;">😐 중립(7-8점)</div>
                <div class="kpi-value" style="font-size:2.3rem; color:{GREEN}; font-weight:800;">{neutrals:,}명</div>
                <div class="kpi-delta" style="color:{GREEN}; opacity:0.85;">{neutrals/total_res*100:.1f}%</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with m3:
        st.markdown(
            f"""
            <div class="kpi-card" style="padding: 15px;">
                <div class="kpi-title" style="color:{RED}; font-weight:700;">😡 부정(0-6점)</div>
                <div class="kpi-value" style="font-size:2.3rem; color:{RED}; font-weight:800;">{detractors:,}명</div>
                <div class="kpi-delta" style="color:{RED}; opacity:0.9;">NPS: {nps:.1f}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    fig_hist = px.histogram(
        display_df, x=rating_col, nbins=11,
        title=f"📈 {rating_col} 분포 (0~10점)",
        template="plotly_dark",
    )
    fig_hist.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_hist, use_container_width=True)
    pdf_add_plotly(fig_hist, f"{sheet_name} - {rating_col} 분포")