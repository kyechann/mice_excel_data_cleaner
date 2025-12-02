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
ADMIN_ID = os.getenv("ADMIN_ID") # 없으면 기본값 admin
ADMIN_PW = os.getenv("ADMIN_PW")

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
    
    /* 네비게이션 버튼 스타일 */
    div[data-testid="column"] > div > div > div > div > div > button {
       border: 1px solid #334155;
       background-color: #1e293b;
       color: #e2e8f0;
       transition: 0.3s;
    }
    div[data-testid="column"] > div > div > div > div > div > button:hover {
       border-color: #6366f1;
       color: #6366f1;
    }

    /* KPI 카드 */
    .kpi-card { background-color: #1e2330; border: 1px solid #334155; border-radius: 16px; padding: 20px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .kpi-value { font-size: 3.5rem; font-weight: 800; margin: 0; line-height: 1.2; }
    
    .text-blue { color: #60a5fa; }
    .text-orange { color: #fb923c; }
    .text-purple { color: #c084fc; }
    
    .stButton button, div[data-testid="stDownloadButton"] button { height: 55px !important; border-radius: 10px !important; font-weight: 700 !important; border: none !important; width: 100%; margin-top: 0px !important; }
    button[kind="primary"] { background: linear-gradient(135deg, #4f46e5, #7c3aed) !important; color: white !important; }
    button[kind="secondary"] { background-color: #334155 !important; color: #f8fafc !important; border: 1px solid #475569 !important; }
    
    .stTabs [data-baseweb="tab-list"] { gap: 10px; border-bottom: 1px solid #334155; }
    .stTabs [data-baseweb="tab"] { height: 50px; background-color: transparent; border: none; color: #64748b; }
    .stTabs [aria-selected="true"] { background-color: #1e293b !important; color: #60a5fa !important; border-bottom: 2px solid #60a5fa !important; }
    .stCheckbox label { color: #cbd5e1; font-weight: 600; }

    /* Q&A 스타일 */
    .qna-box { background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; margin-bottom: 15px; }
    .qna-header { display: flex; justify-content: space-between; color: #94a3b8; font-size: 0.9rem; margin-bottom: 10px; }
    .qna-content { font-size: 1.1rem; color: #f1f5f9; font-weight: 500; margin-bottom: 15px; }
    .qna-answer { background-color: #334155; padding: 15px; border-radius: 8px; border-left: 4px solid #60a5fa; color: #e2e8f0; }
    .badge-pending { background-color: #fb923c; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }
    .badge-done { background-color: #4ade80; color: #000; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 상단 네비게이션 (핵심 변경 포인트)
# ==========================================
# 버튼 3개 배치 (대시보드 / Q&A / 관리자)
col_nav1, col_nav2, col_nav3, col_title = st.columns([0.6, 0.6, 0.6, 10.2])

with col_nav1:
    if st.button("🏠", help="메인 대시보드"): navigate_to('dashboard')
with col_nav2:
    # [NEW] 일반 사용자를 위한 Q&A 버튼
    if st.button("💬", help="문의/오류 제보"): navigate_to('qna')
with col_nav3:
    if st.button("⚙️", help="관리자 설정"): navigate_to('admin')

with col_title:
    if st.session_state['page'] == 'dashboard':
        st.markdown("<h1 style='margin:0; padding:0; font-size: 2.2rem;'>💎 Data Cleaner Pro</h1>", unsafe_allow_html=True)
    elif st.session_state['page'] == 'qna':
        st.markdown("<h1 style='margin:0; padding:0; font-size: 2.2rem;'>💬 문의 및 제보 게시판</h1>", unsafe_allow_html=True)
    else:
        st.markdown("<h1 style='margin:0; padding:0; font-size: 2.2rem; color:#94a3b8;'>⚙️ Admin Settings</h1>", unsafe_allow_html=True)

st.write("") # 간격

# ==========================================
# 3. 화면 라우팅
# ==========================================

# [PAGE: Q&A] 사용자 게시판
if st.session_state['page'] == 'qna':
    st.markdown("사용 중 발생하는 **오류**나 **건의사항**을 자유롭게 남겨주세요.")
    
    with st.container():
        col_in1, col_in2, col_btn = st.columns([2, 5, 1])
        with col_in1:
            writer = st.text_input("작성자 (이름)", placeholder="홍길동")
        with col_in2:
            content = st.text_input("문의 내용", placeholder="예: 000 회사 매핑이 안 됩니다.")
        with col_btn:
            st.write("") # 높이 맞춤
            st.write("")
            if st.button("등록", type="primary", use_container_width=True):
                if writer and content:
                    if database.add_question(writer, content):
                        st.toast("등록되었습니다!", icon="✅")
                        time.sleep(0.5)
                        st.rerun()
                    else: st.error("DB 오류")
                else: st.warning("내용을 입력하세요.")

    st.divider()
    
    # 게시글 목록 표시
    qna_list = database.get_qna_list()
    if not qna_list.empty:
        for idx, row in qna_list.iterrows():
            status_badge = '<span class="badge-done">답변완료</span>' if row['status']=='답변완료' else '<span class="badge-pending">대기중</span>'
            answer_div = f'<div class="qna-answer">↳ 👨‍💻 <b>관리자:</b> {row["answer"]}</div>' if row['answer'] else ""
            
            st.markdown(f"""
            <div class="qna-box">
                <div class="qna-header">
                    <span>👤 {row['writer']} &nbsp;|&nbsp; 🕒 {row['created_at']}</span>
                    {status_badge}
                </div>
                <div class="qna-content">Q. {row['content']}</div>
                {answer_div}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("아직 등록된 문의가 없습니다.")


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
        # 상단 로그아웃
        col_dummy, col_out = st.columns([9, 1])
        with col_out:
            if st.button("로그아웃", type="secondary"): logout()

        st.markdown("---")
        tab_map, tab_qna, tab_sys = st.tabs(["🧩 매핑 관리", "📝 Q&A 답변", "⚠️ 시스템"])
        
        with tab_map:
            c_map = cleaner.load_mapping()
            df = pd.DataFrame(list(c_map.items()), columns=['입력', '변환'])
            edit = st.data_editor(df, num_rows="dynamic", use_container_width=True, height=500, hide_index=True)
            if st.button("규칙 저장", type="primary"):
                cleaner.save_mapping(dict(zip(edit['입력'], edit['변환'])))
                st.toast("저장됨!", icon="✅")

        with tab_qna:
            q_list = database.get_qna_list()
            pending = q_list[q_list['status']=='대기중']
            if not pending.empty:
                st.info(f"답변 대기: {len(pending)}건")
                q_sel = st.selectbox("질문 선택", pending['id'].astype(str) + ". " + pending['content'])
                q_id = int(q_sel.split(".")[0])
                ans = st.text_area("답변 작성")
                if st.button("답변 등록", type="primary"):
                    database.add_answer(q_id, ans)
                    st.success("등록 완료")
                    st.rerun()
            else: st.success("모든 문의에 답변했습니다! 🎉")
            
            with st.expander("전체 문의 기록"):
                st.dataframe(q_list, use_container_width=True)

        with tab_sys:
            st.error("⚠️ 데이터 초기화")
            if st.button("전체 삭제"):
                database.clear_database()
                st.toast("삭제 완료", icon="💥")


# [PAGE: Dashboard] 메인 대시보드
else:
    # 1. 파일 업로드 (데이터 없을 때)
    if st.session_state['analyzed_data'] is None:
        st.markdown('<p style="color:#94a3b8; font-size:1.1rem;">복잡한 명단 정리, AI 자동화로 1초 만에 해결하세요.</p>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader("분석할 엑셀 파일을 드래그하거나 선택하세요", type=['xlsx'])
        
        if uploaded_file:
            with st.spinner("⚡ AI 엔진 구동 중..."):
                try:
                    s = time.time()
                    buf, clean, trash, msg = cleaner.run_cleaning_pipeline(uploaded_file)
                    e = time.time()
                    if msg == "Success":
                        st.session_state['analyzed_data'] = {
                            'excel_buffer': buf, 'cleaned_data': clean, 'trash_data': trash,
                            'filename': uploaded_file.name, 'elapsed': f"{e-s:.2f}s"
                        }
                        st.rerun()
                    else: st.error(msg)
                except Exception as e: st.error(f"Error: {e}")

    # 2. 결과 화면 (데이터 있을 때)
    else:
        # 재분석 버튼
        col_dummy, col_reset = st.columns([8, 2])
        with col_reset:
            if st.button("🔄 새 파일 분석", type="secondary", use_container_width=True): reset_analysis()

        data = st.session_state['analyzed_data']
        cleaned_data = data['cleaned_data']
        trash_data = data['trash_data']
        excel_buffer = data['excel_buffer']
        filename = data['filename']
        
        # KPI
        t_clean = sum(len(df) for df in cleaned_data.values())
        t_trash = sum(len(df) for df in trash_data) if trash_data else 0
        
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(f"""<div class="kpi-card"><div class="kpi-title">✨ 정제된 데이터</div><div class="kpi-value text-blue">{t_clean:,}</div><div class="kpi-delta">Clean Rows</div></div>""", unsafe_allow_html=True)
        with c2: st.markdown(f"""<div class="kpi-card"><div class="kpi-title">🗑️ 중복 데이터</div><div class="kpi-value text-orange">{t_trash:,}</div><div class="kpi-delta">- Duplicates</div></div>""", unsafe_allow_html=True)
        with c3: st.markdown(f"""<div class="kpi-card"><div class="kpi-title">🚀 처리 속도</div><div class="kpi-value text-purple">{data['elapsed']}</div><div class="kpi-delta">Ultra Fast</div></div>""", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)

        # 컨트롤 패널
        st.subheader("🛠️ 작업 컨트롤 패널")
        with st.container():
            col_opt, _ = st.columns([2, 8]) 
            with col_opt: mask_check = st.checkbox("🔒 마스킹 (이름/번호 가리기)", value=True)
            col_act1, col_act2, col_act3 = st.columns(3, gap="medium")
            
            with col_act1:
                final_buffer = excel_buffer
                if mask_check:
                    masked_dict = {k: cleaner.mask_personal_info(v) for k,v in cleaned_data.items()}
                    final_buffer = io.BytesIO()
                    with pd.ExcelWriter(final_buffer, engine='xlsxwriter') as w:
                        for k, v in masked_dict.items(): v.to_excel(w, sheet_name=k, index=False)
                st.download_button("💾 엑셀 다운로드", data=final_buffer.getvalue(), file_name=f"Cleaned_{filename}", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", use_container_width=True)

            with col_act2:
                stats = {'total_rows': t_clean+t_trash, 'removed_rows': t_trash, 'missing_info_rows': 0}
                f_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'NanumGothic.ttf')
                if st.button("📄 PDF 리포트 생성", use_container_width=True):
                    if not os.path.exists(f_path): st.error("폰트 없음")
                    else:
                        try:
                            pdf = reporter.create_pdf_report(stats, cleaned_data)
                            st.download_button("📥 PDF 받기", pdf, "report.pdf", "application/pdf", use_container_width=True)
                        except: st.error("실패")

            with col_act3:
                if st.button("🗄️ DB에 저장하기", use_container_width=True):
                    suc, m = database.save_to_db(cleaned_data, filename)
                    if suc: st.toast("저장 완료!", icon="✅")
                    else: st.error(m)

        st.markdown("---")
        
        # 탭 콘텐츠
        t1, t2, t3 = st.tabs(["📊 인사이트 & 필터", "🗑️ 휴지통", "💾 DB 히스토리"])
        
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
                                    fig = px.pie(c_data, values='Count', names=col_name, title=f"{col_name}", hole=0.3, template="plotly_dark")
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
                sel = st.selectbox("휴지통 시트", sheets)
                subset = full_trash[full_trash['[원본시트]']==sel].dropna(axis=1, how='all')
                st.warning(f"🚨 {len(subset)}건 중복 제거됨")
                st.dataframe(subset, use_container_width=True, hide_index=True)
            else: st.success("중복 없음")

        with t3:
            tbls = database.get_table_names()
            if tbls:
                target = st.selectbox("테이블 선택", tbls)
                q = st.text_area("SQL 쿼리", f"SELECT * FROM {target} LIMIT 50")
                if st.button("쿼리 실행", use_container_width=True):
                    d, m = database.execute_query(q)
                    if d is not None: st.dataframe(d)
                    else: st.error(m)
            else: st.info("데이터 없음")