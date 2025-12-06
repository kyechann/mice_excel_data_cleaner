import pandas as pd
import re
import json
import os
import io
import xlsxwriter
import difflib
import numpy as np

# ... (기존 상수 및 함수들: load_mapping, save_mapping, clean_company_name, normalize_strings 등등 그대로 유지) ...
# (지면 관계상 위쪽 기존 함수들은 생략하지 않고, 사용자가 전체 복붙할 수 있도록 전체 코드를 드립니다.)

# =====================
# 설정 및 상수
# =====================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPPING_FILE = os.path.join(BASE_DIR, 'data', 'mapping_config.json')

EMAIL_KEYWORDS = ['이메일', 'email', 'e-mail', 'mail']
PHONE_KEYWORDS = ['전화', 'phone', 'tel', 'mobile', '휴대폰', '연락처', 'contact']
NAME_KEYWORDS = ['이름', '성명', 'name', 'first name', 'last name', '참가자', 'full name', 'representative', '대표자']
COMPANY_KEYWORDS = ['회사', '소속', 'company', 'organization', 'org', 'firm', 'agency', '부스', 'booth', '업체']
COUNTRY_KEYWORDS = ['국가', '나라', 'country', 'nation', 'nationality', 'region']

DEFAULT_MAPPING = {
    '삼성': 'Samsung', '삼성전자': 'Samsung', 'samsungelectronics': 'Samsung',
    'lg': 'LG', '엘지': 'LG', '현대': 'Hyundai', 'sk': 'SK', 
    'naver': 'Naver', 'kakao': 'Kakao', 'google': 'Google', 'apple': 'Apple'
}

# =====================
# 매핑 관리 함수
# =====================
def load_mapping():
    if not os.path.exists(MAPPING_FILE):
        os.makedirs(os.path.dirname(MAPPING_FILE), exist_ok=True)
        with open(MAPPING_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_MAPPING, f, ensure_ascii=False, indent=4)
        return DEFAULT_MAPPING
    with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_mapping(new_mapping):
    with open(MAPPING_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_mapping, f, ensure_ascii=False, indent=4)

# =====================
# 정제 헬퍼 함수
# =====================

def get_columns_by_keywords(df, keywords):
    return [col for col in df.columns if any(k in str(col).lower() for k in keywords)]

def remove_sequence_columns(df):
    seq_keywords = ['no', 'no.', '연번', '순번', '번호', 'nr', 'num']
    cols = [c for c in df.columns if str(c).lower().strip() in seq_keywords]
    if cols: df = df.drop(columns=cols)
    return df

def clean_company_name(text, mapping_dict):
    if not isinstance(text, str): return text
    text_clean = text.lower()
    patterns = [r'\(주\)', r'\(유\)', r'\(사\)', r'\(재\)', r'주식회사', r'\binc\.?\b', r'\bcorp\.?\b', r'\bltd\.?\b', r'\bkorea\b', r'\bkr\b']
    for pat in patterns:
        text_clean = re.sub(pat, '', text_clean)
    text_clean = re.sub(r'[.,()\-]', ' ', text_clean).strip()
    lookup = text_clean.replace(" ", "")
    if lookup in mapping_dict: return mapping_dict[lookup]
    return text_clean.title()

def clean_country_name(text):
    if not isinstance(text, str): return text
    clean_text = text.lower().replace(" ", "").replace(".", "")
    country_map = {
        'korea': '대한민국', 'southkorea': '대한민국', 'rok': '대한민국', 'kr': '대한민국',
        'usa': '미국', 'us': '미국', 'america': '미국',
        'japan': '일본', 'jp': '일본', 'china': '중국', 'cn': '중국'
    }
    return country_map.get(clean_text, text.strip())

def normalize_strings(df):
    mapping_dict = load_mapping()
    clean_mapping = {k.replace(" ", "").lower(): v for k, v in mapping_dict.items()}
    df = df.copy()
    
    obj_cols = df.select_dtypes(include=['object']).columns
    if len(obj_cols) > 0:
        df[obj_cols] = df[obj_cols].apply(lambda x: x.str.strip())

    for col in df.columns:
        c_lower = str(col).lower()
        if any(k in c_lower for k in COMPANY_KEYWORDS):
            s = df[col].astype(str).str.lower()
            remove_pat = r'\(주\)|\(유\)|\(사\)|\(재\)|주식회사|\binc\.?|\bcorp\.?|\bltd\.?|\bkorea|\bkr'
            s = s.str.replace(remove_pat, '', regex=True)
            s = s.str.replace(r'[.,()\-]', ' ', regex=True).str.strip()
            s_lookup = s.str.replace(" ", "")
            mapped = s_lookup.map(clean_mapping).fillna(s.str.title())
            df[col] = np.where(df[col].isna(), df[col], mapped)
        elif any(k in c_lower for k in COUNTRY_KEYWORDS):
            df[col] = df[col].apply(clean_country_name)
        elif any(k in c_lower for k in NAME_KEYWORDS):
            df[col] = df[col].astype(str).str.title()
        elif any(k in c_lower for k in EMAIL_KEYWORDS):
            df[col] = df[col].astype(str).str.lower().str.strip()
        elif any(k in c_lower for k in PHONE_KEYWORDS):
            df[col] = df[col].astype(str).str.replace(r'[^0-9+]', '', regex=True)
            df[col] = df[col].replace({'nan': pd.NA, 'none': pd.NA, '': pd.NA})

    df = df.replace(["", "nan", "NaN", "None", "NONE", "Nat"], pd.NA)
    df = df.dropna(how="all")
    return df

def flag_missing_info(df, email_cols, phone_cols, comp_cols):
    has_email = df[email_cols].notna().any(axis=1) if email_cols else pd.Series([False]*len(df), index=df.index)
    has_phone = df[phone_cols].notna().any(axis=1) if phone_cols else pd.Series([False]*len(df), index=df.index)
    has_comp = df[comp_cols].notna().any(axis=1) if comp_cols else pd.Series([False]*len(df), index=df.index)
    
    conditions = [(~has_email) & (~has_phone), (~has_email), (~has_phone)]
    choices = ["⚠️ 이메일, 전화번호 누락", "이메일 누락", "전화번호 누락"]
    
    contact_msg = np.select(conditions, choices, default="")
    comp_msg = np.where(~has_comp, "소속 누락", "")
    
    final_msg = pd.Series(contact_msg, index=df.index)
    mask_comp = comp_msg != ""
    mask_contact = final_msg != ""
    final_msg[mask_comp & mask_contact] = final_msg[mask_comp & mask_contact] + " / " + comp_msg[mask_comp & mask_contact]
    final_msg[mask_comp & ~mask_contact] = comp_msg[mask_comp & ~mask_contact]
    
    df['비고_상태체크'] = final_msg
    return df

def mask_personal_info(df):
    df = df.copy()
    for col in df.columns:
        c_lower = str(col).lower()
        if any(k in c_lower for k in NAME_KEYWORDS):
            def mask_name(val):
                s = str(val)
                if len(s) <= 1: return s
                if len(s) == 2: return s[0] + "*"
                return s[0] + "*" * (len(s) - 2) + s[-1]
            df[col] = df[col].apply(mask_name)
        elif any(k in c_lower for k in PHONE_KEYWORDS):
            def mask_phone(val):
                s = str(val)
                if len(s) <= 4: return s
                return s[:-8] + "****" + s[-4:] if len(s) > 8 else "****" + s[-4:]
            df[col] = df[col].apply(mask_phone)
        elif any(k in c_lower for k in EMAIL_KEYWORDS):
            def mask_email(val):
                s = str(val)
                if '@' not in s: return s
                try:
                    id_part, domain = s.split('@', 1)
                    masked_id = id_part[0] + "**" if len(id_part) <= 2 else id_part[:2] + "**"
                    return masked_id + "@" + domain
                except: return s
            df[col] = df[col].apply(mask_email)
    return df

def find_fuzzy_duplicates(df, cols, threshold=0.9):
    limit = 2000 
    records = []
    for col in cols:
        if col not in df.columns: continue
        vals = df[col].dropna().astype(str).unique().tolist()
        if len(vals) > limit: continue
        seen = set()
        for i in range(len(vals)):
            for j in range(i+1, len(vals)):
                a, b = vals[i], vals[j]
                if difflib.SequenceMatcher(None, a, b).ratio() >= threshold:
                    pair = tuple(sorted([a, b]))
                    if pair not in seen:
                        seen.add(pair)
                        records.append({"column": col, "val1": a, "val2": b})
    return pd.DataFrame(records)

# [NEW] 템플릿 메시지 생성 함수
def generate_message_column(df, template_text):
    """데이터프레임의 컬럼 값을 이용해 템플릿 메시지를 생성"""
    df = df.copy()
    
    # 1. 주요 컬럼 자동 감지 (사용자가 편하게 {이름}만 써도 되도록 매핑)
    # 엑셀 컬럼명 중에서 '이름', '소속' 등에 해당하는 실제 컬럼명을 찾음
    col_map = {}
    
    # 이름 컬럼 찾기
    name_col = next((c for c in df.columns if any(k in str(c).lower() for k in NAME_KEYWORDS)), None)
    if name_col: col_map['{이름}'] = name_col
    
    # 소속 컬럼 찾기
    comp_col = next((c for c in df.columns if any(k in str(c).lower() for k in COMPANY_KEYWORDS)), None)
    if comp_col: col_map['{소속}'] = comp_col
    
    # 전화번호 컬럼 찾기
    phone_col = next((c for c in df.columns if any(k in str(c).lower() for k in PHONE_KEYWORDS)), None)
    if phone_col: col_map['{전화번호}'] = phone_col
    
    # 이메일 컬럼 찾기
    email_col = next((c for c in df.columns if any(k in str(c).lower() for k in EMAIL_KEYWORDS)), None)
    if email_col: col_map['{이메일}'] = email_col

    def apply_template(row):
        msg = template_text
        
        # 2. 스마트 치환 (단축 키워드 먼저 적용)
        # 예: 사용자가 {이름} 이라고 썼으면 -> 실제 컬럼 '이름 (Name)'의 값으로 변경
        for placeholder, real_col in col_map.items():
            if placeholder in msg:
                val = str(row[real_col]) if pd.notna(row[real_col]) else ""
                msg = msg.replace(placeholder, val)
        
        # 3. 정밀 치환 (컬럼명 직접 입력한 경우)
        # 예: 사용자가 {비고_상태체크} 처럼 정확한 컬럼명을 쓴 경우
        for col in df.columns:
            exact_placeholder = "{" + str(col) + "}"
            if exact_placeholder in msg:
                val = str(row[col]) if pd.notna(row[col]) else ""
                msg = msg.replace(exact_placeholder, val)
                
        return msg

    df['생성된_메시지'] = df.apply(apply_template, axis=1)
    return df

# =====================
# 메인 파이프라인
# =====================
def run_cleaning_pipeline(uploaded_file):
    try:
        try:
            import python_calamine
            engine = 'calamine'
        except ImportError:
            engine = 'openpyxl'
        sheets = pd.read_excel(uploaded_file, sheet_name=None, dtype=object, engine=engine)
    except Exception as e:
        return None, None, None, str(e)

    cleaned_sheets = {}
    trash_list = []
    output_buffer = io.BytesIO()

    with pd.ExcelWriter(output_buffer, engine='xlsxwriter') as writer:
        for sheet_name, df in sheets.items():
            if df.empty: continue
            
            df = normalize_strings(df)
            e_cols = get_columns_by_keywords(df, EMAIL_KEYWORDS)
            p_cols = get_columns_by_keywords(df, PHONE_KEYWORDS)
            c_cols = get_columns_by_keywords(df, COMPANY_KEYWORDS)
            
            df['_SCORE'] = df.notna().sum(axis=1)
            df = df.sort_values('_SCORE', ascending=False)
            
            delete_mask = pd.Series([False]*len(df), index=df.index)
            for col_group in [e_cols, p_cols]:
                for c in col_group:
                    valid = df[c].astype(str).str.len() > 3
                    delete_mask |= (valid & df.duplicated(subset=[c], keep='first'))
            
            trash_df = df[delete_mask].copy()
            clean_df = df[~delete_mask].copy()
            
            if not trash_df.empty:
                trash_df.insert(0, '[원본시트]', sheet_name)
                if '_SCORE' in trash_df.columns: trash_df = trash_df.drop(columns=['_SCORE'])
                trash_list.append(trash_df)
            
            clean_df = flag_missing_info(clean_df, e_cols, p_cols, c_cols)
            clean_df = remove_sequence_columns(clean_df)
            if '_SCORE' in clean_df.columns: clean_df = clean_df.drop(columns=['_SCORE'])
            clean_df = clean_df.reset_index(drop=True)
            clean_df.index += 1
            
            cleaned_sheets[sheet_name] = clean_df
            clean_df.to_excel(writer, sheet_name=sheet_name, index=False)
            
        if trash_list:
            full_trash = pd.concat(trash_list)
            for origin, group in full_trash.groupby('[원본시트]'):
                safe_name = re.sub(r'[^\w]', '', origin)[:15]
                group.dropna(axis=1, how='all').to_excel(writer, sheet_name=f"휴지통_{safe_name}", index=False)
                
    return output_buffer, cleaned_sheets, trash_list, "Success"