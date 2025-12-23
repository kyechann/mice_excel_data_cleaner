import streamlit as st
import pandas as pd
import plotly.express as px
from core.pdf_assets import pdf_add_plotly

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

    # =========================
    # 1) 등록 추이(일/주) + 누적
    # =========================
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

    fig_trend.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=380,
    )

    daily_sorted = daily.sort_values("등록일").copy()
    daily_sorted["Cumulative"] = daily_sorted["Count"].cumsum()
    fig_cum = px.area(
        daily_sorted, x="등록일", y="Cumulative",
        title="📈 누적 등록 수", template="plotly_dark"
    )
    fig_cum.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=380,
    )

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.plotly_chart(fig_trend, use_container_width=True)
        pdf_add_plotly(fig_trend, f"{sheet_name} - 등록 추이")
    with c2:
        st.plotly_chart(fig_cum, use_container_width=True)
        pdf_add_plotly(fig_cum, f"{sheet_name} - 누적 등록")

    # =========================
    # 2) 참가구분별 월별(있으면) + 히트맵(월×요일)  ✅ 이 줄이 네가 원한 “그래프 2열”
    # =========================
    fig_stack = None
    type_col = "참가구분" if "참가구분" in tmp.columns else None
    if type_col:
        tmp_stack = tmp.copy()
        tmp_stack["등록월"] = tmp_stack[date_col].dt.to_period("M").astype(str)
        g = tmp_stack.groupby(["등록월", type_col]).size().reset_index(name="Count")
        fig_stack = px.bar(
            g, x="등록월", y="Count", color=type_col,
            title="📊 참가구분별 등록 (월별)", template="plotly_dark"
        )
        fig_stack.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis_tickangle=-45,
            height=420,
        )

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
    fig_heat.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=420,
    )

    if fig_stack is not None:
        c3, c4 = st.columns(2, gap="large")
        with c3:
            st.plotly_chart(fig_stack, use_container_width=True)
            pdf_add_plotly(fig_stack, f"{sheet_name} - 참가구분별 월별 등록")
        with c4:
            st.plotly_chart(fig_heat, use_container_width=True)
            pdf_add_plotly(fig_heat, f"{sheet_name} - 등록 히트맵(월×요일)")
    else:
        # 참가구분이 없으면 히트맵만 전체폭
        st.plotly_chart(fig_heat, use_container_width=True)
        pdf_add_plotly(fig_heat, f"{sheet_name} - 등록 히트맵(월×요일)")
                       
def build_registration_figs(display_df: pd.DataFrame):
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
        return {}

    tmp = display_df.copy()
    tmp[date_col] = pd.to_datetime(tmp[date_col], errors="coerce")
    tmp = tmp.dropna(subset=[date_col])
    if tmp.empty:
        return {}

    daily = tmp.groupby(tmp[date_col].dt.date).size().reset_index(name="Count")
    daily.columns = ["등록일", "Count"]
    daily["등록일"] = pd.to_datetime(daily["등록일"])

    if len(daily) > 120:
        weekly = daily.set_index("등록일").resample("W-MON")["Count"].sum().reset_index()
        fig_trend = px.line(weekly, x="등록일", y="Count", markers=True, title="📈 등록 추이 (주별)", template="plotly_dark")
    else:
        fig_trend = px.line(daily, x="등록일", y="Count", markers=True, title="📈 등록 추이 (일별)", template="plotly_dark")

    fig_trend.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=380)

    daily_sorted = daily.sort_values("등록일").copy()
    daily_sorted["Cumulative"] = daily_sorted["Count"].cumsum()
    fig_cum = px.area(daily_sorted, x="등록일", y="Cumulative", title="📈 누적 등록 수", template="plotly_dark")
    fig_cum.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=380)

    fig_stack = None
    type_col = "참가구분" if "참가구분" in tmp.columns else None
    if type_col:
        tmp_stack = tmp.copy()
        tmp_stack["등록월"] = tmp_stack[date_col].dt.to_period("M").astype(str)
        g = tmp_stack.groupby(["등록월", type_col]).size().reset_index(name="Count")
        fig_stack = px.bar(g, x="등록월", y="Count", color=type_col, title="📊 참가구분별 등록 (월별)", template="plotly_dark")
        fig_stack.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_tickangle=-45, height=420)

    tmp2 = tmp.copy()
    tmp2["등록월"] = tmp2[date_col].dt.to_period("M").astype(str)
    tmp2["요일"] = tmp2[date_col].dt.day_name()
    dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    tmp2["요일"] = pd.Categorical(tmp2["요일"], categories=dow_order, ordered=True)

    heat = tmp2.groupby(["요일", "등록월"]).size().reset_index(name="Count")
    heat_pivot = heat.pivot(index="요일", columns="등록월", values="Count").fillna(0)

    fig_heat = px.imshow(heat_pivot, aspect="auto", title="🗓️ 등록 패턴 히트맵 (월 × 요일)", template="plotly_dark")
    fig_heat.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=420)

    return {"trend": fig_trend, "cum": fig_cum, "stack": fig_stack, "heat": fig_heat}