import io
import urllib.request
from datetime import date

import pandas as pd
import streamlit as st

from db.database import Database
from models import CategorizedTransaction, Transaction
from parser.categorizer import categorize, load_rules


@st.cache_resource
def _get_db() -> Database:
    return Database()


db = _get_db()

st.set_page_config(page_title="가계부", page_icon="💰", layout="wide")

PAGES = ["홈", "거래내역", "차트", "설정"]
page = st.sidebar.radio("메뉴", PAGES)

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
        started_at = str(log["started_at"])[:16]  # "YYYY-MM-DD HH:MM"
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

    col1, col2, col3 = st.columns(3)
    today = date.today()
    year = col1.number_input("년도", min_value=2020, max_value=2030, value=today.year)
    month = col2.number_input("월", min_value=1, max_value=12, value=today.month)

    rows = db.get_transactions(year=int(year), month=int(month))
    if not rows:
        st.info("거래내역이 없습니다.")
    else:
        df = pd.DataFrame(rows)
        categories = ["전체"] + sorted(df["category"].unique().tolist())
        selected_cat = col3.selectbox("카테고리", categories)
        if selected_cat != "전체":
            df = df[df["category"] == selected_cat]

        st.dataframe(
            df[["date", "description", "amount", "category", "source", "is_edited"]],
            use_container_width=True,
        )

        st.subheader("카테고리 수정")
        with st.form("edit_category"):
            idx = st.number_input("수정할 행 ID", min_value=1, step=1)
            new_cat = st.text_input("새 카테고리")
            if st.form_submit_button("저장"):
                if not new_cat.strip():
                    st.warning("카테고리를 입력하세요.")
                else:
                    matching = [r for r in rows if r["id"] == int(idx)]
                    if not matching:
                        st.error("해당 ID를 찾을 수 없습니다.")
                    else:
                        r = matching[0]
                        try:
                            db.update_category(
                                date=date.fromisoformat(r["date"]),
                                amount=r["amount"],
                                description=r["description"],
                                source=r["source"],
                                category=new_cat,
                            )
                            st.success("저장되었습니다.")
                            st.rerun()
                        except LookupError:
                            st.error("저장 실패: 해당 거래를 찾을 수 없습니다.")

# ─────────────────────────────────────────────
# 차트
# ─────────────────────────────────────────────
elif page == "차트":
    st.title("📊 차트")

    today = date.today()
    col1, col2 = st.columns(2)
    year = col1.number_input("년도", min_value=2020, max_value=2030, value=today.year)
    month = col2.number_input("월", min_value=1, max_value=12, value=today.month)

    rows = db.get_transactions(year=int(year), month=int(month))
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

    # Monthly comparison
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

    # Category rules viewer
    st.subheader("카테고리 규칙")
    try:
        rules = load_rules()
        st.json(rules)
    except FileNotFoundError:
        st.warning("config/categories.yaml 파일이 없습니다.")

    st.caption("규칙을 수정하려면 `config/categories.yaml` 파일을 직접 편집하세요.")

    # CSV Upload
    st.subheader("CSV 업로드")
    uploaded = st.file_uploader("거래내역 CSV 파일", type=["csv"])
    if uploaded:
        df = pd.read_csv(io.BytesIO(uploaded.read()))
        st.dataframe(df.head())
        st.info(f"{len(df)}개 행 감지됨. 아래 컬럼 매핑을 확인하세요.")
        col_map = {}
        for field in ["date", "amount", "description", "source"]:
            col_map[field] = st.selectbox(f"{field} 컬럼", df.columns.tolist(), key=field)
        if st.button("가져오기"):
            txs = []
            for _, row in df.iterrows():
                try:
                    txs.append(Transaction(
                        date=date.fromisoformat(str(row[col_map["date"]])[:10]),
                        amount=int(row[col_map["amount"]]),
                        description=str(row[col_map["description"]]),
                        source=str(row[col_map["source"]]),
                        raw_source="csv",
                    ))
                except Exception as e:
                    st.warning(f"행 건너뜀: {e}")
            categorized = categorize(txs)
            inserted = db.insert_transactions(categorized)
            st.success(f"{inserted}개 거래 추가됨 (중복 제외)")

    # Manual entry
    st.subheader("수동 입력")
    with st.form("manual_entry"):
        entry_date = st.date_input("날짜", value=date.today())
        entry_amount = st.number_input("금액 (지출은 음수)", step=100)
        entry_desc = st.text_input("내용")
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
                    source=entry_source,
                    raw_source="manual",
                    category=entry_cat,
                )
                db.insert_transactions([tx])
                st.success("추가되었습니다.")
                st.rerun()
