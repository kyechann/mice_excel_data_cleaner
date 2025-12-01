import streamlit as st
import pandas as pd
import io
import plotly.express as px
import time
from modules import cleaner, database, reporter
import os

# ==========================================
# 1. 페이지 설정 및 디자인 시스템
# ==========================================
st.set_page_config(page_title="Data Cleaner Pro", page_icon="💎", layout="wide")

# [핵심] 세션 상태 초기화 (데이터 유지용)
if 'page' not in st.session_state: st.session_state['page'] = 'dashboard'
if 'analyzed_data' not in st.session_state: st.session_state['analyzed_data'] = None

def navigate_to(page):
    st.session_state['page'] = page
    st.rerun()

def reset_analysis():
    st.session_state['analyzed_data'] = None
    st.rerun()

st.markdown("""
<style>
    @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.8/dist/web/static/pretendard.css");
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .stApp { background-color: #0f1117; }

    /* 네비게이션 버튼 */
    .nav-btn { width: 100%; border-radius: 8px; border: 1px solid #334155; background-color: #1e293b; color: white; font-weight: 600; margin-bottom: 10px; }
    
    /* KPI 카드 */
    .kpi-card { background-color: #1e2330; border: 1px solid #334155; border-radius: 16px; padding: 20px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .kpi-value { font-size: 3.5rem; font-weight: 800; margin: 0; line-height: 1.2; }
    
    .text-blue { color: #60a5fa; }
    .text-orange { color: #fb923c; }
    .text-purple { color: #c084fc; }
    
    /* 버튼 공통 */
    .stButton button, div[data-testid="stDownloadButton"] button { height: 50px !important; border-radius: 10px !important; font-weight: 700 !important; border: none !important; width: 100%; }
    button[kind="primary"] { background: linear-gradient(135deg, #4f46e5, #7c3aed) !important; color: white !important; }
    button[kind="secondary"] { background-color: #334155 !important; color: #f8fafc !important; border: 1px solid #475569 !important; }
    
    /* 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; border-bottom: 1px solid #334155; }
    .stTabs [data-baseweb="tab"] { height: 50px; background-color: transparent; border: none; color: #64748b; }
    .stTabs [aria-selected="true"] { background-color: #1e293b !important; color: #60a5fa !important; border-bottom: 2px solid #60a5fa !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 사이드바 (네비게이션)
# ==========================================
with st.sidebar:
    st.markdown("### 💎 Menu")
    
    if st.session_state['page'] == 'dashboard':
        st.info("현재: 🏠 대시보드")
        if st.button("⚙️ 관리자 설정 (매핑)", use_container_width=True):
            navigate_to('admin')
        
        # 데이터가 있을 때만 초기화 버튼 표시
        if st.session_state['analyzed_data'] is not None:
            st.markdown("---")
            if st.button("🔄 새 파일 분석하기 (초기화)", type="secondary", use_container_width=True):
                reset_analysis()

    else:
        st.warning("현재: ⚙️ 관리자 모드")
        if st.button("🏠 대시보드로 복귀", use_container_width=True):
            navigate_to('dashboard')
            
    st.markdown("---")
    st.caption("Data Cleaner Pro v8.1")

# ==========================================
# 3. 화면 라우팅
# ==========================================

# [PAGE 1] 관리자 설정 페이지
if st.session_state['page'] == 'admin':
    st.title("⚙️ 관리자 설정 (Admin Page)")
    col_set1, col_set2 = st.columns([2, 1])
    
    with col_set1:
        st.subheader("🧩 회사명 매핑 규칙 편집")
        current_map = cleaner.load_mapping()
        map_df = pd.DataFrame(list(current_map.items()), columns=['입력값(오타)', '변환값(정준)'])
        edit_df = st.data_editor(map_df, num_rows="dynamic", use_container_width=True, height=600, hide_index=True)
    
    with col_set2:
        st.subheader("💾 관리 도구")
        if st.button("✅ 규칙 저장하기", type="primary", use_container_width=True):
            new_map = dict(zip(edit_df['입력값(오타)'], edit_df['변환값(정준)']))
            cleaner.save_mapping(new_map)
            st.toast("저장되었습니다!", icon="🎉")
            
        st.markdown("---")
        with st.expander("⚠️ DB 초기화"):
            if st.button("🗑️ 모든 데이터 삭제", use_container_width=True):
                database.clear_database()
                st.toast("DB가 초기화되었습니다.", icon="💥")

# [PAGE 2] 메인 대시보드 페이지
else:
    st.markdown("""
        <h1 style='font-size: 3rem; margin-bottom:0;'>💎 Data Cleaner Pro</h1>
        <p style='color:#94a3b8; font-size:1.2rem; margin-bottom:30px;'>
            압도적인 속도, 완벽한 데이터 정제 솔루션
        </p>
    """, unsafe_allow_html=True)

    # 1. 파일 업로드 로직 (세션에 데이터가 없으면 표시)
    if st.session_state['analyzed_data'] is None:
        uploaded_file = st.file_uploader("분석할 엑셀 파일을 드래그하거나 선택하세요", type=['xlsx'])
        
        if uploaded_file:
            with st.spinner("⚡ AI 엔진 구동 중..."):
                try:
                    start_time = time.time()
                    excel_buffer, cleaned_data, trash_data, msg = cleaner.run_cleaning_pipeline(uploaded_file)
                    end_time = time.time()
                    
                    if msg == "Success":
                        # [핵심] 결과를 세션 상태에 저장 (페이지 이동해도 유지됨)
                        st.session_state['analyzed_data'] = {
                            'excel_buffer': excel_buffer,
                            'cleaned_data': cleaned_data,
                            'trash_data': trash_data,
                            'filename': uploaded_file.name,
                            'elapsed': f"{end_time - start_time:.2f}s"
                        }
                        st.rerun() # 새로고침하여 결과 화면으로 전환
                    else:
                        st.error(f"⚠️ 오류가 발생했습니다: {msg}")
                except Exception as e:
                    st.error(f"처리 중 예외 발생: {e}")

    # 2. 결과 대시보드 로직 (데이터가 있으면 표시)
    else:
        data = st.session_state['analyzed_data']
        cleaned_data = data['cleaned_data']
        trash_data = data['trash_data']
        excel_buffer = data['excel_buffer']
        filename = data['filename']
        
        # KPI 섹션
        total_clean = sum(len(df) for df in cleaned_data.values())
        total_trash = sum(len(df) for df in trash_data) if trash_data else 0
        
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(f"""<div class="kpi-card"><div class="kpi-title">✨ 정제된 데이터</div><div class="kpi-value text-blue">{total_clean:,}</div><div class="kpi-delta">Clean Rows</div></div>""", unsafe_allow_html=True)
        with c2: st.markdown(f"""<div class="kpi-card"><div class="kpi-title">🗑️ 중복 데이터</div><div class="kpi-value text-orange">{total_trash:,}</div><div class="kpi-delta">- Duplicates</div></div>""", unsafe_allow_html=True)
        with c3: st.markdown(f"""<div class="kpi-card"><div class="kpi-title">🚀 처리 속도</div><div class="kpi-value text-purple">{data['elapsed']}</div><div class="kpi-delta">Ultra Fast</div></div>""", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)

        # 컨트롤 패널
        st.subheader("🛠️ 작업 컨트롤 패널")
        with st.container():
            col_act1, col_act2, col_act3 = st.columns(3, gap="medium")
            
            with col_act1:
                # Spacer
                st.markdown('<div style="height: 29px;"></div>', unsafe_allow_html=True)
                mask_check = st.checkbox("🔒 마스킹 다운로드", value=True)
                
                final_buffer = excel_buffer
                if mask_check:
                    masked_dict = {k: cleaner.mask_personal_info(v) for k,v in cleaned_data.items()}
                    final_buffer = io.BytesIO()
                    with pd.ExcelWriter(final_buffer, engine='xlsxwriter') as w:
                        for k, v in masked_dict.items(): v.to_excel(w, sheet_name=k, index=False)
                
                st.download_button("💾 엑셀 다운로드", data=final_buffer.getvalue(), file_name=f"Cleaned_{filename}", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", use_container_width=True)

            with col_act2:
                st.markdown('<div style="height: 29px;"></div>', unsafe_allow_html=True)
                st.write("") # Spacer for checkbox alignment
                
                stats = {'total_rows': total_clean+total_trash, 'removed_rows': total_trash, 'missing_info_rows': 0}
                font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'NanumGothic.ttf')
                
                if st.button("📄 PDF 리포트 생성", use_container_width=True):
                    if not os.path.exists(font_path): st.error("폰트 없음")
                    else:
                        try:
                            pdf = reporter.create_pdf_report(stats, cleaned_data)
                            st.download_button("📥 PDF 받기", pdf, "report.pdf", "application/pdf", use_container_width=True)
                        except: st.error("실패")

            with col_act3:
                st.markdown('<div style="height: 29px;"></div>', unsafe_allow_html=True)
                st.write("") # Spacer
                if st.button("🗄️ DB에 저장하기", use_container_width=True):
                    suc, m = database.save_to_db(cleaned_data, filename)
                    if suc: st.toast("DB 저장 완료!", icon="✅")
                    else: st.error(m)

        st.markdown("---")
        
        # 탭 콘텐츠
        t1, t2, t3 = st.tabs(["📊 인사이트 & 필터", "🗑️ 휴지통 (중복)", "💾 DB 히스토리"])
        
        # [Tab 1] 대시보드
        with t1:
            if cleaned_data:
                c_sel1, c_sel2 = st.columns([1, 4])
                with c_sel1: sh = st.selectbox("분석 시트", list(cleaned_data.keys()))
                df = cleaned_data[sh]
                
                with st.expander("🔍 상세 검색 및 필터링", expanded=False):
                    cols = st.multiselect("필터 적용할 컬럼", df.columns)
                    conds = {c: st.text_input(f"'{c}' 키워드") for c in cols}
                    view_df = df.copy()
                    for c, val in conds.items():
                        if val: view_df = view_df[view_df[c].astype(str).str.contains(val, case=False)]
                
                if not view_df.empty:
                    potential_cols = []
                    exclude = ['이름', 'name', '이메일', 'email', 'phone', '전화', '비고', 'check', 'no']
                    for col in view_df.columns:
                        if any(k in str(col).lower() for k in exclude): continue
                        potential_cols.append(col)
                    
                    if potential_cols:
                        st.markdown(f"##### 📈 **{sh}** 시각화")
                        cols_ui = st.columns(2)
                        for i, col_name in enumerate(potential_cols):
                            with cols_ui[i % 2]:
                                chart_data = view_df[col_name].fillna('미입력').value_counts().reset_index()
                                chart_data.columns = [col_name, 'Count']
                                
                                if len(chart_data) <= 5:
                                    fig = px.pie(chart_data, values='Count', names=col_name, title=f"{col_name} 비율", hole=0.3, template="plotly_dark")
                                    fig.update_traces(textposition='inside', textinfo='percent+label')
                                else:
                                    # [수정] 세로 막대 그래프 (x=col_name, y='Count')
                                    top_data = chart_data.head(10)
                                    fig = px.bar(
                                        top_data, 
                                        x=col_name, 
                                        y='Count', 
                                        title=f"{col_name} TOP 10", 
                                        text='Count', 
                                        template="plotly_dark"
                                    )
                                    # X축 레이블이 잘리지 않도록 각도 조정 (자동)
                                    fig.update_layout(xaxis_tickangle=-45)
                                
                                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=400)
                                st.plotly_chart(fig, use_container_width=True)
                    
                    st.markdown("#### 📋 상세 데이터")
                    st.dataframe(view_df, use_container_width=True, hide_index=True, height=500)
                else: st.warning("데이터 없음")
            else: st.info("데이터 없음")

        # [Tab 2] 휴지통
        with t2:
            if trash_data:
                full_trash = pd.concat(trash_data)
                sheets = full_trash['[원본시트]'].unique()
                sel = st.selectbox("확인할 시트", sheets)
                subset = full_trash[full_trash['[원본시트]']==sel].dropna(axis=1, how='all')
                st.warning(f"🚨 {len(subset)}건이 중복 제거되었습니다.")
                st.dataframe(subset, use_container_width=True, hide_index=True)
            else: st.success("중복 없음")

        # [Tab 3] DB
        with t3:
            tbls = database.get_table_names()
            if tbls:
                target = st.selectbox("테이블 선택", tbls)
                q = st.text_area("SQL 쿼리", f"SELECT * FROM {target} LIMIT 50")
                if st.button("쿼리 실행", use_container_width=True):
                    d, m = database.execute_query(q)
                    if d is not None: st.dataframe(d)
                    else: st.error(m)
                
                with st.expander("⚠️ 데이터 초기화"):
                    if st.button("모든 데이터 삭제", type="primary"):
                        database.clear_database()
                        st.rerun()
            else: st.info("저장된 데이터 없음")