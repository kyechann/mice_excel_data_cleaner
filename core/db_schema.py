import pandas as pd
import re

DB_SCHEMA_COLS = ["이름", "소속", "직함", "전화번호", "이메일", "참가구분", "등록일", "평점", "리뷰", "비고"]

DB_COL_ALIASES = {
    "이름": ["이름", "성명", "name", "full name", "이름(name)", "이름 (name)", "이름 (Name)", "이름(Name)"],
    "소속": ["소속", "회사", "기관", "부서", "company", "organization", "organisation",
           "소속(company)", "소속 (company)", "소속 (Company)", "소속(Company)"],
    "직함": ["직함", "직급", "직책", "job", "job title", "position", "title", "role"],
    "전화번호": ["전화번호", "휴대폰", "연락처", "phone", "mobile", "tel", "contact", "contact no", "contact no.",
             "휴대폰 (Phone)", "휴대폰(Phone)", "Contact No.", "Contact No", "Contact"],
    "이메일": ["이메일", "e-mail", "email", "email address", "mail",
            "이메일 (E-mail)", "이메일(E-mail)", "Email Address", "Email"],
    "참가구분": ["참가구분", "구분", "참가 유형", "참가유형", "type", "attendee type", "category", "registration type"],
    "등록일": ["등록일", "신청일", "접수일", "date", "registration date", "registered at", "created at", "created_at"],
    "평점": ["평점", "rating", "score", "점수", "평점(0-10)", "평점(0~10)", "nps", "satisfaction", "만족도"],
    "리뷰": ["리뷰", "review", "comment", "comments", "의견", "코멘트", "후기", "리뷰(코멘트)", "만족도_리뷰"],
    "비고": ["비고", "메모", "note", "notes", "remark", "remarks", "etc", "기타"],
}

def _norm_col(x: str) -> str:
    if x is None:
        return ""
    s = str(x).strip().lower()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[()\[\]{}<>]", "", s)
    s = s.replace(".", "").replace("-", "").replace("_", "")
    return s

def _build_alias_lookup():
    lookup = {}
    for canonical, aliases in DB_COL_ALIASES.items():
        for a in aliases:
            lookup[_norm_col(a)] = canonical
    for c in DB_SCHEMA_COLS:
        lookup[_norm_col(c)] = c
    return lookup

_ALIAS_LOOKUP = _build_alias_lookup()

def project_df_to_db_schema(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=DB_SCHEMA_COLS)

    rename_map = {}
    for col in df.columns:
        key = _norm_col(col)
        if key in _ALIAS_LOOKUP:
            canonical = _ALIAS_LOOKUP[key]
            if canonical not in rename_map.values():
                rename_map[col] = canonical

    df2 = df.rename(columns=rename_map).copy()

    out = pd.DataFrame()
    for c in DB_SCHEMA_COLS:
        out[c] = df2[c] if c in df2.columns else None

    out["전화번호"] = out["전화번호"].astype(str).str.strip().replace({"nan": None, "None": None})
    out["이메일"] = out["이메일"].astype(str).str.strip().str.lower().replace({"nan": None, "none": None})
    out["등록일"] = out["등록일"].astype(str).str.strip().replace({"nan": None, "None": None})

    out["평점"] = pd.to_numeric(out["평점"], errors="coerce")
    out["리뷰"] = out["리뷰"].astype(str).str.strip().replace({"nan": None, "None": None, "none": None})

    return out

def build_db_payload(cleaned_data: dict) -> dict:
    payload = {}
    for sheet_name, df in cleaned_data.items():
        payload[sheet_name] = project_df_to_db_schema(df)
    return payload