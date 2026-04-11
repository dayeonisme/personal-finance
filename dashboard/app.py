from __future__ import annotations

import base64
import html as _html
import io
import json
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import altair as alt
import pandas as pd
import streamlit as st
import yaml
from dotenv import load_dotenv

load_dotenv()

_AI_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

from db.database import Database
from models import CategorizedTransaction, Transaction
from parser.categorizer import categorize, load_rules

st.set_page_config(page_title="가계부", page_icon="💰", layout="wide")

# ─────────────────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────────────────
_RULES_PATH = Path(__file__).parent.parent / "config" / "categories.yaml"
CHART_H = 320

CAT_ICON: dict[str, str] = {
    "식비": "🍜", "카페": "☕", "교통": "🚇", "쇼핑": "🛍️",
    "의료/건강": "💊", "구독/OTT": "📺", "통신": "📱", "주거": "🏠",
    "경조사/후원": "🎁", "수입": "💰", "미분류": "📌",
}

# ─────────────────────────────────────────────────────────
# 세션 상태
# ─────────────────────────────────────────────────────────
_DEFAULTS = {
    "page": "홈",
    "settings_sub": "카테고리 규칙",
    "csv_pending_txs": [],
    "csv_show_analysis": False,
    "sidebar_narrow": False,
    "dark_mode": False,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ─────────────────────────────────────────────────────────
# DB
# ─────────────────────────────────────────────────────────
@st.cache_resource
def _get_db() -> Database:
    return Database()

db = _get_db()

# ─────────────────────────────────────────────────────────
# 사이드바 토글 아이콘 (SVG → base64 data-URI)
# ─────────────────────────────────────────────────────────
def _svg_b64(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()

_narrow = st.session_state.sidebar_narrow
_sw = "66px" if _narrow else "220px"

dark = st.session_state.dark_mode

# ── 테마 색상 변수 ──
_BG     = "#0f0f13" if dark else "#fafafa"
_TEXT   = "#ffffff" if dark else "#191F28"
_SUB    = "#555566" if dark else "#8B95A1"
_LINE   = "#2a2a35" if dark else "#E8ECF0"
_CARD   = "#1a1a22" if dark else "#ffffff"

# 넓은 상태일 때 버튼 아이콘 = 왼쪽 패널 강조 (접기)
# 좁은 상태일 때 버튼 아이콘 = 오른쪽 패널 강조 (펼치기)
_toggle_icon_url = _svg_b64(
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" fill="none">'
    + (
        '<rect x="1.5" y="2" width="13" height="12" rx="2.5" stroke="white" stroke-width="1.4" opacity=".85"/>'
        '<rect x="1.5" y="2" width="5" height="12" rx="2.5" fill="white" opacity=".85"/>'
        if not _narrow else
        '<rect x="1.5" y="2" width="13" height="12" rx="2.5" stroke="white" stroke-width="1.4" opacity=".85"/>'
        '<rect x="9.5" y="2" width="5" height="12" rx="2.5" fill="white" opacity=".85"/>'
    )
    + '</svg>'
)

# ─────────────────────────────────────────────────────────
# CSS 주입
# ─────────────────────────────────────────────────────────
st.markdown(f"""
<style>
/* ── 전역 ── */
.stApp {{ background: #F2F4F7 !important; }}
.main .block-container {{
    padding: 2rem 2.2rem 2rem !important;
    max-width: 100% !important;
}}
header[data-testid="stHeader"] {{
    background: transparent !important;
    box-shadow: none !important;
}}

/* ── 사이드바 컨테이너 ── */
section[data-testid="stSidebar"] {{
    min-width: {_sw} !important;
    max-width: {_sw} !important;
    background: #0064FF !important;
    transition: min-width .2s ease, max-width .2s ease;
}}
/* 사이드바 flex 레이아웃 → 설정 버튼 하단 고정 */
section[data-testid="stSidebar"] > div:first-child {{
    background: #0064FF !important;
    padding: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    height: 100vh !important;
}}
[data-testid="collapsedControl"] {{ display: none !important; }}

/* ── 사이드바 텍스트 ── */
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] small {{
    color: rgba(255,255,255,0.85) !important;
}}

/* ── 사이드바 nav 버튼 (기본 = 비활성) ── */
section[data-testid="stSidebar"] .stButton > button {{
    background: rgba(255,255,255,0.08) !important;
    border: none !important;
    color: rgba(255,255,255,0.88) !important;
    text-align: left !important;
    padding: 11px 14px !important;
    border-radius: 10px !important;
    width: 100% !important;
    font-size: 15px !important;
    font-weight: 500 !important;
    margin-bottom: 4px !important;
    box-shadow: none !important;
    justify-content: flex-start !important;
    letter-spacing: -0.1px !important;
}}
section[data-testid="stSidebar"] .stButton > button:hover {{
    background: rgba(255,255,255,0.18) !important;
    color: white !important;
    border: none !important;
}}
/* 활성 항목: 굵은 텍스트 → 흰 배경 + 파란 텍스트 */
section[data-testid="stSidebar"] .stButton > button strong,
section[data-testid="stSidebar"] .stButton > button b {{
    color: #0064FF !important;
    font-weight: 700 !important;
}}
/* 활성 버튼 자체는 흰 배경 */
section[data-testid="stSidebar"] .stButton > button:has(strong),
section[data-testid="stSidebar"] .stButton > button:has(b) {{
    background: white !important;
    color: #0064FF !important;
}}

/* ── 토글 버튼 (패널 아이콘) ── */
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] .stButton > button {{
    background: rgba(255,255,255,0.18) !important;
    color: white !important;
    width: 30px !important;
    height: 30px !important;
    min-height: 30px !important;
    padding: 0 !important;
    border: none !important;
    border-radius: 8px !important;
    margin: 0 !important;
    font-size: 16px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    flex-shrink: 0 !important;
    line-height: 1 !important;
}}
section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] .stButton > button:hover {{
    background: rgba(255,255,255,0.32) !important;
    border: none !important;
}}

/* ── flex 성장 영역 (설정 버튼 밀기용) ── */
.sb-spacer {{ flex: 1 !important; min-height: 0 !important; }}

/* ── 탭 ── */
.stTabs [data-baseweb="tab-list"] {{
    background: white !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 2px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,.06) !important;
    border-bottom: none !important;
    margin-bottom: 14px !important;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 15px !important;
    color: #8B95A1 !important;
    padding: 7px 18px !important;
    border-bottom: none !important;
}}
.stTabs [aria-selected="true"] {{
    background: #0064FF !important;
    color: white !important;
}}
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] {{ display: none !important; }}

/* ── 일반 버튼 ── */
.stButton > button {{
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 15px !important;
    transition: opacity .15s !important;
}}
button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {{
    background: #0064FF !important;
    color: white !important;
    border: none !important;
}}

/* ── 헤딩 ── */
h1 {{
    color: #191F28 !important;
    font-weight: 800 !important;
    letter-spacing: -0.5px !important;
    font-size: 1.65rem !important;
    margin-bottom: 0 !important;
}}
h2 {{ color: #191F28 !important; font-weight: 700 !important; }}
h3 {{ color: #191F28 !important; font-weight: 700 !important; font-size: 1.05rem !important; }}

/* ── 구분선 ── */
hr {{ border-color: #E8ECF0 !important; margin: 1.2rem 0 !important; }}

/* ── 알림 ── */
.stAlert {{ border-radius: 10px !important; font-size: 14px !important; }}

/* ── Selectbox ── */
[data-baseweb="select"] > div:first-child {{
    border-radius: 8px !important;
    border-color: #E0E6EF !important;
    font-size: 15px !important;
}}

/* ── DataFrame ── */
[data-testid="stDataFrame"] {{
    border-radius: 12px !important;
    overflow: hidden !important;
}}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────
# 공통 헬퍼
# ─────────────────────────────────────────────────────────
def _year_month_selector(key_prefix: str):
    today = date.today()
    available_years = db.get_available_years() or list(range(today.year, today.year - 3, -1))
    year_options = ["전체"] + [str(y) for y in available_years]
    default_year_idx = year_options.index(str(today.year)) if str(today.year) in year_options else 1
    col1, col2 = st.columns(2)
    year_val = col1.selectbox("년도", year_options, index=default_year_idx, key=f"{key_prefix}_year")
    month_val = col2.selectbox("월", ["전체"] + list(range(1, 13)), index=today.month, key=f"{key_prefix}_month")
    return (None if year_val == "전체" else int(year_val),
            None if month_val == "전체" else int(month_val))


def _get_rows(year, month):
    if year is None:
        return db.get_transactions()
    if month is None:
        return db.get_transactions(year=year)
    return db.get_transactions(year=year, month=month)


def _infer_col_idx(cols: list[str], hints: set[str], with_none: bool = False) -> int:
    for i, col in enumerate(cols):
        if col.lower().strip() in hints:
            return i + (1 if with_none else 0)
    return 0


def _update_category_rules(place_to_cat: dict[str, str]) -> None:
    rules = load_rules(_RULES_PATH)
    rule_list = rules.get("rules", [])
    cat_to_rule: dict[str, dict] = {}
    for rule in rule_list:
        cat = rule["category"]
        if cat in cat_to_rule:
            for kw in rule.get("match", []):
                if kw not in cat_to_rule[cat]["match"]:
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


def _section_header(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div style="margin:18px 0 10px">'
        f'<span style="font-size:17px;font-weight:700;color:#191F28">{title}</span>'
        + (f'<span style="font-size:14px;color:#8B95A1;margin-left:8px">{subtitle}</span>' if subtitle else "")
        + '</div>',
        unsafe_allow_html=True,
    )


def _status_bar(text: str, color: str = "#0064FF", bg: str = "#EBF2FF") -> None:
    st.markdown(
        f'<div style="background:{bg};border-radius:8px;padding:10px 14px;margin:10px 0;'
        f'font-size:14px;color:{color};font-weight:500">{text}</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────
# 사이드바
# ─────────────────────────────────────────────────────────
with st.sidebar:
    # ── 로고 + 토글 행 ────────────��─────────────
    if not _narrow:
        c_logo, c_toggle = st.columns([5, 1], gap="small")
        with c_logo:
            st.markdown(
                '<div style="color:white;font-size:20px;font-weight:800;letter-spacing:-.4px;'
                'padding:20px 2px 18px 10px;border-bottom:1px solid rgba(255,255,255,.18)">'
                '💰 가계부'
                '<div style="font-size:11px;font-weight:400;opacity:.5;margin-top:3px">Personal Finance</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        with c_toggle:
            st.markdown('<div style="padding-top:20px;padding-right:4px">', unsafe_allow_html=True)
            # 패널 닫기 아이콘: ⊟ (박스 마이너스)
            if st.button("⊟", key="sb_toggle", help="사이드바 접기"):
                st.session_state.sidebar_narrow = True
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            '<div style="text-align:center;color:white;font-size:24px;'
            'padding:20px 0 18px;border-bottom:1px solid rgba(255,255,255,.18)">'
            '💰</div>',
            unsafe_allow_html=True,
        )
        # 패널 열기 아이콘: ⊞ (박스 플러스)
        c_toggle2 = st.columns([1])[0]
        with c_toggle2:
            if st.button("⊞", key="sb_toggle", help="사이드바 펼치기",
                         use_container_width=True):
                st.session_state.sidebar_narrow = False
                st.rerun()

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

    # ── 메인 nav ────────────────────────────────
    _page = st.session_state.page
    for _nav, _icon in [("홈", "🏠"), ("거래내역", "📋"), ("차트", "📊")]:
        _active = _page == _nav
        _lbl = (f"**{_icon} {_nav}**" if _active else f"{_icon} {_nav}") if not _narrow \
               else (f"**{_icon}**" if _active else _icon)
        if st.button(_lbl, key=f"nav_{_nav}", use_container_width=True):
            st.session_state.page = _nav
            st.rerun()

    # ── flex 성장 → 설정 버튼을 하단으로 밀기 ──
    st.markdown('<div class="sb-spacer"></div>', unsafe_allow_html=True)

    # ── 설정 (하단 고정) ────────────────────────
    st.markdown('<div style="padding-bottom:12px">', unsafe_allow_html=True)
    _set_active = _page == "설정"
    _set_lbl = ("**⚙️ 설정**" if _set_active else "⚙️ 설정") if not _narrow \
               else ("**⚙️**" if _set_active else "⚙️")
    if st.button(_set_lbl, key="nav_설정", use_container_width=True):
        st.session_state.page = "설정"
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

page = st.session_state.page


# ─────────────────────────────────────────────────────────
# 홈
# ─────────────────────────────────────────────────────────
if page == "홈":
    today = date.today()
    c_title, c_sync = st.columns([4, 1])
    with c_title:
        st.markdown(f"<h1>이번달 요약</h1>", unsafe_allow_html=True)
        st.markdown(
            f'<p style="color:#8B95A1;font-size:15px;margin-top:0">{today.year}년 {today.month}월</p>',
            unsafe_allow_html=True,
        )
    with c_sync:
        st.markdown('<div style="padding-top:14px">', unsafe_allow_html=True)
        if st.button("🔄 지금 동기화", use_container_width=True, type="primary"):
            try:
                urllib.request.urlopen(
                    urllib.request.Request("http://127.0.0.1:9000/run", method="POST"), timeout=5
                )
                st.success("동기화 요청 완료!")
            except Exception as e:
                st.error(f"webhook_server.py가 실행 중인지 확인하세요: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

    log = db.get_latest_crawl_log()
    if log:
        _status_map = {"success": "✅ 성공", "failed": "❌ 실패", "running": "⏳ 실행 중"}
        _status_txt = _status_map.get(log["status"], log["status"])
        _bg = "#F0FFF8" if log["status"] == "success" else "#FFF3F3" if log["status"] == "failed" else "#FFF9EB"
        _col = "#00B493" if log["status"] == "success" else "#F03C3C" if log["status"] == "failed" else "#FF9500"
        _status_bar(f"{_status_txt} · 마지막 동기화: {str(log['started_at'])[:16]}", color=_col, bg=_bg)

    # 이번달 / 지난달 데이터
    this_month = db.get_transactions(year=today.year, month=today.month)
    last_m = today.month - 1 if today.month > 1 else 12
    last_y = today.year if today.month > 1 else today.year - 1
    last_month = db.get_transactions(year=last_y, month=last_m)

    inc_this  = sum(r["amount"] for r in this_month if r["amount"] > 0)
    exp_this  = sum(r["amount"] for r in this_month if r["amount"] < 0)
    inc_last  = sum(r["amount"] for r in last_month if r["amount"] > 0)
    exp_last  = sum(r["amount"] for r in last_month if r["amount"] < 0)
    net_this  = inc_this + exp_this
    net_last  = inc_last + exp_last

    def _delta(delta: int, bad_if_positive: bool = False) -> str:
        if delta == 0:
            return '<span style="color:#8B95A1;font-size:13px">변동 없음</span>'
        bad = (delta > 0) if bad_if_positive else (delta < 0)
        col = "#F03C3C" if bad else "#00B493"
        arrow = "▲" if delta > 0 else "▼"
        return f'<span style="color:{col};font-size:13px;font-weight:500">{arrow} {abs(delta):,}원 vs 지난달</span>'

    def _metric_card(label: str, value: str, val_color: str, delta_html: str) -> str:
        return (
            f'<div style="background:white;border-radius:14px;padding:20px 22px;'
            f'box-shadow:0 1px 8px rgba(0,0,0,.07)">'
            f'<div style="font-size:14px;color:#8B95A1;font-weight:500;margin-bottom:10px">{label}</div>'
            f'<div style="font-size:24px;font-weight:800;letter-spacing:-.5px;color:{val_color}">{value}</div>'
            f'<div style="margin-top:6px">{delta_html}</div>'
            f'</div>'
        )

    c1, c2, c3 = st.columns(3)
    c1.markdown(_metric_card("수입",   f"{inc_this:,}원",      "#00B493", _delta(inc_this - inc_last)), unsafe_allow_html=True)
    c2.markdown(_metric_card("지출",   f"{abs(exp_this):,}원", "#F03C3C", _delta(abs(exp_this) - abs(exp_last), bad_if_positive=True)), unsafe_allow_html=True)
    c3.markdown(_metric_card("순수익", f"{net_this:,}원",       "#191F28", _delta(net_this - net_last)), unsafe_allow_html=True)

    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)

    # 카테고리별 지출
    expenses = [r for r in this_month if r["amount"] < 0]
    if expenses:
        cat_totals: dict[str, int] = {}
        for r in expenses:
            cat_totals[r["category"]] = cat_totals.get(r["category"], 0) + abs(r["amount"])
        top_cats = sorted(cat_totals.items(), key=lambda x: -x[1])[:8]

        _section_header("카테고리별 지출")
        cols = st.columns(min(len(top_cats), 4))
        for i, (cat, amount) in enumerate(top_cats):
            icon = CAT_ICON.get(cat, "💳")
            cols[i % 4].markdown(
                f'<div style="background:white;border-radius:12px;padding:14px 12px;'
                f'text-align:center;box-shadow:0 1px 6px rgba(0,0,0,.05)">'
                f'<div style="font-size:24px;margin-bottom:6px">{icon}</div>'
                f'<div style="font-size:13px;color:#8B95A1;margin-bottom:4px">{cat}</div>'
                f'<div style="font-size:16px;font-weight:700;color:#191F28">{amount:,}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── 예산 달성률 ────────────────────────────────
    budgets = db.get_budgets()
    if budgets:
        _section_header("예산 달성률")
        _cat_totals: dict[str, int] = {}
        for r in this_month:
            if r["amount"] < 0:
                _cat_totals[r["category"]] = _cat_totals.get(r["category"], 0) + abs(r["amount"])

        budget_cols = st.columns(min(len(budgets), 4))
        for i, (cat, limit) in enumerate(budgets.items()):
            spent = _cat_totals.get(cat, 0)
            pct = min(spent / limit * 100, 100) if limit > 0 else 0
            over = spent > limit
            bar_color = "#F03C3C" if over else "#0064FF"
            label_color = "#F03C3C" if over else "#191F28"
            icon = CAT_ICON.get(cat, "💳")
            cat_safe = _html.escape(cat)
            budget_cols[i % 4].markdown(
                f'<div style="background:white;border-radius:12px;padding:14px 12px;'
                f'box-shadow:0 1px 6px rgba(0,0,0,.05);margin-bottom:8px">'
                f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:8px">'
                f'<span style="font-size:20px">{icon}</span>'
                f'<span style="font-size:13px;color:#8B95A1">{cat_safe}</span>'
                f'</div>'
                f'<div style="font-size:15px;font-weight:700;color:{label_color};margin-bottom:6px">'
                f'{spent:,} / {limit:,}원</div>'
                f'<div style="background:#F2F4F7;border-radius:4px;height:6px;overflow:hidden">'
                f'<div style="background:{bar_color};width:{pct:.1f}%;height:100%;'
                f'border-radius:4px"></div>'
                f'</div>'
                f'<div style="font-size:12px;color:{"#F03C3C" if over else "#8B95A1"};'
                f'margin-top:4px;text-align:right">'
                f'{"초과 " if over else ""}{pct:.0f}%</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # 최근 거래내역
    all_rows = db.get_transactions()
    recent = sorted(all_rows, key=lambda r: r["date"], reverse=True)[:5]
    if recent:
        _section_header("최근 거래내역")
        tx_html = (
            '<div style="background:white;border-radius:14px;overflow:hidden;'
            'box-shadow:0 1px 8px rgba(0,0,0,.07)">'
        )
        for i, r in enumerate(recent):
            sep = "" if i == len(recent) - 1 else "border-bottom:1px solid #F2F4F7;"
            icon = CAT_ICON.get(r["category"], "💳")
            amt_col = "#00B493" if r["amount"] > 0 else "#F03C3C"
            sign = "+" if r["amount"] > 0 else ""
            place = r["place"] or r["description"] or "알수없음"
            tx_html += (
                f'<div style="display:flex;align-items:center;padding:13px 18px;{sep}">'
                f'<div style="width:38px;height:38px;background:#EBF2FF;border-radius:50%;'
                f'display:flex;align-items:center;justify-content:center;'
                f'font-size:17px;margin-right:12px;flex-shrink:0">{icon}</div>'
                f'<div style="flex:1;min-width:0">'
                f'<div style="font-size:15px;font-weight:600;color:#191F28;'
                f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{place}</div>'
                f'<div style="font-size:13px;color:#8B95A1;margin-top:2px">'
                f'{r["category"]} · {r["date"]}</div>'
                f'</div>'
                f'<div style="font-size:15px;font-weight:700;color:{amt_col};flex-shrink:0">'
                f'{sign}{r["amount"]:,}원</div>'
                f'</div>'
            )
        tx_html += "</div>"
        st.markdown(tx_html, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────
# 거래내역
# ─────────────────────────────────────────────────────────
elif page == "거래내역":
    st.markdown("<h1>거래내역</h1>", unsafe_allow_html=True)

    # 필터 행
    fc1, fc2, fc3, fc4 = st.columns([1, 1, 2, 1])
    today = date.today()
    available_years = db.get_available_years() or list(range(today.year, today.year - 3, -1))
    year_opts = ["전체"] + [str(y) for y in available_years]
    def_y = year_opts.index(str(today.year)) if str(today.year) in year_opts else 1
    year_sel = fc1.selectbox("년도", year_opts, index=def_y, key="tx_year", label_visibility="collapsed")
    month_sel = fc2.selectbox("월", ["전체"] + list(range(1, 13)), index=today.month, key="tx_month", label_visibility="collapsed")

    year = None if year_sel == "전체" else int(year_sel)
    month = None if month_sel == "전체" else int(month_sel)
    rows = _get_rows(year, month)

    if not rows:
        st.info("거래내역이 없습니다.")
    else:
        df = pd.DataFrame(rows).fillna("").replace("nan", "")

        # 카테고리 필터 (selectbox)
        categories = ["전체"] + sorted(df["category"].unique().tolist())
        selected_cat = fc3.selectbox("카테고리", categories, key="tx_cat_filter", label_visibility="collapsed")
        if selected_cat != "전체":
            df = df[df["category"] == selected_cat]

        # 열 선택
        all_cols = ["date", "place", "description", "amount", "category", "source", "is_edited"]
        chosen = st.multiselect("표시할 열", ["전체"] + all_cols, default=["전체"], key="tx_cols",
                                label_visibility="collapsed")
        visible_cols = all_cols if "전체" in chosen else [c for c in all_cols if c in chosen] or all_cols

        select_all = st.checkbox("전체 행 선택", key="tx_select_all")

        editor_df = df[["id"] + visible_cols].copy().fillna("")
        editor_df.insert(0, "선택", select_all)

        # place 컬럼 설정: 카테고리 태그 없음 + 글자 크기 90%
        col_cfg: dict = {
            "선택":        st.column_config.CheckboxColumn("선택", width="small"),
            "id":          st.column_config.NumberColumn("ID", disabled=True, width="small"),
            "date":        st.column_config.DateColumn("날짜", disabled=True),
            "amount":      st.column_config.NumberColumn("금액", disabled=True, format="%d"),
            "category":    st.column_config.TextColumn("카테고리"),
            "place":       st.column_config.TextColumn("사용 장소"),
            "description": st.column_config.TextColumn("메모"),
            "source":      st.column_config.TextColumn("출처", disabled=True),
            "is_edited":   st.column_config.CheckboxColumn("수정됨", disabled=True),
        }

        # place 글자 크기 90% — data_editor column_config width 조정으로 근사
        if "place" in visible_cols:
            col_cfg["place"] = st.column_config.TextColumn("사용 장소", width="medium")

        edited = st.data_editor(
            editor_df,
            use_container_width=True,
            hide_index=True,
            column_config=col_cfg,
            key="tx_editor",
        )

        # 버튼 행 (저장 / 삭제 / CSV)
        btn1, btn2, btn3 = st.columns(3)

        export_df = df[visible_cols].copy()
        period_label = (
            f"{year}년_{month}월" if year and month
            else f"{year}년" if year else "전체"
        )
        btn3.download_button(
            "⬇️ CSV 내보내기",
            data=export_df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"거래내역_{period_label}.csv",
            mime="text/csv",
            use_container_width=True,
        )

        if btn1.button("💾 변경 사항 저장", use_container_width=True, type="primary"):
            saved = 0
            for _, orig_row in editor_df.iterrows():
                row_id = int(orig_row["id"])
                er = edited[edited["id"] == row_id]
                if er.empty:
                    continue
                e = er.iloc[0]
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

        if btn2.button("🗑️ 선택 삭제", use_container_width=True):
            selected_ids = edited[edited["선택"] == True]["id"].tolist()
            if not selected_ids:
                st.warning("삭제할 행을 선택하세요.")
            else:
                deleted = db.delete_transactions([int(i) for i in selected_ids])
                st.success(f"{deleted}개 행 삭제됨.")
                st.rerun()

        # 합계 표시
        total_exp = sum(r["amount"] for r in rows if r["amount"] < 0)
        total_inc = sum(r["amount"] for r in rows if r["amount"] > 0)
        st.markdown(
            f'<div style="background:white;border-radius:10px;padding:10px 16px;margin-top:8px;'
            f'display:flex;gap:24px;font-size:15px;box-shadow:0 1px 4px rgba(0,0,0,.05)">'
            f'<span style="color:#8B95A1">총 {len(df)}건</span>'
            f'<span style="color:#00B493;font-weight:600">수입 +{total_inc:,}원</span>'
            f'<span style="color:#F03C3C;font-weight:600">지출 {total_exp:,}원</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────
# 차트
# ─────────────────────────────────────────────────────────
elif page == "차트":
    st.markdown("<h1>재무 분석</h1>", unsafe_allow_html=True)

    today = date.today()

    def collect_monthly(n: int = 6):
        records = []
        for m_back in range(n - 1, -1, -1):
            tm = today.month - m_back
            ty = today.year
            while tm <= 0:
                tm += 12
                ty -= 1
            rows = db.get_transactions(year=ty, month=tm)
            income  = sum(r["amount"] for r in rows if r["amount"] > 0)
            expense = sum(r["amount"] for r in rows if r["amount"] < 0)
            records.append({
                "month":  f"{ty}-{tm:02d}",
                "수입":   income,
                "지출":   abs(expense),
                "순수익": income + expense,
                "저축률": round((income + expense) / income * 100, 1) if income > 0 else 0,
            })
        return pd.DataFrame(records).set_index("month")

    monthly_df = collect_monthly(6)

    _section_header("최근 6개월 추이")
    tab1, tab2, tab3 = st.tabs(["수입 / 지출", "순수익", "저축률 (%)"])

    with tab1:
        df_long = (monthly_df[["수입", "지출"]].reset_index()
                   .melt(id_vars="month", var_name="구분", value_name="금액"))
        st.altair_chart(
            alt.Chart(df_long).mark_line(point=True).encode(
                x=alt.X("month:N", title="월", sort=None),
                y=alt.Y("금액:Q", scale=alt.Scale(domainMin=0), title="금액 (원)"),
                color=alt.Color("구분:N", scale=alt.Scale(
                    domain=["수입", "지출"], range=["#00B493", "#F03C3C"])),
                tooltip=["month:N", "구분:N", "금액:Q"],
            ).properties(height=CHART_H),
            use_container_width=True,
        )

    with tab2:
        df_net = monthly_df[["순수익"]].reset_index()
        y_min = min(0, int(df_net["순수익"].min()) - 10_000)
        st.altair_chart(
            alt.Chart(df_net).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                x=alt.X("month:N", title="월", sort=None),
                y=alt.Y("순수익:Q", scale=alt.Scale(domainMin=y_min), title="금액 (원)"),
                color=alt.condition(
                    alt.datum["순수익"] >= 0,
                    alt.value("#0064FF"),
                    alt.value("#F03C3C"),
                ),
                tooltip=["month:N", "순수익:Q"],
            ).properties(height=CHART_H),
            use_container_width=True,
        )

    with tab3:
        df_sr = monthly_df[["저축률"]].reset_index()
        st.altair_chart(
            alt.Chart(df_sr).mark_line(point=True, color="#0064FF").encode(
                x=alt.X("month:N", title="월", sort=None),
                y=alt.Y("저축률:Q", scale=alt.Scale(domainMin=0), title="저축률 (%)"),
                tooltip=["month:N", "저축률:Q"],
            ).properties(height=CHART_H),
            use_container_width=True,
        )
        st.caption("저축률 = (수입 − 지출) / 수입 × 100")

    st.divider()

    year, month = _year_month_selector("chart")
    rows = _get_rows(year, month)
    period_label = (f"{year}년 {month}월" if year and month
                    else f"{year}년" if year else "전체 기간")

    _section_header(f"{period_label} 카테고리별 지출")
    if not rows:
        st.info("데이터가 없습니다.")
    else:
        df = pd.DataFrame(rows)
        expenses = df[df["amount"] < 0].copy()
        expenses["amount_abs"] = expenses["amount"].abs()

        if expenses.empty:
            st.info("지출 내역이 없습니다.")
        else:
            cat_df = (expenses.groupby("category")["amount_abs"].sum()
                      .reset_index().sort_values("amount_abs", ascending=False))
            cat_df.columns = ["카테고리", "금액"]

            c1, c2 = st.columns([3, 2])
            with c1:
                st.altair_chart(
                    alt.Chart(cat_df).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
                                               color="#0064FF").encode(
                        x=alt.X("카테고리:N", sort="-y", title=""),
                        y=alt.Y("금액:Q", scale=alt.Scale(domainMin=0), title="금액 (원)"),
                        tooltip=["카테고리:N", "금액:Q"],
                    ).properties(height=CHART_H),
                    use_container_width=True,
                )
            with c2:
                total_exp = cat_df["금액"].sum()
                disp = cat_df.copy()
                disp["비율"] = (disp["금액"] / total_exp * 100).round(1).astype(str) + "%"
                disp["금액"] = disp["금액"].apply(lambda x: f"{x:,.0f}원")
                st.dataframe(disp, use_container_width=True, hide_index=True)

    st.divider()

    if month and year:
        _section_header("전월 대비 카테고리 변화")
        prev_m = month - 1 if month > 1 else 12
        prev_y = year if month > 1 else year - 1
        prev_rows = db.get_transactions(year=prev_y, month=prev_m)

        def cat_expense(r_list):
            d: dict[str, int] = {}
            for r in r_list:
                if r["amount"] < 0:
                    d[r["category"]] = d.get(r["category"], 0) + abs(r["amount"])
            return d

        curr_cat = cat_expense(rows)
        prev_cat = cat_expense(prev_rows)
        all_cats = sorted(set(curr_cat) | set(prev_cat))

        if all_cats:
            cmp_rows = []
            for c in all_cats:
                cmp_rows.append({"카테고리": c, "월": f"{prev_y}-{prev_m:02d}", "금액": prev_cat.get(c, 0)})
                cmp_rows.append({"카테고리": c, "월": f"{year}-{month:02d}", "금액": curr_cat.get(c, 0)})
            st.altair_chart(
                alt.Chart(pd.DataFrame(cmp_rows)).mark_bar(
                    cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                    x=alt.X("카테고리:N", title=""),
                    y=alt.Y("금액:Q", scale=alt.Scale(domainMin=0), title="금액 (원)"),
                    color=alt.Color("월:N", scale=alt.Scale(
                        domain=[f"{prev_y}-{prev_m:02d}", f"{year}-{month:02d}"],
                        range=["#BDD7FF", "#0064FF"])),
                    xOffset="월:N",
                    tooltip=["카테고리:N", "월:N", "금액:Q"],
                ).properties(height=CHART_H),
                use_container_width=True,
            )

    st.divider()

    _section_header("일별 지출 패턴")
    if rows:
        df_day = pd.DataFrame(rows)
        df_day = df_day[df_day["amount"] < 0].copy()
        if not df_day.empty:
            df_day["date"] = pd.to_datetime(df_day["date"])
            daily = df_day.groupby("date")["amount"].sum().abs().reset_index()
            daily.columns = ["날짜", "지출"]
            st.altair_chart(
                alt.Chart(daily).mark_area(opacity=0.15, color="#0064FF", line={"color": "#0064FF"}).encode(
                    x=alt.X("날짜:T", title="날짜"),
                    y=alt.Y("지출:Q", scale=alt.Scale(domainMin=0), title="금액 (원)"),
                    tooltip=["날짜:T", "지출:Q"],
                ).properties(height=CHART_H),
                use_container_width=True,
            )
        else:
            st.info("지출 데이터가 없습니다.")

    st.divider()

    _section_header("TOP 10 지출 항목")
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


# ─────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────
elif page == "설정":
    setting_sub = st.session_state.settings_sub

    # 서브 탭
    sub_tabs = ["카테고리 규칙", "예산 관리", "CSV 업로드", "수동 입력"]
    st.markdown(
        '<div style="display:flex;gap:8px;margin-bottom:20px">'
        + "".join(
            f'<div style="padding:7px 16px;border-radius:20px;font-size:13px;font-weight:600;cursor:pointer;'
            f'background:{"#0064FF" if s == setting_sub else "#fff"};'
            f'color:{"white" if s == setting_sub else "#8B95A1"};'
            f'box-shadow:0 1px 4px rgba(0,0,0,.07)">{s}</div>'
            for s in sub_tabs
        )
        + "</div>",
        unsafe_allow_html=True,
    )
    sub_cols = st.columns(len(sub_tabs))
    for sub, col in zip(sub_tabs, sub_cols):
        if col.button(sub, key=f"sub_{sub}", use_container_width=True,
                      type="primary" if sub == setting_sub else "secondary"):
            st.session_state.settings_sub = sub
            st.rerun()

    st.divider()

    # ── AI 재분류 함수 ──────────────────────────────
    def _ai_recategorize_unclassified() -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            st.error("ANTHROPIC_API_KEY가 .env에 없습니다.")
            return
        all_rows_ = db.get_transactions()
        uncat = [r for r in all_rows_ if r["category"] == "미분류"]
        if not uncat:
            st.info("미분류 항목이 없습니다.")
            return
        unique_places = sorted(set(
            (r["place"] or r["description"]).strip()
            for r in uncat if (r["place"] or r["description"]).strip()
        ))
        if not unique_places:
            st.info("분류 기준이 될 장소/메모가 없습니다.")
            return
        existing_cats = sorted(set(
            rule["category"] for rule in load_rules(_RULES_PATH).get("rules", [])
        ))
        cats_str = ", ".join(existing_cats)
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model=_AI_MODEL, max_tokens=1024,
                messages=[{"role": "user", "content": (
                    f"한국 가계부 앱입니다. 아래 장소/가맹점명을 보고 카테고리를 유추해주세요.\n"
                    f"기존 카테고리: {cats_str}\n"
                    f"기존 카테고리에 없으면 새 카테고리를 만들어도 됩니다.\n"
                    f"확실하지 않으면 \"미분류\"로 설정하세요.\n\n"
                    f"장소 목록:\n" + "\n".join(f"- {p}" for p in unique_places) + "\n\n"
                    f"JSON만 응답 (다른 텍스트 없이): {{\"장소명\": \"카테고리\", ...}}"
                )}],
            )
            text = msg.content[0].text.strip()
            s, e_ = text.find("{"), text.rfind("}") + 1
            if s < 0 or e_ <= s:
                st.error("AI 응답 파싱 실패")
                return
            place_to_cat: dict[str, str] = json.loads(text[s:e_])
        except Exception as e:
            st.error(f"AI 호출 실패: {e}")
            return
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

    # ── 카테고리 규칙 ──────────────────────────────
    if setting_sub == "카테고리 규칙":
        st.markdown("<h1>카테고리 규칙</h1>", unsafe_allow_html=True)

        all_rows_s = db.get_transactions()
        unedited_count = sum(1 for r in all_rows_s if r["is_edited"] == 0)
        uncat_count    = sum(1 for r in all_rows_s if r["category"] == "미분류")

        col_rule, col_ai = st.columns(2)
        if col_rule.button("🔄 규칙으로 전체 재분류", use_container_width=True, type="primary",
                           help="수동 편집하지 않은 모든 항목을 현재 YAML 규칙으로 다시 분류합니다."):
            with st.spinner("규칙 적용 중..."):
                unedited_rows = db.get_unedited_transactions()
                txs = [Transaction(
                    date=date.fromisoformat(r["date"]), amount=r["amount"],
                    description=r["description"], place=r["place"],
                    source=r["source"], raw_source=r["raw_source"],
                ) for r in unedited_rows]
                categorized = categorize(txs)
                updates = {
                    unedited_rows[i]["id"]: ct.category
                    for i, ct in enumerate(categorized)
                    if ct.category != unedited_rows[i]["category"]
                }
                changed = db.bulk_update_categories(updates)
            st.success(f"{changed}개 항목 재분류 완료 (대상: {unedited_count}개).")
            st.rerun()

        if uncat_count > 0:
            col_ai.warning(f"미분류 항목: **{uncat_count}개**")
            if col_ai.button("🤖 AI로 미분류 재분류", use_container_width=True):
                with st.spinner("AI가 분류 중..."):
                    _ai_recategorize_unclassified()
        else:
            col_ai.success("미분류 항목 없음 ✓")

        st.divider()
        try:
            rules = load_rules(_RULES_PATH)
            rule_list = rules.get("rules", [])
            default_cat = rules.get("default_category", "미분류")
            rows_data = [
                {"번호": i, "카테고리": r.get("category", ""),
                 "포함 키워드": ", ".join(r.get("match", []))}
                for i, r in enumerate(rule_list, 1)
            ]
            if rows_data:
                st.dataframe(pd.DataFrame(rows_data), use_container_width=True, hide_index=True,
                             column_config={
                                 "번호": st.column_config.NumberColumn(width="small"),
                                 "카테고리": st.column_config.TextColumn(width="medium"),
                                 "포함 키워드": st.column_config.TextColumn(width="large"),
                             })
            st.info(f"매칭 없을 때 기본 카테고리: **{default_cat}**")
        except FileNotFoundError:
            st.warning("config/categories.yaml 파일이 없습니다.")
        st.caption("규칙을 수정하려면 `config/categories.yaml` 파일을 직접 편집하세요.")

    # ── 예산 관리 ──────────────────────────────────
    elif setting_sub == "예산 관리":
        st.markdown("<h1>예산 관리</h1>", unsafe_allow_html=True)

        budgets = db.get_budgets()
        all_categories = list(CAT_ICON.keys())

        if budgets:
            _section_header("설정된 예산")
            for cat, limit in budgets.items():
                col_cat, col_amt, col_del = st.columns([3, 3, 1])
                cat_safe = _html.escape(cat)
                col_cat.markdown(
                    f'<div style="padding:8px 0;font-size:15px;font-weight:600">'
                    f'{CAT_ICON.get(cat, "💳")} {cat_safe}</div>',
                    unsafe_allow_html=True,
                )
                col_amt.markdown(
                    f'<div style="padding:8px 0;font-size:15px;color:#0064FF;font-weight:700">'
                    f'월 {limit:,}원</div>',
                    unsafe_allow_html=True,
                )
                if col_del.button("삭제", key=f"del_budget_{cat}"):
                    db.delete_budget(cat)
                    st.rerun()
        else:
            st.info("설정된 예산이 없습니다. 아래에서 추가하세요.")

        st.divider()

        _section_header("예산 추가")
        already_set = set(budgets.keys())
        available_cats = [c for c in all_categories if c not in already_set]
        if not available_cats:
            st.success("모든 카테고리에 예산이 설정되어 있습니다.")
        else:
            bc1, bc2, bc3 = st.columns([3, 3, 2])
            new_cat = bc1.selectbox("카테고리", available_cats, key="budget_cat_sel")
            new_limit = bc2.number_input("월 예산 (원)", min_value=1000, step=10000,
                                         value=100000, key="budget_limit_input")
            bc3.markdown('<div style="padding-top:28px">', unsafe_allow_html=True)
            if bc3.button("➕ 추가", use_container_width=True, type="primary"):
                db.set_budget(new_cat, int(new_limit))
                st.success(f"{new_cat} 예산 {int(new_limit):,}원 설정됨.")
                st.rerun()
            bc3.markdown("</div>", unsafe_allow_html=True)

    # ── CSV 업로드 ──────────────────────────────────
    elif setting_sub == "CSV 업로드":
        st.markdown("<h1>CSV 업로드</h1>", unsafe_allow_html=True)
        uploaded = st.file_uploader("거래내역 CSV 파일", type=["csv"])

        if uploaded:
            raw_bytes = uploaded.read()
            df = pd.read_csv(io.BytesIO(raw_bytes))
            first_col = df.columns[0]
            empty_mask = df[first_col].isna() | (df[first_col].astype(str).str.strip() == "")
            if empty_mask.any():
                df = df.iloc[:empty_mask.idxmax()]

            st.info(f"총 {len(df)}개 행 감지됨.")
            st.dataframe(df.fillna(""), height=260, use_container_width=True)

            cols = df.columns.tolist()
            none_option = ["(없음)"] + cols

            DATE_HINTS   = {"날짜","일자","date","거래일","거래일시","거래날짜","transaction_date","거래 일자"}
            AMOUNT_HINTS = {"금액","amount","거래금액","출금금액","입출금액","입출금금액","transaction_amount","출금"}
            PLACE_HINTS  = {"장소","place","사용처","가맹점","가맹점명","merchant","사용장소","사용 장소","이용장소"}
            DESC_HINTS   = {"메모","memo","내용","description","적요","거래내용","비고","거래 내용"}
            SRC_HINTS    = {"출처","source","계좌","카드","account","card","카드명","계좌명"}

            st.markdown("**컬럼 매핑** (자동 유추됨, 수정 가능)")
            c1, c2 = st.columns(2)
            date_col   = c1.selectbox("날짜 *", cols, index=_infer_col_idx(cols, DATE_HINTS), key="csv_date")
            amount_col = c2.selectbox("금액 * (숫자)", cols, index=_infer_col_idx(cols, AMOUNT_HINTS), key="csv_amount")
            c3, c4 = st.columns(2)
            place_col  = c3.selectbox("사용 장소", none_option, index=_infer_col_idx(cols, PLACE_HINTS, True), key="csv_place")
            desc_col   = c4.selectbox("메모", none_option, index=_infer_col_idx(cols, DESC_HINTS, True), key="csv_desc")
            source_col = st.selectbox("출처 (계좌/카드)", none_option, index=_infer_col_idx(cols, SRC_HINTS, True), key="csv_source")

            def parse_txs(dataframe) -> list[Transaction]:
                txs = []
                for _, row in dataframe.iterrows():
                    try:
                        raw_amount = str(row[amount_col]).replace(",", "").strip()
                        txs.append(Transaction(
                            date=date.fromisoformat(str(row[date_col])[:10]),
                            amount=int(float(raw_amount)),
                            description=str(row[desc_col]).strip() if desc_col != "(없음)" and pd.notna(row[desc_col]) else "",
                            place=str(row[place_col]).strip() if place_col != "(없음)" and pd.notna(row[place_col]) else "",
                            source=str(row[source_col]).strip() if source_col != "(없음)" and pd.notna(row[source_col]) else "csv",
                            raw_source="csv",
                        ))
                    except Exception as ex:
                        st.warning(f"행 건너뜀: {ex}")
                return txs

            if st.button("🔍 분석하기", type="primary"):
                st.session_state.csv_pending_txs = parse_txs(df)
                st.session_state.csv_show_analysis = True

            if st.session_state.csv_show_analysis and st.session_state.csv_pending_txs:
                txs = st.session_state.csv_pending_txs
                categorized = categorize(txs)
                cat_counts: dict[str, int] = {}
                for ct in categorized:
                    cat_counts[ct.category] = cat_counts.get(ct.category, 0) + 1
                st.markdown("**카테고리별 분류 결과**")
                st.dataframe(
                    pd.DataFrame([{"카테고리": k, "건수": v} for k, v in sorted(cat_counts.items())]),
                    use_container_width=True, hide_index=True,
                )

                uncat_places = sorted(set(
                    ct.place for ct in categorized if ct.category == "미분류" and ct.place
                ))
                place_to_cat: dict[str, str] = {}

                if uncat_places:
                    existing_cats = sorted(set(
                        r["category"] for r in load_rules(_RULES_PATH).get("rules", [])
                    ))
                    cat_choices = existing_cats + ["미분류"]
                    ai_suggestions: dict[str, str] = {}
                    api_key_csv = os.getenv("ANTHROPIC_API_KEY")
                    if api_key_csv:
                        try:
                            import anthropic as _anth
                            _client = _anth.Anthropic(api_key=api_key_csv)
                            _msg = _client.messages.create(
                                model=_AI_MODEL, max_tokens=512,
                                messages=[{"role": "user", "content": (
                                    f"다음 장소/가맹점명을 보고 카테고리를 유추해주세요.\n"
                                    f"사용 가능한 카테고리: {', '.join(existing_cats)}, 미분류\n\n"
                                    f"장소 목록:\n" + "\n".join(f"- {p}" for p in uncat_places) + "\n\n"
                                    f"JSON만 응답: {{\"장소명\": \"카테고리\", ...}}\n"
                                    f"확실하지 않으면 \"미분류\"로 설정하세요."
                                )}],
                            )
                            _text = _msg.content[0].text
                            _s, _e = _text.find("{"), _text.rfind("}") + 1
                            if _s >= 0 and _e > _s:
                                ai_suggestions = json.loads(_text[_s:_e])
                            st.caption("✨ AI가 카테고리를 유추했습니다. 확인 후 수정하세요.")
                        except Exception as _ex:
                            st.caption(f"AI 유추 실패: {_ex}")

                    st.markdown("**미분류 장소 카테고리 지정** (규칙으로 저장됩니다)")
                    for i in range(0, len(uncat_places), 2):
                        row_cols = st.columns(2)
                        for j, place in enumerate(uncat_places[i:i + 2]):
                            ai_cat = ai_suggestions.get(place, "미분류")
                            default_idx = cat_choices.index(ai_cat) if ai_cat in cat_choices else len(cat_choices) - 1
                            place_to_cat[place] = row_cols[j].selectbox(
                                f"'{place}'", cat_choices, index=default_idx,
                                key=f"place_cat_{place}",
                            )

                if st.button("💾 규칙 저장 및 가져오기", type="primary"):
                    new_rules = {p: c for p, c in place_to_cat.items() if c != "미분류"}
                    if new_rules:
                        _update_category_rules(new_rules)
                        st.success(f"{len(new_rules)}개 장소가 카테고리 규칙에 추가됐습니다.")
                    final_rules = load_rules(_RULES_PATH)
                    final_categorized = categorize(txs, rules=final_rules)
                    inserted = db.insert_transactions(final_categorized)
                    st.success(f"{inserted}개 거래 추가됨 (중복 제외)")
                    st.session_state.csv_pending_txs = []
                    st.session_state.csv_show_analysis = False
                    st.rerun()

    # ── 수동 입력 ──────────────────────────────────
    elif setting_sub == "수동 입력":
        st.markdown("<h1>수동 입력</h1>", unsafe_allow_html=True)
        with st.form("manual_entry"):
            c1, c2 = st.columns(2)
            entry_date   = c1.date_input("날짜", value=date.today())
            entry_amount = c2.number_input("금액 (지출은 음수)", step=100)
            c3, c4 = st.columns(2)
            entry_place  = c3.text_input("사용 장소")
            _manual_cats = list(CAT_ICON.keys())
            entry_cat    = c4.selectbox("카테고리", _manual_cats,
                                        index=_manual_cats.index("미분류") if "미분류" in _manual_cats else 0)
            entry_desc   = st.text_input("메모")
            entry_source = st.text_input("출처", value="manual")
            if st.form_submit_button("➕ 추가", type="primary", use_container_width=True):
                if entry_amount == 0:
                    st.warning("금액을 입력하세요 (지출은 음수).")
                else:
                    db.insert_transactions([CategorizedTransaction(
                        date=entry_date, amount=int(entry_amount),
                        description=entry_desc, place=entry_place,
                        source=entry_source, raw_source="manual",
                        category=entry_cat,
                    )])
                    st.success("추가되었습니다.")
