import io
import urllib.request
from datetime import date
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import yaml
from dotenv import load_dotenv

load_dotenv()

from db.database import Database
from models import CategorizedTransaction, Transaction
from parser.categorizer import categorize, load_rules


st.set_page_config(page_title="가계부", page_icon="💰", layout="wide")


@st.cache_resource
def _get_db() -> Database:
    return Database()


db = _get_db()

# ─────────────────────────────────────────────
# 세션 상태 초기화
# ─────────────────────────────────────────────
def _init_state():
    if "page" not in st.session_state:
        st.session_state.page = "홈"
    if "settings_expanded" not in st.session_state:
        st.session_state.settings_expanded = False
    if "settings_sub" not in st.session_state:
        st.session_state.settings_sub = "카테고리 규칙"
    if "csv_pending_txs" not in st.session_state:
        st.session_state.csv_pending_txs = []
    if "csv_show_analysis" not in st.session_state:
        st.session_state.csv_show_analysis = False

_init_state()

# ─────────────────────────────────────────────
# 사이드바 네비게이션
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 메뉴")

    for nav in ["홈", "거래내역", "차트"]:
        icon = {"홈": "🏠", "거래내역": "📋", "차트": "📊"}[nav]
        is_active = st.session_state.page == nav
        label = f"**{icon} {nav}**" if is_active else f"{icon} {nav}"
        if st.button(label, use_container_width=True, key=f"nav_{nav}"):
            st.session_state.page = nav
            st.session_state.settings_expanded = False
            st.rerun()

    arrow = "▼" if st.session_state.settings_expanded else "▶"
    if st.button(f"⚙️ 설정 {arrow}", use_container_width=True, key="nav_settings_toggle"):
        st.session_state.settings_expanded = not st.session_state.settings_expanded
        st.rerun()

    if st.session_state.settings_expanded:
        for sub in ["카테고리 규칙", "CSV 업로드", "수동 입력"]:
            is_sub_active = st.session_state.page == "설정" and st.session_state.settings_sub == sub
            sub_label = f"**└ {sub}**" if is_sub_active else f"└ {sub}"
            if st.button(sub_label, use_container_width=True, key=f"nav_sub_{sub}"):
                st.session_state.page = "설정"
                st.session_state.settings_sub = sub
                st.rerun()

page = st.session_state.page

# ─────────────────────────────────────────────
# 공통 헬퍼
# ─────────────────────────────────────────────
def _year_month_selector(key_prefix: str):
    today = date.today()
    available_years = db.get_available_years()
    if not available_years:
        available_years = list(range(today.year, today.year - 3, -1))

    year_options = ["전체"] + [str(y) for y in available_years]
    default_year_idx = (year_options.index(str(today.year))
                        if str(today.year) in year_options else 1)

    month_options = ["전체"] + list(range(1, 13))
    default_month_idx = today.month

    col1, col2 = st.columns(2)
    year_val = col1.selectbox("년도", year_options,
                              index=default_year_idx, key=f"{key_prefix}_year")
    month_val = col2.selectbox("월", month_options,
                               index=default_month_idx, key=f"{key_prefix}_month")

    return (None if year_val == "전체" else int(year_val),
            None if month_val == "전체" else int(month_val))


def _get_rows(year, month):
    if year is None and month is None:
        return db.get_transactions()
    if year is not None and month is None:
        return db.get_transactions(year=year)
    return db.get_transactions(year=year, month=month)


def _infer_col_idx(cols: list[str], hints: set[str], with_none: bool = False) -> int:
    """컬럼명에서 hints 와 가장 가깝게 일치하는 인덱스 반환."""
    for i, col in enumerate(cols):
        if col.lower().strip() in hints:
            return i + (1 if with_none else 0)
    return 0


_RULES_PATH = Path("config/categories.yaml")


def _update_category_rules(place_to_cat: dict[str, str]) -> None:
    """장소→카테고리 매핑을 categories.yaml 에 추가 (카테고리는 항상 unique 유지)."""
    rules = load_rules(_RULES_PATH)
    rule_list = rules.get("rules", [])

    # category → rule dict (중복 카테고리 병합)
    cat_to_rule: dict[str, dict] = {}
    for rule in rule_list:
        cat = rule["category"]
        if cat in cat_to_rule:
            existing = set(cat_to_rule[cat]["match"])
            for kw in rule.get("match", []):
                if kw not in existing:
                    cat_to_rule[cat]["match"].append(kw)
        else:
            cat_to_rule[cat] = {"category": cat, "match": list(rule.get("match", []))}

    for place, category in place_to_cat.items():
        if not place or category == "미분류":
            continue
        if category in cat_to_rule:
            if place not in cat_to_rule[category]["match"]:
                cat_to_rule[category]["match"].append(place)
        else:
            cat_to_rule[category] = {"category": category, "match": [place]}

    rules["rules"] = list(cat_to_rule.values())
    with open(_RULES_PATH, "w", encoding="utf-8") as f:
        yaml.dump(rules, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


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
    rows = _get_rows(year, month)

    if not rows:
        st.info("거래내역이 없습니다.")
    else:
        df = pd.DataFrame(rows).fillna("").replace("nan", "")

        # 카테고리 필터
        categories = ["전체"] + sorted(df["category"].unique().tolist())
        selected_cat = st.selectbox("카테고리 필터", categories, key="tx_cat_filter")
        if selected_cat != "전체":
            df = df[df["category"] == selected_cat]

        # 열 표시 선택
        all_cols = ["date", "place", "description", "amount", "category", "source", "is_edited"]
        col_select_opts = ["전체"] + all_cols
        chosen = st.multiselect("표시할 열 선택", col_select_opts,
                                default=["전체"], key="tx_cols")
        visible_cols = all_cols if "전체" in chosen else [c for c in all_cols if c in chosen]
        if not visible_cols:
            visible_cols = all_cols

        # 전체 행 선택 체크박스
        select_all = st.checkbox("전체 행 선택", key="tx_select_all")

        editor_df = df[["id"] + visible_cols].copy().fillna("")
        editor_df.insert(0, "선택", select_all)

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

        if btn1.button("💾 변경 사항 저장"):
            saved = 0
            for _, orig_row in editor_df.iterrows():
                row_id = int(orig_row["id"])
                edited_row = edited[edited["id"] == row_id]
                if edited_row.empty:
                    continue
                e = edited_row.iloc[0]
                kwargs = {}
                for field in ["category", "place", "description"]:
                    if field in visible_cols and str(e.get(field, "")) != str(orig_row.get(field, "")):
                        kwargs[field] = str(e[field])
                if kwargs:
                    db.update_transaction(row_id, **kwargs)
                    saved += 1
            if saved:
                st.success(f"{saved}개 행 저장됨.")
                st.rerun()
            else:
                st.info("변경된 내용이 없습니다.")

        if btn2.button("🗑️ 선택한 행 삭제"):
            selected_ids = edited[edited["선택"] == True]["id"].tolist()
            if not selected_ids:
                st.warning("삭제할 행을 선택하세요.")
            else:
                deleted = db.delete_transactions([int(i) for i in selected_ids])
                st.success(f"{deleted}개 행 삭제됨.")
                st.rerun()

# ─────────────────────────────────────────────
# 차트 (고도화)
# ─────────────────────────────────────────────
elif page == "차트":
    st.title("📊 재무 분석 대시보드")

    today = date.today()

    def collect_monthly(n=6):
        records = []
        for m in range(n - 1, -1, -1):
            tm = today.month - m
            ty = today.year
            while tm <= 0:
                tm += 12
                ty -= 1
            rows = db.get_transactions(year=ty, month=tm)
            income  = sum(r["amount"] for r in rows if r["amount"] > 0)
            expense = sum(r["amount"] for r in rows if r["amount"] < 0)
            records.append({
                "month": f"{ty}-{tm:02d}",
                "수입": income,
                "지출": abs(expense),
                "순수익": income + expense,
                "저축률": round((income + expense) / income * 100, 1) if income > 0 else 0,
            })
        return pd.DataFrame(records).set_index("month")

    monthly_df = collect_monthly(6)

    CHART_H = 300  # 모든 차트 고정 높이

    st.subheader("📈 최근 6개월 추이")
    tab1, tab2, tab3 = st.tabs(["수입 / 지출", "순수익", "저축률 (%)"])

    with tab1:
        df_long = (monthly_df[["수입", "지출"]]
                   .reset_index()
                   .melt(id_vars="month", var_name="구분", value_name="금액"))
        st.altair_chart(
            alt.Chart(df_long).mark_line(point=True).encode(
                x=alt.X("month:N", title="월", sort=None),
                y=alt.Y("금액:Q", scale=alt.Scale(domainMin=0), title="금액 (원)"),
                color="구분:N",
                tooltip=["month:N", "구분:N", "금액:Q"],
            ).properties(height=CHART_H),
            use_container_width=True,
        )

    with tab2:
        df_net = monthly_df[["순수익"]].reset_index()
        y_min = min(0, int(df_net["순수익"].min()) - 10000)
        st.altair_chart(
            alt.Chart(df_net).mark_bar().encode(
                x=alt.X("month:N", title="월", sort=None),
                y=alt.Y("순수익:Q", scale=alt.Scale(domainMin=y_min), title="금액 (원)"),
                color=alt.condition(
                    alt.datum["순수익"] >= 0,
                    alt.value("#4C9BE8"),
                    alt.value("#E84C4C"),
                ),
                tooltip=["month:N", "순수익:Q"],
            ).properties(height=CHART_H),
            use_container_width=True,
        )

    with tab3:
        df_sr = monthly_df[["저축률"]].reset_index()
        st.altair_chart(
            alt.Chart(df_sr).mark_line(point=True).encode(
                x=alt.X("month:N", title="월", sort=None),
                y=alt.Y("저축률:Q", scale=alt.Scale(domainMin=0), title="저축률 (%)"),
                tooltip=["month:N", "저축률:Q"],
            ).properties(height=CHART_H),
            use_container_width=True,
        )
        st.caption("저축률 = (수입 - 지출) / 수입 × 100")

    st.divider()

    year, month = _year_month_selector("chart")
    rows = _get_rows(year, month)
    period_label = (f"{year}년 {month}월" if year and month
                    else f"{year}년" if year else "전체 기간")

    st.subheader(f"🗂️ {period_label} 카테고리별 지출")
    if not rows:
        st.info("데이터가 없습니다.")
    else:
        df = pd.DataFrame(rows)
        expenses = df[df["amount"] < 0].copy()
        expenses["amount_abs"] = expenses["amount"].abs()

        if expenses.empty:
            st.info("지출 내역이 없습니다.")
        else:
            cat_df = expenses.groupby("category")["amount_abs"].sum().reset_index()
            cat_df = cat_df.sort_values("amount_abs", ascending=False)
            cat_df.columns = ["카테고리", "금액"]

            c1, c2 = st.columns([3, 2])
            with c1:
                st.altair_chart(
                    alt.Chart(cat_df).mark_bar().encode(
                        x=alt.X("카테고리:N", sort="-y", title=""),
                        y=alt.Y("금액:Q", scale=alt.Scale(domainMin=0), title="금액 (원)"),
                        tooltip=["카테고리:N", "금액:Q"],
                    ).properties(height=CHART_H),
                    use_container_width=True,
                )
            with c2:
                total_exp = cat_df["금액"].sum()
                cat_df["비율"] = (cat_df["금액"] / total_exp * 100).round(1).astype(str) + "%"
                cat_df["금액"] = cat_df["금액"].apply(lambda x: f"{x:,.0f}원")
                st.dataframe(cat_df, use_container_width=True, hide_index=True)

    st.divider()

    if month and year:
        st.subheader("🔄 전월 대비 카테고리 변화")
        prev_m = month - 1 if month > 1 else 12
        prev_y = year if month > 1 else year - 1
        prev_rows = db.get_transactions(year=prev_y, month=prev_m)

        def cat_expense(r_list):
            d = {}
            for r in r_list:
                if r["amount"] < 0:
                    d[r["category"]] = d.get(r["category"], 0) + abs(r["amount"])
            return d

        curr_cat = cat_expense(rows)
        prev_cat = cat_expense(prev_rows)
        all_cats = sorted(set(curr_cat) | set(prev_cat))

        if all_cats:
            compare_rows = []
            for c in all_cats:
                compare_rows.append({"카테고리": c, "월": f"{prev_y}-{prev_m:02d}", "금액": prev_cat.get(c, 0)})
                compare_rows.append({"카테고리": c, "월": f"{year}-{month:02d}", "금액": curr_cat.get(c, 0)})
            cmp_df = pd.DataFrame(compare_rows)
            st.altair_chart(
                alt.Chart(cmp_df).mark_bar().encode(
                    x=alt.X("카테고리:N", title=""),
                    y=alt.Y("금액:Q", scale=alt.Scale(domainMin=0), title="금액 (원)"),
                    color="월:N",
                    xOffset="월:N",
                    tooltip=["카테고리:N", "월:N", "금액:Q"],
                ).properties(height=CHART_H),
                use_container_width=True,
            )

    st.divider()

    st.subheader("📅 일별 지출 패턴")
    if rows:
        df_day = pd.DataFrame(rows)
        df_day = df_day[df_day["amount"] < 0].copy()
        if not df_day.empty:
            df_day["date"] = pd.to_datetime(df_day["date"])
            daily = df_day.groupby("date")["amount"].sum().abs().reset_index()
            daily.columns = ["날짜", "지출"]
            st.altair_chart(
                alt.Chart(daily).mark_area(opacity=0.7, line=True).encode(
                    x=alt.X("날짜:T", title="날짜"),
                    y=alt.Y("지출:Q", scale=alt.Scale(domainMin=0), title="금액 (원)"),
                    tooltip=["날짜:T", "지출:Q"],
                ).properties(height=CHART_H),
                use_container_width=True,
            )
        else:
            st.info("지출 데이터가 없습니다.")

    st.divider()

    st.subheader("💸 TOP 10 지출 항목")
    if rows:
        df_top = pd.DataFrame(rows)
        df_top = df_top[df_top["amount"] < 0].copy()
        if not df_top.empty:
            df_top["amount_abs"] = df_top["amount"].abs()
            df_top = df_top.nlargest(10, "amount_abs")[
                ["date", "place", "description", "amount_abs", "category"]
            ].copy()
            df_top.columns = ["날짜", "사용 장소", "메모", "금액", "카테고리"]
            df_top["금액"] = df_top["금액"].apply(lambda x: f"{x:,.0f}원")
            st.dataframe(df_top.fillna(""), use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
elif page == "설정":
    setting_sub = st.session_state.settings_sub

    # ── 미분류 일괄 재분류 ─────────────────────
    def _ai_recategorize_unclassified():
        """DB의 미분류 항목을 AI로 일괄 재분류 후 DB 업데이트 + 규칙 저장."""
        import os, json
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            st.error("ANTHROPIC_API_KEY가 .env에 없습니다.")
            return

        all_rows = db.get_transactions()
        uncat = [r for r in all_rows if r["category"] == "미분류"]
        if not uncat:
            st.info("미분류 항목이 없습니다.")
            return

        # place 또는 description 기준으로 unique 목록
        unique_places = sorted(set(
            (r["place"] or r["description"]).strip()
            for r in uncat
            if (r["place"] or r["description"]).strip()
        ))

        if not unique_places:
            st.info("분류 기준이 될 장소/메모가 없습니다.")
            return

        existing_cats = sorted(set(
            rule["category"] for rule in load_rules().get("rules", [])
        ))
        cats_str = ", ".join(existing_cats)

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            places_str = "\n".join(f"- {p}" for p in unique_places)
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": (
                        f"한국 가계부 앱입니다. 아래 장소/가맹점명을 보고 카테고리를 유추해주세요.\n"
                        f"기존 카테고리: {cats_str}\n"
                        f"기존 카테고리에 없으면 새 카테고리를 만들어도 됩니다.\n"
                        f"확실하지 않으면 \"미분류\"로 설정하세요.\n\n"
                        f"장소 목록:\n{places_str}\n\n"
                        f"JSON만 응답 (다른 텍스트 없이): {{\"장소명\": \"카테고리\", ...}}"
                    ),
                }],
            )
            text = msg.content[0].text.strip()
            start, end = text.find("{"), text.rfind("}") + 1
            if start < 0 or end <= start:
                st.error("AI 응답 파싱 실패")
                return
            place_to_cat: dict[str, str] = json.loads(text[start:end])
        except Exception as e:
            st.error(f"AI 호출 실패: {e}")
            return

        # DB 업데이트 + 규칙 저장
        updated = 0
        new_rules: dict[str, str] = {}
        for r in uncat:
            key = (r["place"] or r["description"]).strip()
            cat = place_to_cat.get(key, "")
            if cat and cat != "미분류":
                db.update_transaction(r["id"], category=cat)
                updated += 1
                if r["place"]:
                    new_rules[r["place"]] = cat

        if new_rules:
            _update_category_rules(new_rules)

        st.success(f"{updated}개 항목 재분류 완료, {len(new_rules)}개 규칙 추가됨.")
        st.rerun()

    # ── 카테고리 규칙 ──────────────────────────
    if setting_sub == "카테고리 규칙":
        st.title("📝 카테고리 규칙")

        # 미분류 일괄 재분류 버튼
        uncat_count = sum(1 for r in db.get_transactions() if r["category"] == "미분류")
        if uncat_count > 0:
            st.warning(f"현재 미분류 항목: **{uncat_count}개**")
            if st.button("🤖 AI로 미분류 일괄 재분류"):
                with st.spinner("AI가 분류 중..."):
                    _ai_recategorize_unclassified()
        st.divider()
        try:
            rules = load_rules()
            rule_list = rules.get("rules", [])
            default_cat = rules.get("default_category", "미분류")

            rows_data = []
            for i, rule in enumerate(rule_list, 1):
                rows_data.append({
                    "번호": i,
                    "카테고리": rule.get("category", ""),
                    "포함 키워드": ", ".join(rule.get("match", [])),
                })
            if rows_data:
                st.dataframe(
                    pd.DataFrame(rows_data),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "번호": st.column_config.NumberColumn(width="small"),
                        "카테고리": st.column_config.TextColumn(width="medium"),
                        "포함 키워드": st.column_config.TextColumn(width="large"),
                    },
                )
            st.info(f"매칭 없을 때 기본 카테고리: **{default_cat}**")
        except FileNotFoundError:
            st.warning("config/categories.yaml 파일이 없습니다.")
        st.caption("규칙을 수정하려면 `config/categories.yaml` 파일을 직접 편집하세요.")

    # ── CSV 업로드 ─────────────────────────────
    elif setting_sub == "CSV 업로드":
        st.title("📤 CSV 업로드")
        uploaded = st.file_uploader("거래내역 CSV 파일", type=["csv"])

        if uploaded:
            raw_bytes = uploaded.read()
            df = pd.read_csv(io.BytesIO(raw_bytes))

            # 첫 빈 행에서 중단
            first_col = df.columns[0]
            empty_mask = df[first_col].isna() | (df[first_col].astype(str).str.strip() == "")
            if empty_mask.any():
                df = df.iloc[:empty_mask.idxmax()]

            st.info(f"총 {len(df)}개 행 감지됨.")
            st.dataframe(df.fillna(""), height=300, use_container_width=True)

            cols = df.columns.tolist()
            none_option = ["(없음)"] + cols

            # ── 컬럼 자동 매핑 ───────────────────
            DATE_HINTS   = {"날짜", "일자", "date", "거래일", "거래일시", "거래날짜", "transaction_date", "거래 일자"}
            AMOUNT_HINTS = {"금액", "amount", "거래금액", "출금금액", "입출금액", "입출금금액", "transaction_amount", "출금"}
            PLACE_HINTS  = {"장소", "place", "사용처", "가맹점", "가맹점명", "merchant", "사용장소", "사용 장소", "이용장소"}
            DESC_HINTS   = {"메모", "memo", "내용", "description", "적요", "거래내용", "비고", "거래 내용"}
            SRC_HINTS    = {"출처", "source", "계좌", "카드", "account", "card", "카드명", "계좌명"}

            date_default   = _infer_col_idx(cols, DATE_HINTS)
            amount_default = _infer_col_idx(cols, AMOUNT_HINTS)
            place_default  = _infer_col_idx(cols, PLACE_HINTS, with_none=True)
            desc_default   = _infer_col_idx(cols, DESC_HINTS, with_none=True)
            src_default    = _infer_col_idx(cols, SRC_HINTS, with_none=True)

            st.markdown("**컬럼 매핑** (자동 유추됨, 수정 가능)")
            c1, c2 = st.columns(2)
            date_col   = c1.selectbox("날짜 *", cols, index=date_default, key="csv_date")
            amount_col = c2.selectbox("금액 * (숫자)", cols, index=amount_default, key="csv_amount")

            c3, c4 = st.columns(2)
            place_col  = c3.selectbox("사용 장소", none_option, index=place_default, key="csv_place")
            desc_col   = c4.selectbox("메모", none_option, index=desc_default, key="csv_desc")

            source_col = st.selectbox("출처 (계좌/카드)", none_option, index=src_default, key="csv_source")

            def parse_value(val, dtype: str = "텍스트") -> str:
                if pd.isna(val):
                    return ""
                raw = str(val).strip()
                if dtype == "숫자":
                    return str(int(float(raw.replace(",", ""))))
                return raw

            def parse_txs(dataframe) -> list[Transaction]:
                txs = []
                for _, row in dataframe.iterrows():
                    try:
                        raw_amount = str(row[amount_col]).replace(",", "").strip()
                        txs.append(Transaction(
                            date=date.fromisoformat(str(row[date_col])[:10]),
                            amount=int(float(raw_amount)),
                            description=parse_value(row[desc_col]) if desc_col != "(없음)" else "",
                            place=parse_value(row[place_col]) if place_col != "(없음)" else "",
                            source=parse_value(row[source_col]) if source_col != "(없음)" else "csv",
                            raw_source="csv",
                        ))
                    except Exception as e:
                        st.warning(f"행 건너뜀: {e}")
                return txs

            # ── 분석하기 ─────────────────────────
            if st.button("🔍 분석하기"):
                txs = parse_txs(df)
                st.session_state.csv_pending_txs = txs
                st.session_state.csv_show_analysis = True

            if st.session_state.csv_show_analysis and st.session_state.csv_pending_txs:
                txs = st.session_state.csv_pending_txs
                categorized = categorize(txs)

                # 카테고리 요약
                cat_counts: dict[str, int] = {}
                for ct in categorized:
                    cat_counts[ct.category] = cat_counts.get(ct.category, 0) + 1
                summary_df = pd.DataFrame(
                    [{"카테고리": k, "건수": v} for k, v in sorted(cat_counts.items())]
                )
                st.markdown("**카테고리별 분류 결과**")
                st.dataframe(summary_df, use_container_width=True, hide_index=True)

                # 미분류 장소 카테고리 지정
                uncat_places = sorted(set(
                    ct.place for ct in categorized
                    if ct.category == "미분류" and ct.place
                ))

                place_to_cat: dict[str, str] = {}
                if uncat_places:
                    existing_cats = sorted(set(
                        r["category"] for r in load_rules().get("rules", [])
                    ))
                    cat_choices = existing_cats + ["미분류"]

                    # AI 카테고리 유추 (ANTHROPIC_API_KEY 있을 때만)
                    ai_suggestions: dict[str, str] = {}
                    import os
                    api_key = os.getenv("ANTHROPIC_API_KEY")
                    if api_key:
                        try:
                            import anthropic, json
                            client = anthropic.Anthropic(api_key=api_key)
                            places_str = "\n".join(f"- {p}" for p in uncat_places)
                            cats_str = ", ".join(existing_cats)
                            msg = client.messages.create(
                                model="claude-haiku-4-5-20251001",
                                max_tokens=512,
                                messages=[{
                                    "role": "user",
                                    "content": (
                                        f"다음 장소/가맹점명을 보고 카테고리를 유추해주세요.\n"
                                        f"사용 가능한 카테고리: {cats_str}, 미분류\n\n"
                                        f"장소 목록:\n{places_str}\n\n"
                                        f"JSON만 응답: {{\"장소명\": \"카테고리\", ...}}\n"
                                        f"확실하지 않으면 \"미분류\"로 설정하세요."
                                    ),
                                }],
                            )
                            text = msg.content[0].text
                            start, end = text.find("{"), text.rfind("}") + 1
                            if start >= 0 and end > start:
                                ai_suggestions = json.loads(text[start:end])
                            st.caption("✨ AI가 카테고리를 유추했습니다. 확인 후 수정하세요.")
                        except Exception as e:
                            st.caption(f"AI 유추 실패: {e}")

                    st.markdown("**미분류 장소 카테고리 지정** (규칙으로 저장됩니다)")
                    cols_per_row = 2
                    for i in range(0, len(uncat_places), cols_per_row):
                        row_cols = st.columns(cols_per_row)
                        for j, place in enumerate(uncat_places[i:i + cols_per_row]):
                            ai_cat = ai_suggestions.get(place, "미분류")
                            default_idx = cat_choices.index(ai_cat) if ai_cat in cat_choices else len(cat_choices) - 1
                            place_to_cat[place] = row_cols[j].selectbox(
                                f"'{place}'",
                                cat_choices,
                                index=default_idx,
                                key=f"place_cat_{place}",
                            )

                if st.button("💾 규칙 저장 및 가져오기"):
                    new_rules = {p: c for p, c in place_to_cat.items() if c != "미분류"}
                    if new_rules:
                        _update_category_rules(new_rules)
                        st.success(f"{len(new_rules)}개 장소가 카테고리 규칙에 추가됐습니다.")

                    # 업데이트된 규칙으로 재분류
                    final_rules = load_rules(_RULES_PATH)
                    final_categorized = categorize(txs, rules=final_rules)
                    inserted = db.insert_transactions(final_categorized)
                    st.success(f"{inserted}개 거래 추가됨 (중복 제외)")
                    st.session_state.csv_pending_txs = []
                    st.session_state.csv_show_analysis = False
                    st.rerun()

    # ── 수동 입력 ──────────────────────────────
    elif setting_sub == "수동 입력":
        st.title("✏️ 수동 입력")
        with st.form("manual_entry"):
            entry_date   = st.date_input("날짜", value=date.today())
            entry_amount = st.number_input("금액 (지출은 음수)", step=100)
            entry_place  = st.text_input("사용 장소")
            entry_desc   = st.text_input("메모")
            entry_cat    = st.text_input("카테고리", value="미분류")
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
