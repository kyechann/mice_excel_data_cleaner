import pandas as pd
from sqlalchemy import create_engine, inspect, text, MetaData
from datetime import datetime
import os
import re

# DB 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'cleaned_data.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

engine = create_engine(f'sqlite:///{DB_PATH}')

# --- 기존 히스토리 관련 함수들 (그대로 유지) ---
def sanitize_table_name(name):
    clean = re.sub(r'[^가-힣a-zA-Z0-9_]', '', name)
    return f"history_{clean}"

def save_to_db(cleaned_sheets, batch_name):
    upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    saved_tables = []
    try:
        for sheet_name, df in cleaned_sheets.items():
            save_df = df.copy()
            save_df['meta_filename'] = batch_name
            save_df['meta_processed_at'] = upload_time
            save_df = save_df.astype(str)
            table_name = sanitize_table_name(sheet_name)
            save_df.to_sql(table_name, con=engine, if_exists='append', index=False)
            saved_tables.append(table_name)
        return True, f"저장 완료 ({len(saved_tables)}개 테이블)"
    except Exception as e:
        return False, str(e)

def get_table_names():
    try:
        tables = inspect(engine).get_table_names()
        return [t for t in tables if t != 'qna_board' and t != 'sqlite_sequence']
    except: return []

def execute_query(query):
    try:
        if not query.strip().lower().startswith("select"):
            return None, "보안상 SELECT 문만 허용됩니다."
        with engine.connect() as conn:
            return pd.read_sql(text(query), con=conn), "Success"
    except Exception as e:
        return None, str(e)

def clear_database():
    try:
        metadata = MetaData()
        metadata.reflect(bind=engine)
        metadata.drop_all(bind=engine)
        return True, "모든 데이터가 초기화되었습니다."
    except Exception as e:
        return False, str(e)

# --- [NEW] Q&A 게시판 관련 함수 (업그레이드됨) ---

def init_qna_table():
    """Q&A 테이블 생성 (컬럼 추가됨: category, title)"""
    with engine.connect() as conn:
        # 테이블이 없으면 생성
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS qna_board (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                writer TEXT,
                title TEXT,
                content TEXT,
                answer TEXT,
                created_at TEXT,
                status TEXT
            )
        """))
        
        # (기존 사용자를 위한 마이그레이션) 컬럼이 없는 경우 추가 시도
        try:
            conn.execute(text("ALTER TABLE qna_board ADD COLUMN category TEXT"))
            conn.execute(text("ALTER TABLE qna_board ADD COLUMN title TEXT"))
        except:
            pass # 이미 컬럼이 있으면 무시
        
        conn.commit()

def add_question(writer, category, title, content):
    """질문 등록 (분류, 제목 추가)"""
    init_qna_table()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO qna_board (writer, category, title, content, created_at, status) 
                VALUES (:writer, :category, :title, :content, :now, '대기중')
            """), {"writer": writer, "category": category, "title": title, "content": content, "now": now})
            conn.commit()
        return True
    except Exception as e:
        print(e)
        return False

def get_qna_list():
    """Q&A 목록 조회"""
    init_qna_table()
    try:
        return pd.read_sql("SELECT * FROM qna_board ORDER BY id DESC", con=engine)
    except:
        return pd.DataFrame()

def add_answer(q_id, answer):
    """답변 등록"""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                UPDATE qna_board 
                SET answer = :answer, status = '답변완료' 
                WHERE id = :id
            """), {"answer": answer, "id": q_id})
            conn.commit()
        return True
    except:
        return False