import pandas as pd
import re
import json
import os
import io
import xlsxwriter
import difflib
import numpy as np

# =====================
# 설정 및 상수 (정규식 미리 컴파일 -> 속도 향상)
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

# 정규식 패턴 미리 컴파일 (속도 최적화)
PAT_COMPANY_REMOVE = re.compile(r'\(주\)|\(유\)|\(사\)|\(재\)|주식회사|\binc\.?|\bcorp\.?|\bltd\.?|\bkorea|\bkr', re.IGNORECASE)
PAT_SPECIAL_CHARS = re.compile(r'[.,()\-]', re.IGNORECASE)
PAT_PHONE = re.compile(r'[^0-9+]', re.IGNORECASE)

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
# 정제 헬퍼 함수 (Vectorized)
# =====================

def get_columns_by_keywords(df, keywords):
    # 컬럼명이 문자열이 아닌 경우 대비
    return [col for col in df.columns if any(k in str(col).lower() for k in keywords)]

def remove_sequence_columns(df):
    seq_keywords = ['no', 'no.', '연번', '순번', '번호', 'nr', 'num']
    cols = [c for c in df.columns if str(c).lower().strip() in seq_keywords]
    if cols: df = df.drop(columns=cols)
    return df

def normalize_strings(df):
    # 매핑 데이터 로드 및 최적화
    mapping_dict = load_mapping()
    clean_mapping = {k.replace(" ", "").lower(): v for k, v in mapping_dict.items()}
    
    # [성능] object 타입만 골라서 공백 제거 (전체 데이터프레임 순회 방지)
    obj_cols = df.select_dtypes(include=['object']).columns
    if len(obj_cols) > 0:
        # .str 접근자를 사용하여 벡터화된 공백 제거
        df[obj_cols] = df[obj_cols].apply(lambda x: x.str.strip())

    for col in df.columns:
        c_lower = str(col).lower()
        
        # 2. 회사명 정규화
        if any(k in c_lower for k in COMPANY_KEYWORDS):
            s = df[col].astype(str).str.lower()
            # 컴파일된 정규식 사용
            s = s.str.replace(PAT_COMPANY_REMOVE, '', regex=True)
            s = s.str.replace(PAT_SPECIAL_CHARS, ' ', regex=True).str.strip()
            
            # 매핑 적용
            s_lookup = s.str.replace(" ", "")
            mapped = s_lookup.map(clean_mapping).fillna(s.str.title())
            
            # 원본이 NaN이면 유지, 아니면 매핑값
            df[col] = np.where(df[col].isna(), df[col], mapped)

        # 3. 국가명 정규화
        elif any(k in c_lower for k in COUNTRY_KEYWORDS):
            s = df[col].astype(str).str.lower().str.replace(" ", "").str.replace(".", "", regex=False)
            country_map = {
                'korea': '대한민국', 'southkorea': '대한민국', 'rok': '대한민국', 'kr': '대한민국',
                'usa': '미국', 'us': '미국', 'america': '미국',
                'japan': '일본', 'jp': '일본', 'china': '중국', 'cn': '중국'
            }
            df[col] = s.map(country_map).fillna(df[col].astype(str).str.strip())

        # 4. 이름 Title Case
        elif any(k in c_lower for k in NAME_KEYWORDS):
            df[col] = df[col].astype(str).str.title()

        # 5. 이메일 소문자
        elif any(k in c_lower for k in EMAIL_KEYWORDS):
            df[col] = df[col].astype(str).str.lower().str.strip()

        # 6. 전화번호 정규화
        elif any(k in c_lower for k in PHONE_KEYWORDS):
            # 숫자와 + 제외 제거
            df[col] = df[col].astype(str).str.replace(PAT_PHONE, '', regex=True)
            df[col] = df[col].replace({'nan': pd.NA, 'none': pd.NA, '': pd.NA})

    df = df.replace(["", "nan", "NaN", "None", "NONE", "Nat"], pd.NA)
    # 모든 컬럼이 비어있는 행만 삭제
    df = df.dropna(how="all")
    return df

def flag_missing_info(df, email_cols, phone_cols, comp_cols):
    # 벡터화된 로직 유지
    has_email = df[email_cols].notna().any(axis=1) if email_cols else pd.Series([False]*len(df), index=df.index)
    has_phone = df[phone_cols].notna().any(axis=1) if phone_cols else pd.Series([False]*len(df), index=df.index)
    has_comp = df[comp_cols].notna().any(axis=1) if comp_cols else pd.Series([False]*len(df), index=df.index)
    
    conditions = [
        (~has_email) & (~has_phone),
        (~has_email),
        (~has_phone)
    ]
    choices = [
        "⚠️ 이메일, 전화번호 누락",
        "이메일 누락",
        "전화번호 누락"
    ]
    
    contact_msg = np.select(conditions, choices, default="")
    comp_msg = np.where(~has_comp, "소속 누락", "")
    
    # 문자열 벡터 결합 (빠름)
    final_msg = pd.Series(contact_msg, index=df.index)
    
    # numpy where를 이용한 조건부 결합
    combined = np.where(
        (final_msg != "") & (comp_msg != ""),
        final_msg + " / " + comp_msg,
        np.where(final_msg != "", final_msg, comp_msg)
    )
    
    df['비고_상태체크'] = combined
    return df

def mask_personal_info(df):
    """개인정보 마스킹 (이름, 전화, 이메일) - 안전한 apply 방식"""
    df = df.copy()
    for col in df.columns:
        c_lower = str(col).lower()
        
        # 이름 마스킹: 첫글자 + * + 마지막글자 (길이에 따라 다름)
        if any(k in c_lower for k in NAME_KEYWORDS):
            def mask_name(val):
                s = str(val)
                if len(s) <= 1: return s
                if len(s) == 2: return s[0] + "*"
                return s[0] + "*" * (len(s) - 2) + s[-1]
            df[col] = df[col].apply(mask_name)

        # 전화번호 마스킹: 뒤 4자리 앞을 마스킹
        elif any(k in c_lower for k in PHONE_KEYWORDS):
            def mask_phone(val):
                s = str(val)
                if len(s) <= 4: return s
                return s[:-8] + "****" + s[-4:] if len(s) > 8 else "****" + s[-4:]
            df[col] = df[col].apply(mask_phone)
            
        # 이메일 마스킹: ID 앞 2자리만 노출
        elif any(k in c_lower for k in EMAIL_KEYWORDS):
            def mask_email(val):
                s = str(val)
                if '@' not in s: return s
                try:
                    id_part, domain = s.split('@', 1)
                    if len(id_part) <= 2:
                        masked_id = id_part[0] + "**"
                    else:
                        masked_id = id_part[:2] + "**"
                    return masked_id + "@" + domain
                except: return s
            df[col] = df[col].apply(mask_email)
            
    return df

def find_fuzzy_duplicates(df, cols, threshold=0.9):
    # [성능] 데이터가 많으면 과감히 스킵
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

# =====================
# 메인 파이프라인
# =====================
def run_cleaning_pipeline(uploaded_file):
    try:
        # [핵심] 엔진 변경: openpyxl -> calamine (속도 5배 이상 향상)
        # calamine이 설치되어 있으면 사용, 없으면 openpyxl 사용 (Fallback)
        try:
            import python_calamine
            engine = 'calamine'
        except ImportError:
            engine = 'openpyxl'
            
        sheets = pd.read_excel(uploaded_file, sheet_name=None, dtype=object, engine=engine)
        
    except Exception as e:
        return None, None, None, f"파일 읽기 실패 ({str(e)})"

    cleaned_sheets = {}
    trash_list = []
    output_buffer = io.BytesIO()

    # xlsxwriter는 쓰기 속도가 가장 빠름
    with pd.ExcelWriter(output_buffer, engine='xlsxwriter') as writer:
        for sheet_name, df in sheets.items():
            if df.empty: continue
            
            # 1. 정규화
            df = normalize_strings(df)
            
            # 2. 컬럼 감지
            e_cols = get_columns_by_keywords(df, EMAIL_KEYWORDS)
            p_cols = get_columns_by_keywords(df, PHONE_KEYWORDS)
            c_cols = get_columns_by_keywords(df, COMPANY_KEYWORDS)
            
            # 3. 중복 제거 (Vectorized)
            df['_SCORE'] = df.notna().sum(axis=1)
            df = df.sort_values('_SCORE', ascending=False)
            
            delete_mask = pd.Series([False]*len(df), index=df.index)
            
            # 벡터화된 중복 체크
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
            
            # 4. 마무리
            clean_df = flag_missing_info(clean_df, e_cols, p_cols, c_cols)
            clean_df = remove_sequence_columns(clean_df)
            if '_SCORE' in clean_df.columns: clean_df = clean_df.drop(columns=['_SCORE'])
            clean_df = clean_df.reset_index(drop=True)
            clean_df.index += 1
            
            cleaned_sheets[sheet_name] = clean_df
            
            # 인덱스 제외하고 저장
            clean_df.to_excel(writer, sheet_name=sheet_name, index=False)
            
        if trash_list:
            full_trash = pd.concat(trash_list)
            for origin, group in full_trash.groupby('[원본시트]'):
                safe_name = re.sub(r'[^\w]', '', origin)[:15]
                group.dropna(axis=1, how='all').to_excel(writer, sheet_name=f"휴지통_{safe_name}", index=False)
                
    return output_buffer, cleaned_sheets, trash_list, "Success"