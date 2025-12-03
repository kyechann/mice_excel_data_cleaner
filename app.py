import streamlit as st
import pandas as pd
import io
import plotly.express as px
import time
from modules import cleaner, database, reporter
import os
from dotenv import load_dotenv

# ==========================================
# 0. 환경 변수 로드
# ==========================================
load_dotenv()
ADMIN_ID = os.getenv("ADMIN_ID", "admin")
ADMIN_PW = os.getenv("ADMIN_PW", "1234")

# ==========================================
# 1. 페이지 설정 및 디자인
# ==========================================
st.set_page_config(page_title="Data Cleaner Pro", page_icon="💎", layout="wide", initial_sidebar_state="collapsed")

if 'page' not in st.session_state: st.session_state['page'] = 'dashboard'
if 'analyzed_data' not in st.session_state: st.session_state['analyzed_data'] = None
if 'admin_logged_in' not in st.session_state: st.session_state['admin_logged_in'] = False

def navigate_to(page):
    st.session_state['page'] = page
    st.rerun()

def reset_analysis():
    st.session_state['analyzed_data'] = None
    st.rerun()

def logout():
    st.session_state['admin_logged_in'] = False
    st.toast("로그아웃 되었습니다.", icon="👋")
    navigate_to('dashboard')

st.markdown("""
<style>
    @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.8/dist/web/static/pretendard.css");
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .stApp { background-color: #0f1117; }
    
    /* ============================================================ */
    /* [1] 상단 네비게이션 아이콘 버튼 (반응형 & 투명화) */
    /* ============================================================ */
    
    /* 첫 번째 Row의 1~3번째 컬럼 내 버튼 타겟팅 */
    div[data-testid="column"]:nth-of-type(-n+3) button {
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
        font-size: 2.0rem !important;  
        padding: 0 !important;
        margin: 0 auto !important;     /* 가로 중앙 */
        height: auto !important;
        width: 100% !important;        /* 부모 너비 꽉 채움 */
        min-height: 50px !important;   /* 최소 높이 확보 */
        color: #94a3b8 !important;
        
        /* [핵심 수정] Flexbox로 내용물(이모지) 정중앙 정렬 */
        display: flex !important;
        align-items: center !important;     /* 수직 중앙 */
        justify-content: center !important; /* 수평 중앙 */
        line-height: 1 !important;
    }
    
    /* 내부 텍스트 컨테이너도 중앙 정렬 강제 */
    div[data-testid="column"]:nth-of-type(-n+3) button > div {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    
    div[data-testid="column"]:nth-of-type(-n+3) button:hover {
        color: #60a5fa !important;
        background-color: transparent !important;
        transform: scale(1.2);
        transition: transform 0.2s ease;
    }
    
    /* 컬럼 자체도 내용물 중앙 정렬 */
    div[data-testid="column"]:nth-of-type(-n+3) {
        min-width: 50px !important;
        flex: 1 1 auto !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }

    /* ============================================================ */
    /* [2] 하단 작업 버튼 (박스 스타일 유지) */
    /* ============================================================ */
    
    div[data-testid="column"]:nth-of-type(n+4) button {
        height: 55px !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        font-size: 1.05rem !important;
        width: 100%;
        margin-top: 0px !important;
        transition: all 0.2s ease;
    }

    button[kind="primary"] {
        background: linear-gradient(135deg, #ef4444, #b91c1c) !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 4px 15px rgba(239, 68, 68, 0.4) !important;
    }
    button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(239, 68, 68, 0.6) !important;
    }

    button[kind="secondary"] {
        background-color: #334155 !important;
        color: #f8fafc !important;
        border: 1px solid #475569 !important;
    }
    div[data-testid="column"]:nth-of-type(n+4) button[kind="secondary"]:hover {
        border-color: #94a3b8 !important;
        background-color: #475569 !important;
        transform: translateY(-2px);
    }

    /* ============================================================ */
    /* [3] 기타 UI 컴포넌트 */
    /* ============================================================ */
    
    .kpi-card { background-color: #1e2330; border: 1px solid #334155; border-radius: 16px; padding: 20px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .kpi-value { font-size: clamp(2.5rem, 5vw, 4rem); font-weight: 800; margin: 0; line-height: 1.2; }
    
    .text-blue { color: #60a5fa; }
    .text-orange { color: #fb923c; }
    .text-purple { color: #c084fc; }
    
    .stTabs [data-baseweb="tab-list"] { gap: 10px; border-bottom: 1px solid #334155; }
    .stTabs [data-baseweb="tab"] { height: 50px; background-color: transparent; border: none; color: #64748b; font-weight: 600; }
    .stTabs [aria-selected="true"] { background-color: #1e293b !important; color: #60a5fa !important; border-bottom: 2px solid #60a5fa !important; }
    .stCheckbox label { color: #cbd5e1; font-weight: 600; white-space: nowrap; }

    .qna-box { background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; margin-bottom: 15px; }
    .qna-header { display: flex; justify-content: space-between; color: #94a3b8; font-size: 0.9rem; margin-bottom: 10px; }
    .qna-content { font-size: 1.1rem; color: #f1f5f9; font-weight: 500; margin-bottom: 15px; white-space: pre-wrap; }
    .qna-answer { background-color: #334155; padding: 15px; border-radius: 8px; border-left: 4px solid #60a5fa; color: #e2e8f0; }
    .badge-pending { background-color: #fb923c; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }
    .badge-done { background-color: #4ade80; color: #000; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }
    .badge-err { background-color: #ef4444; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; margin-right: 5px;}
    .badge-idea { background-color: #f59e0b; color: black; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; margin-right: 5px;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 상단 네비게이션 (레이아웃 조정)
# ==========================================
# [수정] 버튼 공간을 약간 늘려서(1) 좁은 화면에서도 겹치지 않게 함
col_nav1, col_nav2, col_nav3, col_title = st.columns([0.8, 0.8, 0.8, 9.6])

with col_nav1:
    if st.button("🏠", help="메인 대시보드"): navigate_to('dashboard')
with col_nav2:
    if st.button("💬", help="문의/오류 제보"): navigate_to('qna')
with col_nav3:
    if st.button("⚙️", help="관리자 설정"): navigate_to('admin')

with col_title:
    if st.session_state['page'] == 'dashboard':
        st.markdown("<h1 style='margin:0; padding:0; font-size: 2.5rem;'>💎 Data Cleaner Pro</h1>", unsafe_allow_html=True)
    elif st.session_state['page'] == 'qna':
        st.markdown("<h1 style='margin:0; padding:0; font-size: 2.5rem;'>💬 문의 및 제보 게시판</h1>", unsafe_allow_html=True)
    else:
        st.markdown("<h1 style='margin:0; padding:0; font-size: 2.5rem; color:#94a3b8;'>⚙️ Admin Settings</h1>", unsafe_allow_html=True)

st.write("")

# ==========================================
# 3. 화면 라우팅
# ==========================================

# [PAGE: Q&A]
if st.session_state['page'] == 'qna':
    st.markdown("서비스 이용 중 발생한 **오류**나 **건의사항**을 자유롭게 남겨주세요.")
    
    # [수정 완료] 불필요한 HTML div 제거하고 순수 레이아웃만 사용 -> 빈칸 문제 해결
    with st.container():
        # 1행: 분류 | 작성자 | 제목
        c_cat, c_writer, c_title = st.columns([1.5, 1.5, 7])
        with c_cat:
            category = st.selectbox("분류", ["🚨 오류", "💡 건의사항"], label_visibility="collapsed")
        with c_writer:
            writer = st.text_input("작성자", placeholder="작성자", label_visibility="collapsed")
        with c_title:
            title_input = st.text_input("제목", placeholder="제목을 입력하세요", label_visibility="collapsed")
        
        # 2행: 내용 (넓게)
        content_input = st.text_area("내용", placeholder="상세 내용을 입력하세요", height=300, label_visibility="collapsed")
        
        # 3행: 등록 버튼 (우측 하단)
        _, c_btn = st.columns([8.5, 1.5])
        with c_btn:
            st.write("") 
            if st.button("등록", key="qna_reg", type="primary", use_container_width=True):
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

    st.divider()
    st.subheader("📋 등록된 문의사항")
    
    t_err, t_idea = st.tabs(["🚨 오류 제보", "💡 건의사항"])
    qna_df = database.get_qna_list()

    def render_list(df):
        if df.empty:
            st.info("등록된 게시글이 없습니다.")
            return
        for idx, row in df.iterrows():
            badge_cat = '<span class="badge-err">오류</span>' if row['category']=='오류' else '<span class="badge-idea">건의</span>'
            status_badge = '<span class="badge-done">답변완료</span>' if row['status']=='답변완료' else '<span class="badge-pending">대기중</span>'
            ans_html = f'<div class="qna-answer">↳ 👨‍💻 <b>관리자:</b> {row["answer"]}</div>' if row['answer'] else ""
            
            st.markdown(f"""
            <div class="qna-box">
                <div class="qna-header">
                    <span>{badge_cat} {row['writer']} &nbsp;|&nbsp; {row['created_at']}</span>
                    {status_badge}
                </div>
                <div style="color:white; font-weight:bold; font-size:1.1rem; margin-bottom:5px;">{row['title']}</div>
                <div class="qna-content">{row['content']}</div>
                {ans_html}
            </div>
            """, unsafe_allow_html=True)

    with t_err:
        if not qna_df.empty: render_list(qna_df[qna_df['category']=='오류'])
        else: st.info("등록된 오류 제보가 없습니다.")
    
    with t_idea:
        if not qna_df.empty: render_list(qna_df[qna_df['category']=='건의사항'])
        else: st.info("등록된 건의사항이 없습니다.")

# [PAGE: Admin] 관리자 페이지
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
                    else: st.error("정보가 일치하지 않습니다.")
    else:
        col_dummy, col_out = st.columns([9, 1])
        with col_out:
            if st.button("로그아웃", key="logout_btn"): logout()

        st.markdown("---")
        tab_map, tab_qna, tab_sys = st.tabs(["🧩 매핑 관리", "📝 Q&A 답변", "⚠️ 시스템"])
        
        with tab_map:
            c_map = cleaner.load_mapping()
            df = pd.DataFrame(list(c_map.items()), columns=['입력', '변환'])
            edit = st.data_editor(df, num_rows="dynamic", use_container_width=True, height=500, hide_index=True)
            if st.button("규칙 저장", key="map_save", type="primary"):
                cleaner.save_mapping(dict(zip(edit['입력'], edit['변환'])))
                st.toast("저장됨!", icon="✅")

        with tab_qna:
            st.subheader("📬 답변 대기 중인 질문")
            qna_df = database.get_qna_list()
            if not qna_df.empty:
                pending = qna_df[qna_df['status']=='대기중']
                if not pending.empty:
                    q_opts = {f"[{row['category']}] {row['title']} ({row['writer']})": row['id'] for idx, row in pending.iterrows()}
                    sel_label = st.selectbox("질문 선택", list(q_opts.keys()))
                    sel_id = q_opts[sel_label]
                    
                    target = pending[pending['id']==sel_id].iloc[0]
                    st.info(f"Q. {target['content']}")
                    
                    ans = st.text_area("답변 입력")
                    if st.button("답변 등록", key="ans_reg", type="primary"):
                        database.add_answer(sel_id, ans)
                        st.success("등록 완료")
                        st.rerun()
                else: st.success("대기 중인 질문이 없습니다.")
                with st.expander("전체 문의 기록 보기"): st.dataframe(qna_df, use_container_width=True)
            else: st.info("문의 내역이 없습니다.")

        with tab_sys:
            st.error("⚠️ 데이터 초기화")
            if st.button("전체 삭제", key="db_del"):
                database.clear_database()
                st.toast("삭제 완료", icon="💥")

# [PAGE: Dashboard] 메인 대시보드
else:
    if st.session_state['analyzed_data'] is None:
        st.markdown('<p style="color:#94a3b8; font-size:1.1rem; margin-bottom:40px;">복잡한 명단 정리, AI 자동화로 1초 만에 해결하세요.</p>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader("분석할 엑셀 파일을 드래그하거나 선택하세요", type=['xlsx'])
        if uploaded_file:
            with st.spinner("⚡ AI 엔진 구동 중..."):
                try:
                    s = time.time()
                    buf, clean, trash, msg = cleaner.run_cleaning_pipeline(uploaded_file)
                    e = time.time()
                    if msg == "Success":
                        st.session_state['analyzed_data'] = {'excel_buffer': buf, 'cleaned_data': clean, 'trash_data': trash, 'filename': uploaded_file.name, 'elapsed': f"{e-s:.2f}s"}
                        st.rerun()
                    else: st.error(msg)
                except Exception as e: st.error(f"Error: {e}")
    else:
        col_dummy, col_reset = st.columns([8, 2])
        with col_reset:
            if st.button("🔄 새 파일 분석", key="reset_btn", type="secondary"): reset_analysis()

        data = st.session_state['analyzed_data']
        cleaned_data = data['cleaned_data']
        trash_data = data['trash_data']
        excel_buffer = data['excel_buffer']
        filename = data['filename']
        t_clean = sum(len(df) for df in cleaned_data.values())
        t_trash = sum(len(df) for df in trash_data) if trash_data else 0
        
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(f"""<div class="kpi-card"><div class="kpi-title">✨ 정제된 데이터</div><div class="kpi-value text-blue">{t_clean:,}</div><div class="kpi-delta">Clean Rows</div></div>""", unsafe_allow_html=True)
        with c2: st.markdown(f"""<div class="kpi-card"><div class="kpi-title">🗑️ 중복 데이터</div><div class="kpi-value text-orange">{t_trash:,}</div><div class="kpi-delta">- Duplicates</div></div>""", unsafe_allow_html=True)
        with c3: st.markdown(f"""<div class="kpi-card"><div class="kpi-title">🚀 처리 속도</div><div class="kpi-value text-purple">{data['elapsed']}</div><div class="kpi-delta">Ultra Fast</div></div>""", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)

        st.subheader("🛠️ 작업 컨트롤 패널")
        
        # 체크박스 (버튼과 분리)
        st.markdown('<div style="margin-bottom: 10px;">', unsafe_allow_html=True)
        mask_check = st.checkbox("🔒 개인정보 마스킹 (이름/번호 가리기)", value=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # 버튼 (3개 균등 배치)
        with st.container():
            col_act1, col_act2, col_act3 = st.columns(3, gap="medium")
            
            with col_act1:
                final_buffer = excel_buffer
                if mask_check:
                    masked_dict = {k: cleaner.mask_personal_info(v) for k,v in cleaned_data.items()}
                    final_buffer = io.BytesIO()
                    with pd.ExcelWriter(final_buffer, engine='xlsxwriter') as w:
                        for k, v in masked_dict.items(): v.to_excel(w, sheet_name=k, index=False)
                st.download_button("💾 엑셀 다운로드", data=final_buffer.getvalue(), file_name=f"Cleaned_{filename}", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", use_container_width=True, key="dn_excel")

            with col_act2:
                stats = {'total_rows': t_clean+t_trash, 'removed_rows': t_trash, 'missing_info_rows': 0}
                f_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'NanumGothic.ttf')
                if st.button("📄 PDF 리포트 생성", use_container_width=True, key="btn_pdf"):
                    if not os.path.exists(f_path): st.error("폰트 없음")
                    else:
                        try:
                            pdf = reporter.create_pdf_report(stats, cleaned_data)
                            st.download_button("📥 PDF 받기", pdf, "report.pdf", "application/pdf", use_container_width=True)
                        except: st.error("실패")

        with col_act3:
                    if st.button("🗄️ DB에 저장하기", use_container_width=True, key="btn_db"):
                        suc, m = database.save_to_db(cleaned_data, filename)
                        # [수정] 줄바꿈으로 문법 오류 해결
                        if suc:
                            st.toast("저장 완료!", icon="✅")
                        else:
                            st.error(m)

        st.markdown("---")
        t1, t2, t3 = st.tabs(["📊 인사이트 & 필터", "🗑️ 휴지통 (중복)", "💾 DB 히스토리"])
        
        with t1:
            if cleaned_data:
                c_sel1, c_sel2 = st.columns([1, 4])
                with c_sel1: sh = st.selectbox("분석 시트", list(cleaned_data.keys()))
                df = cleaned_data[sh]
                with st.expander("🔍 상세 검색", expanded=False):
                    cols = st.multiselect("필터 컬럼", df.columns)
                    conds = {c: st.text_input(f"'{c}' 검색") for c in cols}
                    view_df = df.copy()
                    for c, val in conds.items():
                        if val: view_df = view_df[view_df[c].astype(str).str.contains(val, case=False)]
                
                if not view_df.empty:
                    potential = [c for c in view_df.columns if not any(k in str(c).lower() for k in ['이름','name','이메일','email','phone','전화','비고','check','no'])]
                    if potential:
                        st.markdown(f"##### 📈 **{sh}** 시각화")
                        cols_ui = st.columns(2)
                        for i, col_name in enumerate(potential):
                            with cols_ui[i%2]:
                                c_data = view_df[col_name].fillna('미입력').value_counts().reset_index()
                                c_data.columns = [col_name, 'Count']
                                if len(c_data) <= 5:
                                    fig = px.pie(c_data, values='Count', names=col_name, title=f"{col_name} 비율", hole=0.3, template="plotly_dark")
                                    fig.update_traces(textposition='inside', textinfo='percent+label')
                                else:
                                    top = c_data.head(10)
                                    fig = px.bar(top, x=col_name, y='Count', title=f"{col_name} TOP 10", text='Count', template="plotly_dark")
                                    fig.update_layout(xaxis_tickangle=-45)
                                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=400)
                                st.plotly_chart(fig, use_container_width=True)
                    st.markdown("#### 📋 상세 데이터")
                    st.dataframe(view_df, use_container_width=True, hide_index=True, height=500)
                else: st.warning("데이터 없음")
            else: st.info("데이터 없음")

        with t2:
            if trash_data:
                full_trash = pd.concat(trash_data)
                sheets = full_trash['[원본시트]'].unique()
                sel = st.selectbox("확인할 시트", sheets)
                subset = full_trash[full_trash['[원본시트]']==sel].dropna(axis=1, how='all')
                st.warning(f"🚨 {len(subset)}건 중복 제거됨")
                st.dataframe(subset, use_container_width=True, hide_index=True)
            else: st.success("중복 없음")

        with t3:
            tbls = database.get_table_names()
            if tbls:
                target = st.selectbox("테이블 선택", tbls)
                q = st.text_area("SQL 쿼리", f"SELECT * FROM {target} LIMIT 50")
                if st.button("쿼리 실행", use_container_width=True, key="sql_run"):
                    d, m = database.execute_query(q)
                    if d is not None: st.dataframe(d)
                    else: st.error(m)
            else: st.info("데이터 없음")