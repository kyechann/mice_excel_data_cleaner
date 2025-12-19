import streamlit as st
import pandas as pd
import plotly.express as px
import os
import re
from collections import Counter

from core.pdf_assets import pdf_add_plotly, pdf_add_mpl, pdf_add_table

try:
    from wordcloud import WordCloud
    import matplotlib.pyplot as plt
except ImportError:
    WordCloud = None
    plt = None

def render_satisfaction_and_review(display_df: pd.DataFrame, sheet_name: str):
    """
    ✅ 이 섹션은 "제목 -> KPI/차트/분석"이 한 블록으로 붙어서 나오게 구성.
    ✅ 여기서만 만족도/리뷰 분석을 그리고, 밖에서 중복 호출하지 않도록.
    """
    st.markdown("---")
    st.subheader("📊 만족도 및 리뷰 분석")

    rating_cols = [
        c for c in display_df.columns
        if any(k in str(c).lower() for k in ["평점", "rating", "score", "점수", "nps", "satisfaction", "만족도"])
    ]
    review_cols = [
        c for c in display_df.columns
        if any(k in str(c).lower() for k in ["리뷰", "review", "comment", "comments", "의견", "코멘트", "후기"])
    ]

    if not rating_cols and not review_cols:
        st.info("평점/리뷰 컬럼을 찾지 못했습니다. (컬럼명에 '평점' 또는 '리뷰'가 포함되어야 자동 분석됩니다.)")
        return

    # ---------------------------
    # 1) 평점 분석
    # ---------------------------
    if rating_cols:
        rating_col = rating_cols[0]
        st.markdown("---")
        st.subheader("📊 만족도 분석")

        try:
            scores = pd.to_numeric(display_df[rating_col], errors="coerce").dropna()
            if not scores.empty:
                promoters = len(scores[scores >= 9])
                neutrals = len(scores[(scores >= 7) & (scores <= 8)])
                detractors = len(scores[scores <= 6])
                total_res = len(scores)
                nps = ((promoters - detractors) / total_res) * 100

                m1, m2, m3 = st.columns(3)
                with m1:
                    st.markdown(
                        f"""
                        <div class="kpi-card" style="padding: 15px;">
                            <div class="kpi-title">😊 긍정 고객 (9-10점)</div>
                            <div class="kpi-value val-clean" style="font-size: 2.5rem;">{promoters:,}명</div>
                            <div class="kpi-delta">{promoters/total_res*100:.1f}%</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with m2:
                    st.markdown(
                        f"""
                        <div class="kpi-card" style="padding: 15px;">
                            <div class="kpi-title">😐 중립 고객 (7-8점)</div>
                            <div class="kpi-value" style="font-size: 2.5rem; color: #cbd5e1;">{neutrals:,}명</div>
                            <div class="kpi-delta" style="color: #64748b;">{neutrals/total_res*100:.1f}%</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with m3:
                    st.markdown(
                        f"""
                        <div class="kpi-card" style="padding: 15px;">
                            <div class="kpi-title">😡 부정 고객 (0-6점)</div>
                            <div class="kpi-value val-trash" style="font-size: 2.5rem;">{detractors:,}명</div>
                            <div class="kpi-delta">NPS: {nps:.1f}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        except Exception as e:
            st.warning(f"점수 계산 중 오류: {e}")

        fig_hist = px.histogram(
            display_df, x=rating_col, nbins=11,
            title=f"📈 {rating_col} 분포 (0~10점)",
            template="plotly_dark",
            color_discrete_sequence=["#6366f1"]
        )
        fig_hist.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="평점",
            yaxis_title="인원 수",
            bargap=0.1
        )
        st.plotly_chart(fig_hist, use_container_width=True)
        pdf_add_plotly(fig_hist, f"{sheet_name} - {rating_col} 분포(히스토그램)")

    # ---------------------------
    # 2) 리뷰 텍스트 분석
    # ---------------------------
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
                    font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts", "NanumGothic.ttf")
                    font_path = os.path.abspath(font_path)

                    if os.path.exists(font_path) and full_text_all.strip():
                        wc = WordCloud(
                            font_path=font_path, width=600, height=400,
                            background_color="#0f1117", colormap="cool"
                        ).generate(full_text_all)

                        fig, ax = plt.subplots(figsize=(8, 5))
                        ax.imshow(wc, interpolation="bilinear")
                        ax.axis("off")
                        fig.patch.set_facecolor("#0f1117")
                        st.pyplot(fig)

                        pdf_add_mpl(fig, f"{sheet_name} - 워드클라우드({review_col})")
                    else:
                        st.warning("텍스트가 없거나 폰트 파일이 없습니다.")
                except Exception as e:
                    st.warning(f"워드클라우드 생성 실패: {e}")

        with bar_col:
            st.write("###### 🧠 평점별 핵심 키워드 (불용어 제거)")

            # 평점 컬럼이 있으면 평점별로, 없으면 전체 빈도만
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
                        "행사","참가","진짜","정말","너무","매우","역시","부분","관련","내용",
                        "시간","사람","생각","정도","참석","진행","운영","전반","개최",
                        "great","good","event","session","conference","meeting"
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
                    sent_df["Sentiment"] = sent_df[target_rating_col].apply(get_sentiment)

                    all_keywords = []
                    for sentiment in ["1. 긍정(9-10점)", "2. 중립(7-8점)", "3. 부정(0-6점)"]:
                        texts = sent_df[sent_df["Sentiment"] == sentiment][review_col].astype(str).tolist()
                        full_text = " ".join(texts)
                        if not full_text.strip():
                            continue

                        words = []
                        if has_kiwi:
                            tokens = kiwi.tokenize(full_text)
                            words = [
                                t.form for t in tokens
                                if t.tag in ["NNG","NNP","SL"]
                                and len(t.form) > 1
                                and t.form.lower() not in STOPWORDS
                            ]
                        else:
                            raw_words = full_text.split()
                            for w in raw_words:
                                clean_w = re.sub(r"[^\w]", "", w)
                                if len(clean_w) > 1 and clean_w.lower() not in STOPWORDS:
                                    words.append(clean_w)

                        if words:
                            common = Counter(words).most_common(15)
                            for word, count in common:
                                all_keywords.append({"Sentiment": sentiment, "Word": word, "Count": count})

                    if all_keywords:
                        df_treemap = pd.DataFrame(all_keywords)

                        fig_tree = px.treemap(
                            df_treemap,
                            path=["Sentiment", "Word"],
                            values="Count",
                            color="Sentiment",
                            color_discrete_map={
                                "1. 긍정(9-10점)": "#6366f1",
                                "2. 중립(7-8점)": "#94a3b8",
                                "3. 부정(0-6점)": "#ef4444",
                            },
                        )
                        fig_tree.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(family="Pretendard", size=14),
                            margin=dict(t=20, l=0, r=0, b=0),
                        )
                        if fig_tree.data and len(fig_tree.data) > 0:
                            fig_tree.data[0].textinfo = "label+value"

                        st.plotly_chart(fig_tree, use_container_width=True)

                        pdf_add_plotly(fig_tree, f"{sheet_name} - 평점별 핵심키워드(Treemap)")
                        pdf_add_table(df_treemap, f"{sheet_name} - 키워드 요약표", head=80)
                    else:
                        st.info("유의미한 키워드를 찾지 못했습니다.")

                except Exception as e:
                    st.error(f"분석 중 오류: {e}")

            else:
                # 평점이 없으면 전체 키워드 빈도만 간단히
                words = [re.sub(r"[^\w]", "", w) for w in full_text_all.split()]
                words = [w for w in words if len(w) > 1]
                common = Counter(words).most_common(20)
                if common:
                    df_common = pd.DataFrame(common, columns=["Word", "Count"])
                    fig_bar = px.bar(df_common, x="Word", y="Count", title="🧾 리뷰 키워드 TOP 20", template="plotly_dark")
                    fig_bar.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis_tickangle=-45
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)
                    pdf_add_plotly(fig_bar, f"{sheet_name} - 리뷰 키워드 TOP20")
                    pdf_add_table(df_common, f"{sheet_name} - 리뷰 키워드 표", head=80)
                else:
                    st.info("리뷰 텍스트가 부족합니다.")