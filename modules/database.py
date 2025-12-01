import pandas as pd
from sqlalchemy import create_engine, inspect, text, MetaData
from datetime import datetime
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'data', 'cleaned_data.db')
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

engine = create_engine(f'sqlite:///{DB_PATH}')

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
        return inspect(engine).get_table_names()
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