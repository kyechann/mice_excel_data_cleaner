import streamlit as st
import plotly.express as px
from core.pdf_assets import pdf_add_plotly, pdf_add_table

def render_insights_dashboard(display_df, sheet_name: str):
    st.markdown("---")
    st.markdown("#### 📊 인사이트 대시보드")

    if display_df.empty:
        st.warning("데이터 없음")
        return

    excluded_keywords = [
        "이름", "name", "이메일", "email", "phone",
        "전화", "비고", "check", "no", "메시지",
        "리뷰", "review", "comment", "의견", "코멘트",
        "평점", "rating", "score", "점수"
    ]
    potential = [c for c in display_df.columns if not any(k in str(c).lower() for k in excluded_keywords)]

    if not potential:
        st.info("대시보드를 만들 수 있는 적절한 컬럼이 없습니다.")
        return

    st.markdown(f"##### 📈 **{sheet_name}** 주요 대시보드")
    cols_ui = st.columns(2)

    for i, col_name in enumerate(potential[:6]):
        with cols_ui[i % 2]:
            c_data = display_df[col_name].fillna("미입력").value_counts().reset_index()
            c_data.columns = [col_name, "Count"]

            if len(c_data) <= 5:
                fig = px.pie(
                    c_data,
                    values="Count",
                    names=col_name,
                    title=f"{col_name} 비율",
                    hole=0.3,
                    template="plotly_dark",
                )
                fig.update_traces(textposition="inside", textinfo="percent+label")
            else:
                top = c_data.head(10)
                fig = px.bar(
                    top,
                    x=col_name,
                    y="Count",
                    title=f"{col_name} TOP 10",
                    text="Count",
                    template="plotly_dark",
                )
                fig.update_layout(xaxis_tickangle=-45)

            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)
            pdf_add_plotly(fig, f"{sheet_name} - 인사이트({col_name})")

    st.markdown("---")
    st.markdown("#### 📋 상세 데이터")
    st.dataframe(display_df, use_container_width=True, hide_index=True, height=500)
    pdf_add_table(display_df, f"{sheet_name} - 상세 데이터", head=80)