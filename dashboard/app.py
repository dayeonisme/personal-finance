import io
import urllib.request
from datetime import date

import pandas as pd
import streamlit as st

from db.database import Database
from models import CategorizedTransaction, Transaction
from parser.categorizer import categorize, load_rules


st.set_page_config(page_title="가계부", page_icon="💰", layout="wide")


@st.cache_resource
def _get_db() -> Database:
    return Database()


db = _get_db()

PAGES = ["홈", "거래내역", "차트", "설정"]
page = st.sidebar.radio("메뉴", PAGES)

# ─────────────────────────────────────────────
# 공통 헬퍼
# ─────────────────────────────────────────────
def _year_month_selector(key_prefix: str):
    today = date.today()
    available_years = db.get_available_years()
    if not available_years:
        available_years = list(range(today.year, today.year - 3, -1))
    year_options = [str(y) for y in available_years]
    default_year = str(today.year) if str(today.year) in year_options else year_options[0]

    col1, col2 = st.columns(2)
    year = col1.selectbox("년도", year_options,
                          index=year_options.index(default_year),
                          key=f"{key_prefix}_year")
    month = col2.selectbox("월", list(range(1, 13)),
                           index=today.month - 1,
                           key=f"{key_prefix}_month")
    return int(year), int(month)


# ─────────────────────────────────────────────
# 홈
# ─────────────────────────────────────────────
if page == "홈":
    st.title("💰 이번달 요약")

    today = date.today()
    this_month = db.get_transactions(year=today.year, month=today.month)
    last_month = db.get_transactions(
        year=today.year if today.month > 1 else today.year - 1,
        month=today.month - 1 if today.month > 1 else 12,
    )

    def summarize(rows):
        income = sum(r["amount"] for r in rows if r["amount"] > 0)
        expense = sum(r["amount"] for r in rows if r["amount"] < 0)
        return income, expense

    inc_this, exp_this = summarize(this_month)
    inc_last, exp_last = summarize(last_month)

    net_this = inc_this + exp_this
    net_last = inc_last + exp_last
    col1, col2, col3 = st.columns(3)
    col1.metric("수입", f"{inc_this:,}원", f"{inc_this - inc_last:+,}원 vs 지난달")
    col2.metric("지출", f"{abs(exp_this):,}원", f"{abs(exp_this) - abs(exp_last):+,}원 vs 지난달")
    col3.metric("순수익", f"{net_this:,}원", f"{net_this - net_last:+,}원 vs 지난달")

    log = db.get_latest_crawl_log()
    if log:
        status_map = {"success": "성공", "failed": "실패", "running": "실행 중"}
        status_ko = status_map.get(log["status"], log["status"])
        status_emoji = "✅" if log["status"] == "success" else "❌"
        started_at = str(log["started_at"])[:16]
        st.caption(f"{status_emoji} 마지막 동기화: {started_at} ({status_ko})")

    if st.button("🔄 지금 동기화"):
        try:
            urllib.request.urlopen(
                urllib.request.Request("http://127.0.0.1:9000/run", method="POST"),
                timeout=5,
            )
            st.success("동기화 요청 완료!")
        except Exception as e:
            st.error(f"webhook_server.py가 실행 중인지 확인하세요: {e}")

# ─────────────────────────────────────────────
# 거래내역
# ─────────────────────────────────────────────
elif page == "거래내역":
    st.title("📋 거래내역")

    year, month = _year_month_selector("tx")

    rows = db.get_transactions(year=year, month=month)
    if not rows:
        st.info("거래내역이 없습니다.")
    else:
        df = pd.DataFrame(rows)

        # 카테고리 필터
        categories = ["전체"] + sorted(df["category"].unique().tolist())
        selected_cat = st.selectbox("카테고리 필터", categories, key="tx_cat_filter")
        if selected_cat != "전체":
            df = df[df["category"] == selected_cat]

        # 열 표시 선택
        all_cols = ["date", "place", "description", "amount", "category", "source", "is_edited"]
        visible_cols = st.multiselect("표시할 열 선택", all_cols, default=all_cols, key="tx_cols")
        if not visible_cols:
            visible_cols = all_cols

        edit_cols = {"category", "place", "description"}
        disabled_cols = [c for c in visible_cols if c not in edit_cols]

        # 체크박스 열 추가
        editor_df = df[["id"] + visible_cols].copy()
        editor_df.insert(0, "선택", False)

        edited = st.data_editor(
            editor_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "선택": st.column_config.CheckboxColumn("선택", width="small"),
                "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                "date": st.column_config.DateColumn("날짜", disabled=True),
                "amount": st.column_config.NumberColumn("금액", disabled=True, format="%d"),
                "category": st.column_config.TextColumn("카테고리"),
                "place": st.column_config.TextColumn("사용 장소"),
                "description": st.column_config.TextColumn("메모"),
                "source": st.column_config.TextColumn("출처", disabled=True),
                "is_edited": st.column_config.CheckboxColumn("수정됨", disabled=True),
            },
            key="tx_editor",
        )

        btn1, btn2 = st.columns(2)

        # 변경 사항 저장
        if btn1.button("💾 변경 사항 저장"):
            saved = 0
            for _, orig_row in editor_df.iterrows():
                row_id = int(orig_row["id"])
                edited_row = edited[edited["id"] == row_id]
                if edited_row.empty:
                    continue
                e = edited_row.iloc[0]
                kwargs = {}
                if "category" in visible_cols and e.get("category") != orig_row.get("category"):
                    kwargs["category"] = str(e["category"])
                if "place" in visible_cols and e.get("place") != orig_row.get("place"):
                    kwargs["place"] = str(e["place"])
                if "description" in visible_cols and e.get("description") != orig_row.get("description"):
                    kwargs["description"] = str(e["description"])
                if kwargs:
                    db.update_transaction(row_id, **kwargs)
                    saved += 1
            if saved:
                st.success(f"{saved}개 행 저장됨.")
                st.rerun()
            else:
                st.info("변경된 내용이 없습니다.")

        # 선택한 행 삭제
        if btn2.button("🗑️ 선택한 행 삭제"):
            selected_ids = edited[edited["선택"] == True]["id"].tolist()
            if not selected_ids:
                st.warning("삭제할 행을 선택하세요.")
            else:
                deleted = db.delete_transactions([int(i) for i in selected_ids])
                st.success(f"{deleted}개 행 삭제됨.")
                st.rerun()

# ─────────────────────────────────────────────
# 차트
# ─────────────────────────────────────────────
elif page == "차트":
    st.title("📊 차트")

    year, month = _year_month_selector("chart")

    rows = db.get_transactions(year=year, month=month)
    if not rows:
        st.info("데이터가 없습니다.")
    else:
        df = pd.DataFrame(rows)
        expenses = df[df["amount"] < 0].copy()
        expenses["amount_abs"] = expenses["amount"].abs()

        st.subheader("카테고리별 지출")
        cat_summary = expenses.groupby("category")["amount_abs"].sum().reset_index()
        st.bar_chart(cat_summary.set_index("category"))

        st.subheader("카테고리별 비율")
        st.write(cat_summary)

    today = date.today()
    st.subheader("월별 지출 비교 (최근 6개월)")
    monthly = []
    for m in range(5, -1, -1):
        target_month = today.month - m
        target_year = today.year
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        r = db.get_transactions(year=target_year, month=target_month)
        exp = sum(row["amount"] for row in r if row["amount"] < 0)
        monthly.append({"month": f"{target_year}-{target_month:02d}", "지출": abs(exp)})
    if monthly:
        st.bar_chart(pd.DataFrame(monthly).set_index("month"))

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
elif page == "설정":
    st.title("⚙️ 설정")

    setting_sub = st.radio(
        "기능 선택",
        ["카테고리 규칙", "CSV 업로드", "수동 입력"],
        horizontal=True,
        key="setting_sub",
    )
    st.divider()

    # ── 카테고리 규칙 ──────────────────────────
    if setting_sub == "카테고리 규칙":
        st.subheader("카테고리 규칙")
        try:
            rules = load_rules()
            st.json(rules)
        except FileNotFoundError:
            st.warning("config/categories.yaml 파일이 없습니다.")
        st.caption("규칙을 수정하려면 `config/categories.yaml` 파일을 직접 편집하세요.")

    # ── CSV 업로드 ─────────────────────────────
    elif setting_sub == "CSV 업로드":
        st.subheader("CSV 업로드")
        uploaded = st.file_uploader("거래내역 CSV 파일", type=["csv"])
        if uploaded:
            df = pd.read_csv(io.BytesIO(uploaded.read()))

            # 첫 번째 열이 비어있는 첫 행에서 멈추기
            first_col = df.columns[0]
            empty_mask = df[first_col].isna() | (df[first_col].astype(str).str.strip() == "")
            if empty_mask.any():
                df = df.iloc[:empty_mask.idxmax()]

            # 전체 데이터 미리보기 (스크롤 가능)
            st.info(f"총 {len(df)}개 행 감지됨.")
            st.dataframe(df, height=400, use_container_width=True)

            cols = df.columns.tolist()
            none_option = ["(없음)"] + cols
            dtype_options = ["텍스트", "숫자", "boolean"]

            def parse_value(val, dtype: str) -> str:
                raw = str(val).strip()
                if dtype == "숫자":
                    return str(int(float(raw.replace(",", ""))))
                if dtype == "boolean":
                    return "예" if raw.lower() in {"1", "true", "y", "yes", "예", "t"} else "아니오"
                return raw

            st.markdown("**필수 컬럼** (타입 고정)")
            c1, c2 = st.columns(2)
            date_col   = c1.selectbox("날짜 *", cols, key="csv_date")
            amount_col = c2.selectbox("금액 * (숫자)", cols, key="csv_amount")

            st.markdown("**선택 컬럼** (타입 지정 가능)")
            c3, c4 = st.columns([3, 1])
            place_col   = c3.selectbox("사용 장소", none_option, key="csv_place")
            place_dtype = c4.selectbox("타입", dtype_options, key="csv_place_dtype")

            c5, c6 = st.columns([3, 1])
            desc_col   = c5.selectbox("메모", none_option, key="csv_desc")
            desc_dtype = c6.selectbox("타입", dtype_options, key="csv_desc_dtype")

            c7, c8 = st.columns([3, 1])
            source_col   = c7.selectbox("출처 (계좌/카드)", none_option, key="csv_source")
            source_dtype = c8.selectbox("타입", dtype_options, key="csv_source_dtype")

            if st.button("가져오기"):
                txs = []
                for _, row in df.iterrows():
                    try:
                        raw_amount = str(row[amount_col]).replace(",", "").strip()
                        txs.append(Transaction(
                            date=date.fromisoformat(str(row[date_col])[:10]),
                            amount=int(float(raw_amount)),
                            description=parse_value(row[desc_col], desc_dtype) if desc_col != "(없음)" else "",
                            place=parse_value(row[place_col], place_dtype) if place_col != "(없음)" else "",
                            source=parse_value(row[source_col], source_dtype) if source_col != "(없음)" else "csv",
                            raw_source="csv",
                        ))
                    except Exception as e:
                        st.warning(f"행 건너뜀: {e}")
                categorized = categorize(txs)
                inserted = db.insert_transactions(categorized)
                st.success(f"{inserted}개 거래 추가됨 (중복 제외)")

    # ── 수동 입력 ──────────────────────────────
    elif setting_sub == "수동 입력":
        st.subheader("수동 입력")
        with st.form("manual_entry"):
            entry_date = st.date_input("날짜", value=date.today())
            entry_amount = st.number_input("금액 (지출은 음수)", step=100)
            entry_place = st.text_input("사용 장소")
            entry_desc = st.text_input("메모")
            entry_cat = st.text_input("카테고리", value="미분류")
            entry_source = st.text_input("출처", value="manual")
            if st.form_submit_button("추가"):
                if entry_amount == 0:
                    st.warning("금액을 입력하세요 (지출은 음수).")
                else:
                    tx = CategorizedTransaction(
                        date=entry_date,
                        amount=int(entry_amount),
                        description=entry_desc,
                        place=entry_place,
                        source=entry_source,
                        raw_source="manual",
                        category=entry_cat,
                    )
                    db.insert_transactions([tx])
                    st.success("추가되었습니다.")
                    st.rerun()
