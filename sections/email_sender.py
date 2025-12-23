# sections/email_sender.py
import streamlit as st
import pandas as pd
import io
from datetime import datetime
import html

from modules import cleaner, mailer


# -----------------------------
# Config
# -----------------------------
MAX_TOTAL_ATTACH_MB = 24.0  # Gmail 25MB 근처 안전선(여유)


# -----------------------------
# Utils
# -----------------------------
def _is_valid_email(x) -> bool:
    s = "" if x is None else str(x).strip()
    if "@" not in s:
        return False
    try:
        domain = s.split("@", 1)[1]
        return "." in domain and len(domain) >= 3
    except Exception:
        return False


def _df_to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "selected") -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
        df.to_excel(w, sheet_name=str(sheet_name)[:31], index=False)
    return buf.getvalue()


def _df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def _run_sql_on_df(df: pd.DataFrame, query: str) -> pd.DataFrame:
    q = (query or "").strip().rstrip(";")
    if not q:
        raise ValueError("SQL 쿼리가 비어있습니다.")
    if not q.lower().startswith("select"):
        raise ValueError("보안상 SELECT 쿼리만 허용됩니다.")

    try:
        import duckdb  # type: ignore
        con = duckdb.connect(database=":memory:")
        con.register("data", df)
        out = con.execute(q).df()
        con.close()
        return out
    except Exception:
        import sqlite3
        con = sqlite3.connect(":memory:")
        df.to_sql("data", con, index=False, if_exists="replace")
        out = pd.read_sql_query(q, con)
        con.close()
        return out


def _ensure_rowid_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    ✅ 선택 유지 핵심:
    - rowid가 index/변동컬럼(생성된_메시지/선택) 변화에 영향을 받지 않도록
      "내용 기반 + index 비의존 + 변동 컬럼 제외"로 생성
    """
    out = df.copy()

    if "__rowid__" in out.columns:
        return out.set_index("__rowid__", drop=True)

    volatile_cols = {"선택", "생성된_메시지", "__rowid__"}
    stable_cols = [c for c in out.columns if c not in volatile_cols]
    if not stable_cols:
        stable_cols = list(out.columns)

    rid = pd.util.hash_pandas_object(out[stable_cols], index=False).astype("uint64").astype(str)
    out["__rowid__"] = rid
    return out.set_index("__rowid__", drop=True)


def _attachments_from_uploads(uploaded_files):
    payload = []
    if not uploaded_files:
        return payload
    for f in uploaded_files:
        try:
            payload.append((f.name, f.getvalue(), getattr(f, "type", None)))
        except Exception:
            continue
    return payload


def _attachments_total_bytes(payload) -> int:
    return int(
        sum(
            len(p[1])
            for p in (payload or [])
            if isinstance(p, (list, tuple)) and len(p) >= 2 and p[1]
        )
    )


def _mb(n_bytes: int) -> float:
    return float(n_bytes) / (1024.0 * 1024.0)


def _build_dataset_attachment(df: pd.DataFrame, fmt: str, base_name: str):
    safe_base = (base_name or "dataset").strip().replace(" ", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    df2 = df.drop(columns=["__rowid__"], errors="ignore")

    if fmt == "xlsx":
        b = _df_to_xlsx_bytes(df2, sheet_name="data")
        return (
            f"{safe_base}_{ts}.xlsx",
            b,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        b = _df_to_csv_bytes(df2)
        return (f"{safe_base}_{ts}.csv", b, "text/csv")


def _check_attach_size(payload):
    total = _attachments_total_bytes(payload)
    if _mb(total) > MAX_TOTAL_ATTACH_MB:
        return False, total
    return True, total

def _render_message_cards(df: pd.DataFrame, msg_col: str = "생성된_메시지", n: int = 1, cols: int = 1):
    if df is None or df.empty or msg_col not in df.columns:
        st.info("미리볼 메시지가 없습니다.")
        return

    msgs = (
        df[msg_col]
        .dropna()
        .astype(str)
        .head(n)
        .tolist()
    )
    if not msgs:
        st.info("미리볼 메시지가 없습니다.")
        return

    # ✅ 카드 CSS (한 번만 주입)
    st.markdown(
        """
        <style>
        .msg-card{
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.10);
            border-radius: 18px;
            padding: 18px 18px 14px 18px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.35);
            margin: 10px 0 16px 0;
        }
        .msg-title{
            font-size: 16px;
            font-weight: 800;
            opacity: 0.9;
            margin-bottom: 10px;
        }
        .msg-pre{
            white-space: pre-wrap;
            word-break: break-word;
            font-size: 15px;
            line-height: 1.6;
            margin: 0;
        }
        </style>
        """,
        unsafe_allow_html=True,  # ✅ 핵심
    )

    # cols=1로 쓰면 하나만 예쁘게
    for i, m in enumerate(msgs, start=1):
        safe = html.escape(m)  # ✅ 메시지에 < > 가 있어도 안전하게
        st.markdown(
            f"""
            <div class="msg-card">
              <pre class="msg-pre">{safe}</pre>
            </div>
            """,
            unsafe_allow_html=True,  # ✅ 핵심
        )

# -----------------------------
# Main UI
# -----------------------------
def render_email_sender(view_df: pd.DataFrame, base_df: pd.DataFrame, key_prefix: str = "MAIL"):
    kp = key_prefix or "MAIL"

    # session keys
    MAIL_DF_KEY = f"{kp}_MAIL_DF"
    SQL_TEXT_KEY = f"{kp}_SQL_TEXT"
    SQL_PREVIEW_KEY = f"{kp}_SQL_PREVIEW_DF"
    SQL_APPLIED_KEY = f"{kp}_SQL_APPLIED"
    SQL_ERR_KEY = f"{kp}_SQL_ERR"
    VER_KEY = f"{kp}_VER"
    SEGMENTS_KEY = f"{kp}_SEGMENTS"
    SELECTED_IDS_KEY = f"{kp}_SELECTED_IDS"
    ATTACH_PAYLOAD_KEY = f"{kp}_ATTACH_PAYLOAD"
    TMPL_KEY = f"{kp}_TEMPLATE"

    # ✅ 내부/테스트 모드 토글(자동첨부 노출 제어)
    INTERNAL_MODE_KEY = f"{kp}_INTERNAL_MODE"
    AUTO_ATTACH_MODE_KEY = f"{kp}_AUTO_ATTACH_MODE"
    AUTO_ATTACH_FMT_KEY = f"{kp}_AUTO_ATTACH_FMT"
    AUTO_ATTACH_NAME_KEY = f"{kp}_AUTO_ATTACH_NAME"

    # init
    if VER_KEY not in st.session_state:
        st.session_state[VER_KEY] = 0
    if SEGMENTS_KEY not in st.session_state:
        st.session_state[SEGMENTS_KEY] = {}
    if SELECTED_IDS_KEY not in st.session_state:
        st.session_state[SELECTED_IDS_KEY] = set()
    if ATTACH_PAYLOAD_KEY not in st.session_state:
        st.session_state[ATTACH_PAYLOAD_KEY] = []
    if SQL_APPLIED_KEY not in st.session_state:
        st.session_state[SQL_APPLIED_KEY] = False
    if INTERNAL_MODE_KEY not in st.session_state:
        st.session_state[INTERNAL_MODE_KEY] = False

    # base_send_df: 템플릿 적용본 우선, 없으면 view_df
    base_send_df = st.session_state.get(MAIL_DF_KEY, None)
    if base_send_df is None:
        base_send_df = view_df

    # send_df: SQL 적용 결과 우선
    send_df = base_send_df
    if st.session_state.get(SQL_APPLIED_KEY) and st.session_state.get(SQL_PREVIEW_KEY) is not None:
        send_df = st.session_state[SQL_PREVIEW_KEY]

    # rowid 기반 선택 유지
    editor_source = _ensure_rowid_index(send_df)
    all_ids = list(editor_source.index.astype(str))
    st.session_state[SELECTED_IDS_KEY] = set(st.session_state[SELECTED_IDS_KEY]).intersection(set(all_ids))

    def _compose_attachments_common(send_df_local: pd.DataFrame, selected_df_local: pd.DataFrame):
        """
        업로드 첨부 + (내부모드일 때만) 데이터셋 자동첨부 옵션
        """
        payload = list(st.session_state.get(ATTACH_PAYLOAD_KEY, []))

        if not st.session_state.get(INTERNAL_MODE_KEY, False):
            return payload

        mode_pick = st.session_state.get(AUTO_ATTACH_MODE_KEY, "안함")
        if mode_pick == "안함":
            return payload

        fmt = st.session_state.get(AUTO_ATTACH_FMT_KEY, "xlsx")
        name = st.session_state.get(AUTO_ATTACH_NAME_KEY, "mail_targets")

        if str(mode_pick).startswith("선택"):
            df_attach = selected_df_local
            base_name = f"{name}_selected"
        else:
            df_attach = send_df_local.reset_index(drop=True)
            base_name = f"{name}_all"

        if df_attach is None or df_attach.empty:
            return payload

        payload.append(_build_dataset_attachment(df_attach, fmt, base_name))
        return payload

    with st.expander("📧 메일/문자 템플릿 & 발송", expanded=False):
        st.info(f"사용 가능 변수: {', '.join([f'{{{c}}}' for c in base_df.columns])}")

        t_seg, t_tmpl, t_send, t_pick = st.tabs(
            ["① 세그먼트(SQL)", "② 템플릿", "③ 발송 설정/테스트", "④ 대상 선택/발송"]
        )

        # =========================================================
        # ① 세그먼트(SQL)
        # =========================================================
        with t_seg:
            st.caption("테이블 이름은 항상 `data` 입니다. (보안상 SELECT만 허용)")
            with st.expander("컬럼 목록 보기", expanded=False):
                st.code(", ".join([str(c) for c in base_send_df.columns]))

            default_sql = "SELECT * FROM data LIMIT 200"
            sql = st.text_area(
                "SQL 쿼리",
                value=st.session_state.get(SQL_TEXT_KEY, default_sql),
                height=120,
                key=f"{kp}_SQL_TEXTAREA",
            )
            st.session_state[SQL_TEXT_KEY] = sql

            cA, cB = st.columns([1, 1], gap="small")
            with cA:
                seg_name = st.text_input("세그먼트 이름(저장용)", key=f"{kp}_SEG_NAME", placeholder="예: VIP_2025Q4")
                if st.button("세그먼트 저장", use_container_width=True, key=f"{kp}_SEG_SAVE"):
                    name = (seg_name or "").strip()
                    if not name:
                        st.warning("세그먼트 이름을 입력하세요.")
                    else:
                        st.session_state[SEGMENTS_KEY][name] = st.session_state[SQL_TEXT_KEY]
                        st.toast(f"✅ 저장됨: {name}", icon="✅")

            with cB:
                saved = list(st.session_state[SEGMENTS_KEY].keys())
                pick = st.selectbox("저장된 세그먼트 불러오기", options=["(선택)"] + saved, key=f"{kp}_SEG_PICK")
                col_load, col_del = st.columns([1, 1], gap="small")
                with col_load:
                    if st.button("불러오기", use_container_width=True, key=f"{kp}_SEG_LOAD"):
                        if pick != "(선택)":
                            st.session_state[SQL_TEXT_KEY] = st.session_state[SEGMENTS_KEY][pick]
                            st.toast(f"📌 불러옴: {pick}", icon="📌")
                            st.rerun()
                with col_del:
                    if st.button("삭제", use_container_width=True, key=f"{kp}_SEG_DEL"):
                        if pick != "(선택)":
                            st.session_state[SEGMENTS_KEY].pop(pick, None)
                            st.toast(f"🗑️ 삭제됨: {pick}", icon="🗑️")
                            st.rerun()

            st.markdown("---")
            c1, c2, c3 = st.columns([1, 1, 1], gap="small")

            with c1:
                if st.button("미리보기 실행", use_container_width=True, key=f"{kp}_SQL_RUN"):
                    try:
                        out = _run_sql_on_df(base_send_df, st.session_state[SQL_TEXT_KEY])
                        st.session_state[SQL_PREVIEW_KEY] = out
                        st.session_state[SQL_ERR_KEY] = ""
                        st.success(f"쿼리 성공: {len(out):,} rows")
                    except Exception as e:
                        st.session_state[SQL_ERR_KEY] = str(e)
                        st.error(f"SQL 오류: {e}")

            with c2:
                if st.button("발송 대상으로 적용", type="primary", use_container_width=True, key=f"{kp}_SQL_APPLY"):
                    if st.session_state.get(SQL_PREVIEW_KEY) is None:
                        st.warning("먼저 '미리보기 실행'으로 결과를 만든 뒤 적용하세요.")
                    else:
                        st.session_state[SQL_APPLIED_KEY] = True
                        st.session_state[VER_KEY] += 1
                        st.toast("✅ SQL 결과가 발송 대상으로 적용되었습니다.", icon="✅")
                        st.rerun()

            with c3:
                if st.button("SQL 적용 해제", use_container_width=True, key=f"{kp}_SQL_RESET"):
                    st.session_state[SQL_APPLIED_KEY] = False
                    st.session_state.pop(SQL_PREVIEW_KEY, None)
                    st.session_state.pop(SQL_ERR_KEY, None)
                    st.session_state[VER_KEY] += 1
                    st.toast("↩️ SQL 적용 해제됨 (원래 데이터로 복귀)", icon="↩️")
                    st.rerun()

            err_msg = st.session_state.get(SQL_ERR_KEY, "")
            if err_msg:
                st.warning(f"마지막 SQL 오류: {err_msg}")

            if st.session_state.get(SQL_PREVIEW_KEY) is not None:
                st.markdown("**SQL 결과 미리보기**")
                st.dataframe(st.session_state[SQL_PREVIEW_KEY].head(200), use_container_width=True, hide_index=True)

        # =========================================================
        # ② 템플릿
        # =========================================================
        with t_tmpl:
            default_msg = """[MICE 2025 컨퍼런스] 사전등록 확정 안내

안녕하세요, {이름}님.
신청해주신 내용으로 등록이 정상적으로 완료되었습니다.

▶ 소속: {소속}
▶ 연락처: {전화번호}

행사 당일, 등록데스크에서 본 메시지를 보여주시면 명찰을 수령하실 수 있습니다.
감사합니다."""
            if TMPL_KEY not in st.session_state:
                st.session_state[TMPL_KEY] = default_msg

            st.markdown("#### 🧾 템플릿 내용")
            tmpl = st.text_area(
                "템플릿 내용",
                value=st.session_state[TMPL_KEY],
                height=260,
                label_visibility="collapsed",
                key=f"{kp}_TEMPLATE_TEXTAREA",
            )
            st.session_state[TMPL_KEY] = tmpl

            # 최신 send_df 재계산
            base2 = st.session_state.get(MAIL_DF_KEY, None)
            base2 = base2 if base2 is not None else view_df
            send2 = base2
            if st.session_state.get(SQL_APPLIED_KEY) and st.session_state.get(SQL_PREVIEW_KEY) is not None:
                send2 = st.session_state[SQL_PREVIEW_KEY]

            if st.button(
                "템플릿 적용 (현재 발송대상에 생성된_메시지 추가)",
                type="primary",
                use_container_width=True,
                key=f"{kp}_APPLY_TEMPLATE",
            ):
                try:
                    out = cleaner.generate_message_column(send2, tmpl)
                    st.session_state[MAIL_DF_KEY] = out
                    if st.session_state.get(SQL_APPLIED_KEY):
                        st.session_state[SQL_PREVIEW_KEY] = out
                    st.session_state[VER_KEY] += 1
                    st.toast("✅ 생성된_메시지 생성 완료!", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"생성 실패: {e}")

            if "생성된_메시지" in send2.columns:
                st.markdown("---")
                st.markdown("#### 미리보기(상위 3명)")

                # ✅ 템플릿 카드처럼 보여주기
                _render_message_cards(send2, msg_col="생성된_메시지", n=3, cols=1)  # 1단 카드
                # _render_message_cards(send2, msg_col="생성된_메시지", n=4, cols=2) # 2단 카드 원하면 이걸로
            else:
                st.info("아직 '생성된_메시지'가 없습니다. 위에서 템플릿 적용을 눌러주세요.")
                
# sections/email_sender.py
import streamlit as st
import pandas as pd
import io
from datetime import datetime

from modules import cleaner, mailer


# -----------------------------
# Config
# -----------------------------
MAX_TOTAL_ATTACH_MB = 24.0  # Gmail 25MB 근처 안전선(여유)


# -----------------------------
# Utils
# -----------------------------
def _is_valid_email(x) -> bool:
    s = "" if x is None else str(x).strip()
    if "@" not in s:
        return False
    try:
        domain = s.split("@", 1)[1]
        return "." in domain and len(domain) >= 3
    except Exception:
        return False


def _df_to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "selected") -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
        df.to_excel(w, sheet_name=str(sheet_name)[:31], index=False)
    return buf.getvalue()


def _df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def _run_sql_on_df(df: pd.DataFrame, query: str) -> pd.DataFrame:
    q = (query or "").strip().rstrip(";")
    if not q:
        raise ValueError("SQL 쿼리가 비어있습니다.")
    if not q.lower().startswith("select"):
        raise ValueError("보안상 SELECT 쿼리만 허용됩니다.")

    try:
        import duckdb  # type: ignore
        con = duckdb.connect(database=":memory:")
        con.register("data", df)
        out = con.execute(q).df()
        con.close()
        return out
    except Exception:
        import sqlite3
        con = sqlite3.connect(":memory:")
        df.to_sql("data", con, index=False, if_exists="replace")
        out = pd.read_sql_query(q, con)
        con.close()
        return out


def _ensure_rowid_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    ✅ 선택 유지 핵심:
    - rowid가 index/변동컬럼(생성된_메시지/선택) 변화에 영향을 받지 않도록
      "내용 기반 + index 비의존 + 변동 컬럼 제외"로 생성
    """
    out = df.copy()

    if "__rowid__" in out.columns:
        return out.set_index("__rowid__", drop=True)

    volatile_cols = {"선택", "생성된_메시지", "__rowid__"}
    stable_cols = [c for c in out.columns if c not in volatile_cols]
    if not stable_cols:
        stable_cols = list(out.columns)

    rid = pd.util.hash_pandas_object(out[stable_cols], index=False).astype("uint64").astype(str)
    out["__rowid__"] = rid
    return out.set_index("__rowid__", drop=True)


def _attachments_from_uploads(uploaded_files):
    payload = []
    if not uploaded_files:
        return payload
    for f in uploaded_files:
        try:
            payload.append((f.name, f.getvalue(), getattr(f, "type", None)))
        except Exception:
            continue
    return payload


def _attachments_total_bytes(payload) -> int:
    return int(
        sum(
            len(p[1])
            for p in (payload or [])
            if isinstance(p, (list, tuple)) and len(p) >= 2 and p[1]
        )
    )


def _mb(n_bytes: int) -> float:
    return float(n_bytes) / (1024.0 * 1024.0)


def _build_dataset_attachment(df: pd.DataFrame, fmt: str, base_name: str):
    safe_base = (base_name or "dataset").strip().replace(" ", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    df2 = df.drop(columns=["__rowid__"], errors="ignore")

    if fmt == "xlsx":
        b = _df_to_xlsx_bytes(df2, sheet_name="data")
        return (
            f"{safe_base}_{ts}.xlsx",
            b,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        b = _df_to_csv_bytes(df2)
        return (f"{safe_base}_{ts}.csv", b, "text/csv")


def _check_attach_size(payload):
    total = _attachments_total_bytes(payload)
    if _mb(total) > MAX_TOTAL_ATTACH_MB:
        return False, total
    return True, total


# -----------------------------
# Main UI
# -----------------------------
def render_email_sender(view_df: pd.DataFrame, base_df: pd.DataFrame, key_prefix: str = "MAIL"):
    kp = key_prefix or "MAIL"

    # session keys
    MAIL_DF_KEY = f"{kp}_MAIL_DF"
    SQL_TEXT_KEY = f"{kp}_SQL_TEXT"
    SQL_PREVIEW_KEY = f"{kp}_SQL_PREVIEW_DF"
    SQL_APPLIED_KEY = f"{kp}_SQL_APPLIED"
    SQL_ERR_KEY = f"{kp}_SQL_ERR"
    VER_KEY = f"{kp}_VER"
    SEGMENTS_KEY = f"{kp}_SEGMENTS"
    SELECTED_IDS_KEY = f"{kp}_SELECTED_IDS"
    ATTACH_PAYLOAD_KEY = f"{kp}_ATTACH_PAYLOAD"
    TMPL_KEY = f"{kp}_TEMPLATE"

    # 내부/테스트 모드
    INTERNAL_MODE_KEY = f"{kp}_INTERNAL_MODE"
    AUTO_ATTACH_MODE_KEY = f"{kp}_AUTO_ATTACH_MODE"
    AUTO_ATTACH_FMT_KEY = f"{kp}_AUTO_ATTACH_FMT"
    AUTO_ATTACH_NAME_KEY = f"{kp}_AUTO_ATTACH_NAME"

    # init
    if VER_KEY not in st.session_state:
        st.session_state[VER_KEY] = 0
    if SEGMENTS_KEY not in st.session_state:
        st.session_state[SEGMENTS_KEY] = {}
    if SELECTED_IDS_KEY not in st.session_state:
        st.session_state[SELECTED_IDS_KEY] = set()
    if ATTACH_PAYLOAD_KEY not in st.session_state:
        st.session_state[ATTACH_PAYLOAD_KEY] = []
    if SQL_APPLIED_KEY not in st.session_state:
        st.session_state[SQL_APPLIED_KEY] = False
    if INTERNAL_MODE_KEY not in st.session_state:
        st.session_state[INTERNAL_MODE_KEY] = False

    # base_send_df: 템플릿 적용본 우선, 없으면 view_df
    base_send_df = st.session_state.get(MAIL_DF_KEY, None)
    if base_send_df is None:
        base_send_df = view_df

    # send_df: SQL 적용 결과 우선
    send_df = base_send_df
    if st.session_state.get(SQL_APPLIED_KEY) and st.session_state.get(SQL_PREVIEW_KEY) is not None:
        send_df = st.session_state[SQL_PREVIEW_KEY]

    # rowid 기반 선택 유지
    editor_source = _ensure_rowid_index(send_df)
    all_ids = list(editor_source.index.astype(str))
    st.session_state[SELECTED_IDS_KEY] = set(st.session_state[SELECTED_IDS_KEY]).intersection(set(all_ids))

    with st.expander("📧 메일/문자 템플릿 & 발송", expanded=False):
        st.info(f"사용 가능 변수: {', '.join([f'{{{c}}}' for c in base_df.columns])}")

        t_seg, t_tmpl, t_send, t_pick = st.tabs(
            ["① 세그먼트(SQL)", "② 템플릿", "③ 발송 설정/테스트", "④ 대상 선택/발송"]
        )

        # =========================================================
        # ① 세그먼트(SQL)
        # =========================================================
        with t_seg:
            st.caption("테이블 이름은 항상 `data` 입니다. (보안상 SELECT만 허용)")
            with st.expander("컬럼 목록 보기", expanded=False):
                st.code(", ".join([str(c) for c in base_send_df.columns]))

            default_sql = "SELECT * FROM data LIMIT 200"
            sql = st.text_area(
                "SQL 쿼리",
                value=st.session_state.get(SQL_TEXT_KEY, default_sql),
                height=120,
                key=f"{kp}_SQL_TEXTAREA",
            )
            st.session_state[SQL_TEXT_KEY] = sql

            cA, cB = st.columns([1, 1], gap="small")
            with cA:
                seg_name = st.text_input("세그먼트 이름(저장용)", key=f"{kp}_SEG_NAME", placeholder="예: VIP_2025Q4")
                if st.button("세그먼트 저장", use_container_width=True, key=f"{kp}_SEG_SAVE"):
                    name = (seg_name or "").strip()
                    if not name:
                        st.warning("세그먼트 이름을 입력하세요.")
                    else:
                        st.session_state[SEGMENTS_KEY][name] = st.session_state[SQL_TEXT_KEY]
                        st.toast(f"✅ 저장됨: {name}", icon="✅")

            with cB:
                saved = list(st.session_state[SEGMENTS_KEY].keys())
                pick = st.selectbox("저장된 세그먼트 불러오기", options=["(선택)"] + saved, key=f"{kp}_SEG_PICK")
                col_load, col_del = st.columns([1, 1], gap="small")
                with col_load:
                    if st.button("불러오기", use_container_width=True, key=f"{kp}_SEG_LOAD"):
                        if pick != "(선택)":
                            st.session_state[SQL_TEXT_KEY] = st.session_state[SEGMENTS_KEY][pick]
                            st.toast(f"📌 불러옴: {pick}", icon="📌")
                            st.rerun()
                with col_del:
                    if st.button("삭제", use_container_width=True, key=f"{kp}_SEG_DEL"):
                        if pick != "(선택)":
                            st.session_state[SEGMENTS_KEY].pop(pick, None)
                            st.toast(f"🗑️ 삭제됨: {pick}", icon="🗑️")
                            st.rerun()

            st.markdown("---")
            c1, c2, c3 = st.columns([1, 1, 1], gap="small")

            with c1:
                if st.button("미리보기 실행", use_container_width=True, key=f"{kp}_SQL_RUN"):
                    try:
                        out = _run_sql_on_df(base_send_df, st.session_state[SQL_TEXT_KEY])
                        st.session_state[SQL_PREVIEW_KEY] = out
                        st.session_state[SQL_ERR_KEY] = ""
                        st.success(f"쿼리 성공: {len(out):,} rows")
                    except Exception as e:
                        st.session_state[SQL_ERR_KEY] = str(e)
                        st.error(f"SQL 오류: {e}")

            with c2:
                if st.button("발송 대상으로 적용", type="primary", use_container_width=True, key=f"{kp}_SQL_APPLY"):
                    if st.session_state.get(SQL_PREVIEW_KEY) is None:
                        st.warning("먼저 '미리보기 실행'으로 결과를 만든 뒤 적용하세요.")
                    else:
                        st.session_state[SQL_APPLIED_KEY] = True
                        st.session_state[VER_KEY] += 1
                        st.toast("✅ SQL 결과가 발송 대상으로 적용되었습니다.", icon="✅")
                        st.rerun()

            with c3:
                if st.button("SQL 적용 해제", use_container_width=True, key=f"{kp}_SQL_RESET"):
                    st.session_state[SQL_APPLIED_KEY] = False
                    st.session_state.pop(SQL_PREVIEW_KEY, None)
                    st.session_state.pop(SQL_ERR_KEY, None)
                    st.session_state[VER_KEY] += 1
                    st.toast("↩️ SQL 적용 해제됨 (원래 데이터로 복귀)", icon="↩️")
                    st.rerun()

            err_msg = st.session_state.get(SQL_ERR_KEY, "")
            if err_msg:
                st.warning(f"마지막 SQL 오류: {err_msg}")

            if st.session_state.get(SQL_PREVIEW_KEY) is not None:
                st.markdown("**SQL 결과 미리보기**")
                st.dataframe(st.session_state[SQL_PREVIEW_KEY].head(200), use_container_width=True, hide_index=True)

        # =========================================================
        # ② 템플릿
        # =========================================================
        with t_tmpl:
            default_msg = """[MICE 2025 컨퍼런스] 사전등록 확정 안내

안녕하세요, {이름}님.
신청해주신 내용으로 등록이 정상적으로 완료되었습니다.

▶ 소속: {소속}
▶ 연락처: {전화번호}

행사 당일, 등록데스크에서 본 메시지를 보여주시면 명찰을 수령하실 수 있습니다.
감사합니다."""
            if TMPL_KEY not in st.session_state:
                st.session_state[TMPL_KEY] = default_msg

            st.markdown("#### 🧾 템플릿 내용")
            tmpl = st.text_area(
                "템플릿 내용",
                value=st.session_state[TMPL_KEY],
                height=260,
                label_visibility="collapsed",
                key=f"{kp}_TEMPLATE_TEXTAREA",
            )
            st.session_state[TMPL_KEY] = tmpl

            base2 = st.session_state.get(MAIL_DF_KEY, None)
            base2 = base2 if base2 is not None else view_df
            send2 = base2
            if st.session_state.get(SQL_APPLIED_KEY) and st.session_state.get(SQL_PREVIEW_KEY) is not None:
                send2 = st.session_state[SQL_PREVIEW_KEY]

            if st.button(
                "템플릿 적용 (현재 발송대상에 생성된_메시지 추가)",
                type="primary",
                use_container_width=True,
                key=f"{kp}_APPLY_TEMPLATE",
            ):
                try:
                    out = cleaner.generate_message_column(send2, tmpl)
                    st.session_state[MAIL_DF_KEY] = out
                    if st.session_state.get(SQL_APPLIED_KEY):
                        st.session_state[SQL_PREVIEW_KEY] = out
                    st.session_state[VER_KEY] += 1
                    st.toast("✅ 생성된_메시지 생성 완료!", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"생성 실패: {e}")

            if "생성된_메시지" in send2.columns:
                st.markdown("---")
                st.markdown("#### 미리보기")
                _render_message_cards(send2, msg_col="생성된_메시지", n=1, cols=1) 
            else:
                st.info("아직 '생성된_메시지'가 없습니다. 위에서 템플릿 적용을 눌러주세요.")

        # =========================================================
        # ③ 발송 설정/테스트  ✅ (미리보기는 ④로 이동)
        # =========================================================
        with t_send:
            base3 = st.session_state.get(MAIL_DF_KEY, None)
            base3 = base3 if base3 is not None else view_df
            send3 = base3
            if st.session_state.get(SQL_APPLIED_KEY) and st.session_state.get(SQL_PREVIEW_KEY) is not None:
                send3 = st.session_state[SQL_PREVIEW_KEY]

            # 선택된 row들(자동첨부에 사용 가능)
            ed3 = _ensure_rowid_index(send3)
            all3 = list(ed3.index.astype(str))
            st.session_state[SELECTED_IDS_KEY] = set(st.session_state[SELECTED_IDS_KEY]).intersection(set(all3))
            selected_ids = st.session_state.get(SELECTED_IDS_KEY, set())
            selected_df = ed3.loc[list(selected_ids)].reset_index(drop=True) if selected_ids else pd.DataFrame(columns=send3.columns)

            has_msg = ("생성된_메시지" in send3.columns)

            st.markdown("#### 발송 설정")
            st.text_input("SMTP 서버", value="smtp.gmail.com", key="SMTP_HOST")
            st.number_input("포트", value=465, step=1, key="SMTP_PORT")

            st.markdown("---")
            st.markdown("#### 📨 계정 설정")
            st.caption("💡 Gmail은 **앱 비밀번호(16자리)** 를 사용해야 합니다.")
            st.text_input("보내는 메일 주소", key="SMTP_SENDER_EMAIL", placeholder="myname@gmail.com")
            st.text_input("앱 비밀번호(16자리)", type="password", key="SMTP_SENDER_PW")
            st.text_input("메일 제목", value="[MICE 2025] 등록 안내", key=f"{kp}_MAIL_SUBJECT")

            mail_cols = [c for c in send3.columns if ("이메일" in str(c)) or ("email" in str(c).lower())]
            if not mail_cols:
                st.warning("⚠️ 이메일 컬럼을 찾지 못했습니다. (컬럼명에 '이메일' 또는 'email' 포함 필요)")
                st.stop()

            default_idx = list(send3.columns).index(mail_cols[0])
            st.selectbox(
                "받는 사람 이메일 컬럼",
                options=list(send3.columns),
                index=default_idx,
                key=f"{kp}_EMAIL_COL",
            )

            st.markdown("---")
            st.markdown("#### 📎 첨부파일")
            uploaded_attachments = st.file_uploader(
                "첨부파일 업로드 (여러 개 가능)",
                accept_multiple_files=True,
                key=f"{kp}_attachments_uploader",
            )
            st.session_state[ATTACH_PAYLOAD_KEY] = _attachments_from_uploads(uploaded_attachments)
            base_attach = st.session_state.get(ATTACH_PAYLOAD_KEY, [])
            if base_attach:
                st.caption(f"업로드 첨부 {len(base_attach)}개 (총 {_mb(_attachments_total_bytes(base_attach)):.2f} MB)")

            st.markdown("---")
            st.markdown("#### 🛡️ 내부/테스트 모드")
            internal_mode = st.toggle(
                "내부/테스트 모드 (운영자용 고급 옵션 표시)",
                value=st.session_state.get(INTERNAL_MODE_KEY, False),
                key=INTERNAL_MODE_KEY,
                help="고객/참관객 발송은 OFF 권장. 데이터셋 자동첨부 같은 내부 기능이 숨겨집니다.",
            )
            if not internal_mode:
                st.session_state[AUTO_ATTACH_MODE_KEY] = "안함"

            if internal_mode:
                st.markdown("---")
                st.markdown("#### 🧷 데이터셋 자동 첨부 (내부/테스트 모드에서만 표시 / 기본 OFF)")
                st.radio(
                    "자동 첨부 대상",
                    options=["안함", "선택 대상(체크된 사람)", "전체 발송 대상(SQL/필터 반영)"],
                    index=0,
                    horizontal=True,
                    key=AUTO_ATTACH_MODE_KEY,
                )
                st.radio(
                    "파일 형식",
                    options=["xlsx", "csv"],
                    index=0,
                    horizontal=True,
                    key=AUTO_ATTACH_FMT_KEY,
                )
                st.text_input("자동 첨부 파일명(베이스)", value="mail_targets", key=AUTO_ATTACH_NAME_KEY)

            def _compose_attachments(send_df_local: pd.DataFrame, selected_df_local: pd.DataFrame):
                payload = list(st.session_state.get(ATTACH_PAYLOAD_KEY, []))

                if not st.session_state.get(INTERNAL_MODE_KEY, False):
                    return payload

                mode_pick = st.session_state.get(AUTO_ATTACH_MODE_KEY, "안함")
                if mode_pick == "안함":
                    return payload

                fmt = st.session_state.get(AUTO_ATTACH_FMT_KEY, "xlsx")
                name = st.session_state.get(AUTO_ATTACH_NAME_KEY, "mail_targets")

                if mode_pick.startswith("선택"):
                    df_attach = selected_df_local
                    base_name = f"{name}_selected"
                else:
                    df_attach = send_df_local.reset_index(drop=True)
                    base_name = f"{name}_all"

                if df_attach is None or df_attach.empty:
                    return payload

                payload.append(_build_dataset_attachment(df_attach, fmt, base_name))
                return payload

            # ---------- 테스트 발송 ----------
            st.markdown("---")
            st.markdown("### ✅ 테스트 발송 (최대 5명)")

            if not has_msg:
                st.warning("먼저 ② 탭에서 템플릿을 적용해 '생성된_메시지'를 만든 뒤 테스트 발송이 가능합니다.")

            test_receivers_text = st.text_area(
                "테스트 받는 사람 이메일들 (줄바꿈/쉼표로 여러 개 가능)",
                key=f"{kp}_TEST_RECEIVERS",
                placeholder="a@example.com\nb@example.com",
                height=90,
            )

            if st.button(
                "테스트 발송 실행 (최대 5명)",
                use_container_width=True,
                key=f"{kp}_TEST_SEND",
                disabled=(not has_msg),
            ):
                smtp_host = st.session_state.get("SMTP_HOST", "smtp.gmail.com")
                smtp_port = st.session_state.get("SMTP_PORT", 465)
                sender_email = st.session_state.get("SMTP_SENDER_EMAIL", "")
                sender_pw = st.session_state.get("SMTP_SENDER_PW", "")
                mail_subject = st.session_state.get(f"{kp}_MAIL_SUBJECT", "[MICE 2025] 등록 안내")
                target_email_col = st.session_state.get(f"{kp}_EMAIL_COL")

                if not (sender_email or "").strip() or not (sender_pw or "").strip():
                    st.warning("보내는 계정 정보를 입력하세요.")
                else:
                    raw = (test_receivers_text or "").replace(",", "\n")
                    receivers = [x.strip() for x in raw.splitlines() if x.strip()][:5]
                    if not receivers:
                        st.warning("테스트 이메일을 1개 이상 입력하세요.")
                    else:
                        base_row = send3.head(1).copy().reset_index(drop=True)
                        test_df = pd.concat([base_row] * len(receivers), ignore_index=True)
                        test_df[target_email_col] = receivers

                        payload = _compose_attachments(send3, selected_df)
                        ok, total_bytes = _check_attach_size(payload)
                        if not ok:
                            st.error(
                                f"첨부 총 용량이 {_mb(total_bytes):.2f}MB 입니다. "
                                f"{MAX_TOTAL_ATTACH_MB:.0f}MB 이하로 줄여주세요."
                            )
                        else:
                            suc, s_cnt, f_cnt, logs = mailer.send_bulk_emails(
                                test_df,
                                sender_email,
                                sender_pw,
                                target_email_col,
                                mail_subject,
                                "생성된_메시지",
                                smtp_host,
                                int(smtp_port),
                                attachments=payload,
                            )
                            if suc:
                                st.success(f"테스트 발송 완료! (성공: {s_cnt}, 실패: {f_cnt})")
                                if logs:
                                    with st.expander("실패 로그 보기"):
                                        st.write("\n".join(logs[:200]))
                            else:
                                st.error(f"실패: {logs[0] if logs else 'Unknown'}")

            st.markdown("---")
            st.info("✅ 선택/전체 발송은 ④ 탭에서 대상 체크 후 실행합니다.")

        # =========================================================
        # ④ 대상 선택/발송
        # =========================================================
        with t_pick:
            base4 = st.session_state.get(MAIL_DF_KEY, None)
            base4 = base4 if base4 is not None else view_df
            send4 = base4
            if st.session_state.get(SQL_APPLIED_KEY) and st.session_state.get(SQL_PREVIEW_KEY) is not None:
                send4 = st.session_state[SQL_PREVIEW_KEY]

            if "생성된_메시지" not in send4.columns:
                st.warning("아직 '생성된_메시지'가 없습니다. ② 템플릿 탭에서 템플릿 적용을 먼저 해주세요.")
                st.stop()

            ed4 = _ensure_rowid_index(send4)
            all4 = list(ed4.index.astype(str))
            st.session_state[SELECTED_IDS_KEY] = set(st.session_state[SELECTED_IDS_KEY]).intersection(set(all4))

            # --- 선택 현황 미리보기(④ 탭 최상단) ---
            selected_ids_now = st.session_state.get(SELECTED_IDS_KEY, set())
            selected_count4 = len(selected_ids_now)

            st.markdown(f"#### 👀 선택 대상 미리보기 (상위 10명) — 현재 **{selected_count4:,}명** 선택됨")

            if selected_count4 == 0:
                st.info("아직 선택된 대상이 없습니다. 아래 표에서 체크하면 여기에 바로 반영됩니다.")
            else:
                picked = ed4.loc[list(selected_ids_now)].reset_index(drop=True)

                email_col = st.session_state.get(f"{kp}_EMAIL_COL")
                cols_for_preview = []

                for cand in ["이름", "성명", "Name", "name"]:
                    if cand in picked.columns:
                        cols_for_preview.append(cand)
                        break
                if email_col and email_col in picked.columns:
                    cols_for_preview.append(email_col)
                for extra in ["소속", "회사", "참가구분", "직급"]:
                    if extra in picked.columns and extra not in cols_for_preview:
                        cols_for_preview.append(extra)
                    if len(cols_for_preview) >= 5:
                        break
                if not cols_for_preview:
                    cols_for_preview = list(picked.columns)[:5]

                st.dataframe(picked[cols_for_preview].head(10), use_container_width=True, hide_index=True)

            st.markdown("---")

            st.markdown("#### 📋 발송 대상 데이터 (체크/일괄체크/다운로드)")
            top1, top2, top3, top4 = st.columns([1, 1, 1, 1.4], gap="small")

            with top1:
                if st.button("✅ 전체 선택", use_container_width=True, key=f"{kp}_SEL_ALL"):
                    st.session_state[SELECTED_IDS_KEY] = set(all4)
                    st.session_state[VER_KEY] += 1
                    st.rerun()

            with top2:
                if st.button("⬜ 전체 해제", use_container_width=True, key=f"{kp}_UNSEL_ALL"):
                    st.session_state[SELECTED_IDS_KEY] = set()
                    st.session_state[VER_KEY] += 1
                    st.rerun()

            with top3:
                if st.button("🔁 선택 반전", use_container_width=True, key=f"{kp}_SEL_INVERT"):
                    cur = set(st.session_state[SELECTED_IDS_KEY])
                    st.session_state[SELECTED_IDS_KEY] = set(all4) - cur
                    st.session_state[VER_KEY] += 1
                    st.rerun()

            with top4:
                st.caption("유효 이메일만 자동 선택(③에서 선택한 이메일 컬럼 기준)")
                if st.button("📌 유효 이메일만 선택", use_container_width=True, key=f"{kp}_SEL_VALID_EMAIL"):
                    email_col = st.session_state.get(f"{kp}_EMAIL_COL")
                    if not email_col or email_col not in ed4.columns:
                        mail_cols = [c for c in ed4.columns if ("이메일" in str(c)) or ("email" in str(c).lower())]
                        if mail_cols:
                            email_col = mail_cols[0]

                    if not email_col or email_col not in ed4.columns:
                        st.warning("이메일 컬럼을 찾지 못했습니다. ③ 탭에서 이메일 컬럼을 먼저 선택하세요.")
                    else:
                        valid_mask = ed4[email_col].apply(_is_valid_email)
                        st.session_state[SELECTED_IDS_KEY] = set(ed4.index[valid_mask].astype(str))
                        st.session_state[VER_KEY] += 1
                        st.rerun()

            preview = ed4.copy()
            if "선택" not in preview.columns:
                preview.insert(0, "선택", False)
            preview.loc[preview.index.astype(str).isin(st.session_state[SELECTED_IDS_KEY]), "선택"] = True

            editor_key = f"{kp}_EDITOR_{st.session_state.get(VER_KEY, 0)}"
            edited_df = st.data_editor(
                preview,
                use_container_width=True,
                hide_index=True,
                height=460,
                key=editor_key,
                column_config={"선택": st.column_config.CheckboxColumn("선택", required=True)},
            )

            st.session_state[SELECTED_IDS_KEY] = set(edited_df.loc[edited_df["선택"] == True].index.astype(str))
            selected_rows = edited_df[edited_df["선택"] == True].drop(columns=["선택"], errors="ignore").reset_index(drop=True)
            selected_count4 = len(st.session_state[SELECTED_IDS_KEY])

            st.caption(f"✅ 현재 선택됨: **{selected_count4:,}명**")

            st.markdown("---")
            if selected_rows.empty:
                st.download_button(
                    "⬇️ 선택 엑셀 다운로드",
                    data=b"",
                    file_name="selected.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    disabled=True,
                    use_container_width=True,
                    key=f"{kp}_DL_SELECTED_DISABLED",
                )
            else:
                xlsx_bytes = _df_to_xlsx_bytes(
                    selected_rows.drop(columns=["__rowid__"], errors="ignore"),
                    sheet_name="selected",
                )
                st.download_button(
                    "⬇️ 선택 엑셀 다운로드",
                    data=xlsx_bytes,
                    file_name="selected.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key=f"{kp}_DL_SELECTED",
                )

            # -------------------------
            # 발송 실행 (④에서 실행)
            # -------------------------
            st.markdown("---")
            st.markdown("### ✉️ 발송 실행")

            smtp_host = st.session_state.get("SMTP_HOST", "smtp.gmail.com")
            smtp_port = st.session_state.get("SMTP_PORT", 465)
            sender_email = st.session_state.get("SMTP_SENDER_EMAIL", "")
            sender_pw = st.session_state.get("SMTP_SENDER_PW", "")
            mail_subject = st.session_state.get(f"{kp}_MAIL_SUBJECT", "[MICE 2025] 등록 안내")
            target_email_col = st.session_state.get(f"{kp}_EMAIL_COL", None)

            st.caption(
                f"설정 요약 | sender={'OK' if (sender_email or '').strip() else 'EMPTY'} / "
                f"pw_len={len(sender_pw or '')} / smtp={smtp_host}:{smtp_port} / "
                f"email_col={target_email_col or 'UNKNOWN'}"
            )

            if not target_email_col or target_email_col not in send4.columns:
                st.error("③ 탭에서 '받는 사람 이메일 컬럼'을 먼저 선택해주세요.")
                st.stop()

            def _compose_attachments_for_send(send_df_local: pd.DataFrame, selected_df_local: pd.DataFrame):
                payload = list(st.session_state.get(ATTACH_PAYLOAD_KEY, []))

                if not st.session_state.get(INTERNAL_MODE_KEY, False):
                    return payload

                mode_pick = st.session_state.get(AUTO_ATTACH_MODE_KEY, "안함")
                if mode_pick == "안함":
                    return payload

                fmt = st.session_state.get(AUTO_ATTACH_FMT_KEY, "xlsx")
                name = st.session_state.get(AUTO_ATTACH_NAME_KEY, "mail_targets")

                if mode_pick.startswith("선택"):
                    df_attach = selected_df_local
                    base_name = f"{name}_selected"
                else:
                    df_attach = send_df_local.reset_index(drop=True)
                    base_name = f"{name}_all"

                if df_attach is None or df_attach.empty:
                    return payload

                payload.append(_build_dataset_attachment(df_attach, fmt, base_name))
                return payload

            colA, colB = st.columns([1, 1], gap="small")

            with colA:
                confirm_sel = st.checkbox("선택 발송 확인", value=False, key=f"{kp}_CONFIRM_SEL_4")
                if st.button("선택 발송 실행", type="secondary", use_container_width=True, key=f"{kp}_SEND_SELECTED_4"):
                    if not confirm_sel:
                        st.warning("체크박스로 확인 후 진행하세요.")
                    elif not (sender_email or "").strip() or not (sender_pw or "").strip():
                        st.error("③ 탭에서 이메일 계정 정보를 입력해주세요.")
                    elif selected_rows.empty:
                        st.warning("선택된 대상이 없습니다. 위 표에서 체크하세요.")
                    else:
                        valid_rows = []
                        invalid_rows = []
                        for idx, r in selected_rows.iterrows():
                            em = r.get(target_email_col, None)
                            if _is_valid_email(em):
                                valid_rows.append(r)
                            else:
                                invalid_rows.append(f"- row#{idx+1} / email='{em}'")

                        if not valid_rows:
                            st.error("선택된 행들의 이메일이 전부 비어있거나 형식이 올바르지 않습니다.")
                            if invalid_rows:
                                with st.expander("제외된 대상(이메일 이상)"):
                                    st.write("\n".join(invalid_rows))
                        else:
                            run_df = pd.DataFrame(valid_rows).reset_index(drop=True)

                            payload = _compose_attachments_for_send(send4, run_df)
                            ok, total_bytes = _check_attach_size(payload)
                            if not ok:
                                st.error(
                                    f"첨부 총 용량이 {_mb(total_bytes):.2f}MB 입니다. "
                                    f"{MAX_TOTAL_ATTACH_MB:.0f}MB 이하로 줄여주세요."
                                )
                            else:
                                suc, s_cnt, f_cnt, logs = mailer.send_bulk_emails(
                                    run_df,
                                    sender_email,
                                    sender_pw,
                                    target_email_col,
                                    mail_subject,
                                    "생성된_메시지",
                                    smtp_host,
                                    int(smtp_port),
                                    attachments=payload,
                                )
                                if suc:
                                    st.success(f"선택 발송 완료! (성공: {s_cnt}, 실패: {f_cnt})")
                                else:
                                    st.error(f"선택 발송 실패: {logs[0] if logs else 'Unknown'}")

                                if invalid_rows or logs:
                                    with st.expander("선택 발송 로그(제외/실패)"):
                                        if invalid_rows:
                                            st.markdown("**[제외됨: 이메일 형식 이상]**")
                                            st.write("\n".join(invalid_rows))
                                        if logs:
                                            st.markdown("**[발송 실패 로그]**")
                                            st.write("\n".join(logs[:200]))

            with colB:
                confirm_all = st.checkbox("전체 발송 확인", value=False, key=f"{kp}_CONFIRM_ALL_4")
                st.caption(f"전체 발송 대상: {len(send4):,}명 (SQL/필터 반영)")
                if st.button("전체 발송 시작", type="primary", use_container_width=True, key=f"{kp}_SEND_ALL_4"):
                    if not confirm_all:
                        st.warning("체크박스로 확인 후 진행하세요.")
                    elif not (sender_email or "").strip() or not (sender_pw or "").strip():
                        st.error("③ 탭에서 이메일 계정 정보를 입력해주세요.")
                    else:
                        run_df = send4.reset_index(drop=True)

                        payload = _compose_attachments_for_send(send4, selected_rows)
                        ok, total_bytes = _check_attach_size(payload)
                        if not ok:
                            st.error(
                                f"첨부 총 용량이 {_mb(total_bytes):.2f}MB 입니다. "
                                f"{MAX_TOTAL_ATTACH_MB:.0f}MB 이하로 줄여주세요."
                            )
                        else:
                            suc, s_cnt, f_cnt, logs = mailer.send_bulk_emails(
                                run_df,
                                sender_email,
                                sender_pw,
                                target_email_col,
                                mail_subject,
                                "생성된_메시지",
                                smtp_host,
                                int(smtp_port),
                                attachments=payload,
                            )
                            if suc:
                                st.success(f"전체 발송 완료! (성공: {s_cnt}, 실패: {f_cnt})")
                                if logs:
                                    with st.expander("실패 로그 보기"):
                                        st.write("\n".join(logs[:200]))
                            else:
                                st.error(f"전체 발송 실패: {logs[0] if logs else 'Unknown'}")