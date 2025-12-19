import pandas as pd
import re
import json
import os
import io
import difflib
import numpy as np

# =====================
# 설정 및 상수
# =====================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPPING_FILE = os.path.join(BASE_DIR, "data", "mapping_config.json")

EMAIL_KEYWORDS = ["이메일", "email", "e-mail", "mail"]
PHONE_KEYWORDS = ["전화", "phone", "tel", "mobile", "휴대폰", "연락처", "contact"]
NAME_KEYWORDS = ["이름", "성명", "name", "first name", "last name", "참가자", "full name", "representative", "대표자"]
COMPANY_KEYWORDS = ["회사", "소속", "company", "organization", "org", "firm", "agency", "부스", "booth", "업체"]
COUNTRY_KEYWORDS = ["국가", "나라", "country", "nation", "nationality", "region"]
REGION_KEYWORDS = ["지역", "city", "state", "province", "prefecture", "county"]

DEFAULT_MAPPING = {
    "삼성": "Samsung", "삼성전자": "Samsung", "samsungelectronics": "Samsung",
    "lg": "LG", "엘지": "LG", "현대": "Hyundai", "sk": "SK",
    "naver": "Naver", "kakao": "Kakao", "google": "Google", "apple": "Apple"
}

COUNTRY_TO_CC = {
    "대한민국": "82", "한국": "82",
    "미국": "1", "캐나다": "1",
    "일본": "81",
    "중국": "86",
    "홍콩": "852",
    "대만": "886",
    "싱가포르": "65",
    "태국": "66",
    "베트남": "84",
    "필리핀": "63",
    "인도네시아": "62",
    "말레이시아": "60",
    "영국": "44",
    "프랑스": "33",
    "독일": "49",
    "이탈리아": "39",
    "스페인": "34",
    "호주": "61",
}

KR_ALIASES = {"대한민국", "한국", "KR", "KOREA", "South Korea", "southkorea", "ROK"}

# =====================
# 매핑 관리 함수
# =====================
def load_mapping():
    if not os.path.exists(MAPPING_FILE):
        os.makedirs(os.path.dirname(MAPPING_FILE), exist_ok=True)
        with open(MAPPING_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_MAPPING, f, ensure_ascii=False, indent=4)
        return DEFAULT_MAPPING
    with open(MAPPING_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_mapping(new_mapping):
    with open(MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(new_mapping, f, ensure_ascii=False, indent=4)

# =====================
# 정제 헬퍼
# =====================
def get_columns_by_keywords(df, keywords):
    kws = [k.lower() for k in keywords]
    cols = []
    for col in df.columns:
        name = str(col).lower()

        # ✅ 내부/보조 컬럼은 키워드 감지에서 제외
        if name.startswith("_") or name.startswith("["):
            continue

        if any(k in name for k in kws):
            cols.append(col)
    return cols

def remove_sequence_columns(df):
    seq_keywords = ["no", "no.", "연번", "순번", "번호", "nr", "num"]
    cols = [c for c in df.columns if str(c).lower().strip() in seq_keywords]
    if cols:
        df = df.drop(columns=cols)
    return df

def normalize_phone_kr(raw):
    """+82/82/0082/10.../010... -> 010... (국내형 통일)"""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return pd.NA

    s = str(raw).strip()
    if not s or s.lower() in {"nan", "none"}:
        return pd.NA

    s = re.sub(r"[^\d+]", "", s)
    if s.startswith("00"):
        s = "+" + s[2:]

    digits = re.sub(r"\D", "", s)

    if s.startswith("+82"):
        rest = re.sub(r"\D", "", s[3:])
        if not rest:
            return pd.NA
        return rest if rest.startswith("0") else ("0" + rest)

    if digits.startswith("82") and len(digits) >= 11:
        rest = digits[2:]
        if not rest:
            return pd.NA
        return rest if rest.startswith("0") else ("0" + rest)

    if digits.startswith("010"):
        return digits

    if digits.startswith("10") and len(digits) in (10, 11):
        return "0" + digits

    if digits.startswith("0"):
        return digits

    return digits if digits else pd.NA

def normalize_phone_with_country(raw_phone, country_value):
    """
    - KR이면 010... 통일
    - 외국이면 +국가코드숫자... 통일
    """
    if raw_phone is None or (isinstance(raw_phone, float) and pd.isna(raw_phone)):
        return pd.NA

    s = str(raw_phone).strip()
    if not s or s.lower() in {"nan", "none"}:
        return pd.NA

    c = "" if country_value is None or (isinstance(country_value, float) and pd.isna(country_value)) else str(country_value).strip()

    # KR 처리
    if c in KR_ALIASES or c == "":
        return normalize_phone_kr(s)

    s = re.sub(r"[^\d+]", "", s)
    if s.startswith("00"):
        s = "+" + s[2:]

    if s.startswith("+"):
        return "+" + re.sub(r"\D", "", s[1:])

    digits = re.sub(r"\D", "", s)
    if not digits:
        return pd.NA

    cc = COUNTRY_TO_CC.get(c)
    if not cc:
        # 국가코드를 모르면: 길면 국제번호로 간주(+붙임), 아니면 그대로
        return ("+" + digits) if len(digits) >= 11 else digits

    if digits.startswith(cc):
        return "+" + digits

    if digits.startswith("0"):
        digits = digits[1:]

    return f"+{cc}{digits}"

def normalize_strings(df):
    mapping_dict = load_mapping()
    clean_mapping = {k.replace(" ", "").lower(): v for k, v in mapping_dict.items()}

    df = df.copy()

    # ✅ object 컬럼만 strip
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)

    # 국가 컬럼 미리 찾기(전화 컬럼에서 함께 참조)
    country_col = next((ccol for ccol in df.columns if any(k in str(ccol).lower() for k in COUNTRY_KEYWORDS)), None)

    for col in df.columns:
        c_lower = str(col).lower()

        # 회사명 정규화
        if any(k in c_lower for k in COMPANY_KEYWORDS):
            s = df[col].astype(str).str.lower()
            remove_pat = r"\(주\)|\(유\)|\(사\)|\(재\)|주식회사|\binc\.?|\bcorp\.?|\bltd\.?|\bkorea|\bkr"
            s = s.str.replace(remove_pat, "", regex=True)
            s = s.str.replace(r"[.,()\-\u00b7]", " ", regex=True).str.strip()
            s_lookup = s.str.replace(" ", "")
            mapped = s_lookup.map(clean_mapping).fillna(s.str.title())
            df[col] = np.where(df[col].isna(), df[col], mapped)

        # 국가명 정규화
        elif any(k in c_lower for k in COUNTRY_KEYWORDS):
            s = df[col].astype(str).str.lower().str.replace(" ", "").str.replace(".", "", regex=False)
            country_map = {
                "korea": "대한민국", "southkorea": "대한민국", "rok": "대한민국", "kr": "대한민국",
                "usa": "미국", "us": "미국", "america": "미국",
                "japan": "일본", "jp": "일본", "china": "중국", "cn": "중국"
            }
            df[col] = s.map(country_map).fillna(df[col].astype(str).str.strip())

        # 이름
        elif any(k in c_lower for k in NAME_KEYWORDS):
            df[col] = df[col].astype(str).str.title()

        # 이메일
        elif any(k in c_lower for k in EMAIL_KEYWORDS):
            s = df[col].astype(str).str.strip().str.lower()

            # ✅ 결측/쓰레기 문자열 제거
            s = s.replace({"nan": pd.NA, "none": pd.NA, "null": pd.NA, "": pd.NA})

            df[col] = s

        # 전화번호
        elif any(k in c_lower for k in PHONE_KEYWORDS):
            if "_PHONE_NOTE" not in df.columns:
                df["_PHONE_NOTE"] = ""

            if country_col:
                df[col] = df.apply(lambda r: normalize_phone_with_country(r[col], r[country_col]), axis=1)

                c_series = df[country_col].fillna("").astype(str).str.strip()
                phone_series = df[col].fillna("").astype(str).str.strip()

                is_foreign_like = phone_series.str.startswith("+") & ~phone_series.str.startswith("+82")
                missing_country = (c_series == "") & is_foreign_like
                df.loc[missing_country, "_PHONE_NOTE"] = (
                    df.loc[missing_country, "_PHONE_NOTE"].astype(str).replace("nan", "") +
                    np.where(df.loc[missing_country, "_PHONE_NOTE"].astype(str).str.len() > 0, " / ", "") +
                    "⚠️ 해외번호: 국가 미기입"
                )

                non_kr = ~c_series.isin(KR_ALIASES) & (c_series != "")
                unknown_cc = non_kr & ~c_series.isin(set(COUNTRY_TO_CC.keys()))
                has_phone = phone_series.str.len() > 0
                bad = unknown_cc & has_phone
                df.loc[bad, "_PHONE_NOTE"] = (
                    df.loc[bad, "_PHONE_NOTE"].astype(str).replace("nan", "") +
                    np.where(df.loc[bad, "_PHONE_NOTE"].astype(str).str.len() > 0, " / ", "") +
                    ("⚠️ 해외번호: 국가코드 매핑 없음(" + c_series[bad] + ")")
                )

                not_in_plus_format = non_kr & has_phone & ~phone_series.str.startswith("+")
                df.loc[not_in_plus_format, "_PHONE_NOTE"] = (
                    df.loc[not_in_plus_format, "_PHONE_NOTE"].astype(str).replace("nan", "") +
                    np.where(df.loc[not_in_plus_format, "_PHONE_NOTE"].astype(str).str.len() > 0, " / ", "") +
                    "⚠️ 해외번호: 형식 확인 필요(+국가코드)"
                )
            else:
                df[col] = df[col].apply(normalize_phone_kr)

            # ✅ 전화 컬럼 자체의 nan/none/'' 처리
            df[col] = df[col].replace({"nan": pd.NA, "none": pd.NA, "": pd.NA})

    # ✅ 전체 공통 정리
    df = df.replace(["", "nan", "NaN", "None", "NONE", "Nat"], pd.NA)
    df = df.dropna(how="all")
    return df

def flag_missing_info(df, email_cols, phone_cols, comp_cols):
    has_email = df[email_cols].notna().any(axis=1) if email_cols else pd.Series([False]*len(df), index=df.index)
    has_phone = df[phone_cols].notna().any(axis=1) if phone_cols else pd.Series([False]*len(df), index=df.index)
    has_comp = df[comp_cols].notna().any(axis=1) if comp_cols else pd.Series([False]*len(df), index=df.index)

    conditions = [
        (~has_email) & (~has_phone),
        (~has_email),
        (~has_phone),
    ]
    choices = [
        "⚠️ 이메일, 전화번호 누락",
        "이메일 누락",
        "전화번호 누락",
    ]

    contact_msg = np.select(conditions, choices, default="")
    comp_msg = np.where(~has_comp, "소속 누락", "")

    final_msg = pd.Series(contact_msg, index=df.index)
    mask_comp = comp_msg != ""
    mask_contact = final_msg != ""

    final_msg[mask_comp & mask_contact] = final_msg[mask_comp & mask_contact] + " / " + comp_msg[mask_comp & mask_contact]
    final_msg[mask_comp & ~mask_contact] = comp_msg[mask_comp & ~mask_contact]

    df["비고_상태체크"] = final_msg
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
                if "@" not in s: return s
                try:
                    id_part, domain = s.split("@", 1)
                    masked_id = id_part[0] + "**" if len(id_part) <= 2 else id_part[:2] + "**"
                    return masked_id + "@" + domain
                except:
                    return s
            df[col] = df[col].apply(mask_email)
    return df

def find_fuzzy_duplicates(df, cols, threshold=0.9):
    limit = 2000
    records = []
    for col in cols:
        if col not in df.columns:
            continue
        vals = df[col].dropna().astype(str).unique().tolist()
        if len(vals) > limit:
            continue
        seen = set()
        for i in range(len(vals)):
            for j in range(i + 1, len(vals)):
                a, b = vals[i], vals[j]
                if difflib.SequenceMatcher(None, a, b).ratio() >= threshold:
                    pair = tuple(sorted([a, b]))
                    if pair not in seen:
                        seen.add(pair)
                        records.append({"column": col, "val1": a, "val2": b})
    return pd.DataFrame(records)

def generate_message_column(df, template_text):
    df = df.copy()
    col_map = {}

    name_col = next((c for c in df.columns if any(k in str(c).lower() for k in NAME_KEYWORDS)), None)
    if name_col: col_map["{이름}"] = name_col

    comp_col = next((c for c in df.columns if any(k in str(c).lower() for k in COMPANY_KEYWORDS)), None)
    if comp_col: col_map["{소속}"] = comp_col

    phone_col = next((c for c in df.columns if any(k in str(c).lower() for k in PHONE_KEYWORDS)), None)
    if phone_col: col_map["{전화번호}"] = phone_col

    email_col = next((c for c in df.columns if any(k in str(c).lower() for k in EMAIL_KEYWORDS)), None)
    if email_col: col_map["{이메일}"] = email_col

    def apply_template(row):
        msg = template_text
        for placeholder, real_col in col_map.items():
            if placeholder in msg:
                val = str(row[real_col]) if pd.notna(row[real_col]) else ""
                msg = msg.replace(placeholder, val)

        for col in df.columns:
            exact = "{" + str(col) + "}"
            if exact in msg:
                val = str(row[col]) if pd.notna(row[col]) else ""
                msg = msg.replace(exact, val)
        return msg

    df["생성된_메시지"] = df.apply(apply_template, axis=1)
    return df

# =====================
# 메인 파이프라인
# =====================
def run_cleaning_pipeline(uploaded_file):
    try:
        try:
            import python_calamine  # noqa
            engine = "calamine"
        except ImportError:
            engine = "openpyxl"
        sheets = pd.read_excel(uploaded_file, sheet_name=None, dtype=object, engine=engine)
    except Exception as e:
        return None, None, None, str(e)

    cleaned_sheets = {}
    trash_list = []
    output_buffer = io.BytesIO()

    with pd.ExcelWriter(output_buffer, engine="xlsxwriter") as writer:
        for sheet_name, df in sheets.items():
            if df is None or df.empty:
                continue

            # 1) 정규화
            df = normalize_strings(df)

            # 2) 컬럼 감지
            e_cols = get_columns_by_keywords(df, EMAIL_KEYWORDS)
            p_cols = get_columns_by_keywords(df, PHONE_KEYWORDS)
            c_cols = get_columns_by_keywords(df, COMPANY_KEYWORDS)

            # 3) 중복 제거 (✅ delete_mask 항상 존재하도록)
            df["_SCORE"] = df.notna().sum(axis=1)
            df = df.sort_values("_SCORE", ascending=False)

            delete_mask = pd.Series(False, index=df.index)

            # ✅ 이메일: @ 포함 + 길이 최소
            for c in e_cols:
                s = df[c].fillna("").astype(str).str.strip().str.lower()
                valid = s.str.contains("@", na=False) & (s.str.len() >= 6)
                delete_mask |= (valid & df.duplicated(subset=[c], keep="first"))

            # ✅ 전화: 숫자만 뽑아서 9자리 이상일 때만 중복 판정
            for c in p_cols:
                s = df[c].fillna("").astype(str).str.replace(r"\D", "", regex=True)
                valid = s.str.len() >= 9
                delete_mask |= (valid & df.duplicated(subset=[c], keep="first"))

            trash_df = df.loc[delete_mask].copy()
            clean_df = df.loc[~delete_mask].copy()

            if not trash_df.empty:
                trash_df.insert(0, "[원본시트]", sheet_name)
                if "_SCORE" in trash_df.columns:
                    trash_df = trash_df.drop(columns=["_SCORE"])
                trash_list.append(trash_df)

            # 4) 마무리
            clean_df = flag_missing_info(clean_df, e_cols, p_cols, c_cols)
            clean_df = remove_sequence_columns(clean_df)

            if "_SCORE" in clean_df.columns:
                clean_df = clean_df.drop(columns=["_SCORE"])

            clean_df = clean_df.reset_index(drop=True)
            cleaned_sheets[sheet_name] = clean_df

            clean_df.to_excel(writer, sheet_name=sheet_name, index=False)

        # 휴지통 시트들
        if trash_list:
            full_trash = pd.concat(trash_list, ignore_index=True)
            if "[원본시트]" in full_trash.columns:
                for origin, group in full_trash.groupby("[원본시트]"):
                    safe_name = re.sub(r"[^\w]", "", str(origin))[:15]
                    group.dropna(axis=1, how="all").to_excel(
                        writer, sheet_name=f"휴지통_{safe_name}", index=False
                    )

    return output_buffer, cleaned_sheets, trash_list, "Success"