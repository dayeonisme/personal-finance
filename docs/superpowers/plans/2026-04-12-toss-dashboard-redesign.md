# 대시보드 Toss 리디자인 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `dashboard/app.py`의 CSS 주입 + HTML 컴포넌트만 교체해 플랫 타이포 + 라이트/다크 토글 디자인으로 바꾼다. Python 데이터 로직은 무변경.

**Architecture:** `dark_mode` 세션 상태로 테마를 관리하고, `_build_css()` 함수가 색상 변수를 받아 전체 CSS를 생성한다. 모든 HTML 컴포넌트 함수가 `dark` 인자를 받아 색상을 분기한다.

**Tech Stack:** Streamlit, Python f-string CSS injection, `st.markdown(unsafe_allow_html=True)`

---

## 파일 변경 범위

| 파일 | 변경 내용 |
|------|---------|
| `dashboard/app.py` | CSS 주입 블록 전면 교체, 헬퍼 함수 수정, 홈 페이지 HTML 컴포넌트 수정 |
| `dashboard/sidebar-options.html` | 삭제 (임시 파일) |
| `dashboard/card-options.html` | 삭제 (임시 파일) |
| `dashboard/approach-options.html` | 삭제 (임시 파일) |

---

### Task 1: dark_mode 세션 상태 추가

**Files:**
- Modify: `dashboard/app.py:46-55` (`_DEFAULTS` 딕셔너리)

- [ ] **Step 1: `_DEFAULTS`에 `dark_mode` 추가**

`dashboard/app.py` 의 `_DEFAULTS` 딕셔너리를 찾아 아래처럼 수정:

```python
_DEFAULTS = {
    "page": "홈",
    "settings_sub": "카테고리 규칙",
    "csv_pending_txs": [],
    "csv_show_analysis": False,
    "sidebar_narrow": False,
    "dark_mode": False,          # ← 추가
}
```

- [ ] **Step 2: CSS 블록 직전에 `dark` 변수 선언**

사이드바 width 계산 코드(`_narrow = st.session_state.sidebar_narrow`) 아래, CSS 주입 `st.markdown(f"""<style>...`) 바로 위에 삽입:

```python
dark = st.session_state.dark_mode

# ── 테마 색상 변수 ──
_BG     = "#0f0f13" if dark else "#fafafa"
_TEXT   = "#ffffff" if dark else "#191F28"
_SUB    = "#555566" if dark else "#8B95A1"
_LINE   = "#2a2a35" if dark else "#E8ECF0"
_CARD   = "#1a1a22" if dark else "#ffffff"     # data_editor 배경용
```

- [ ] **Step 3: 앱 실행 후 세션 상태 확인**

```bash
cd /path/to/personal-finance
source .venv/bin/activate
streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501
```

브라우저에서 에러 없이 로드되면 OK.

- [ ] **Step 4: 커밋**

```bash
git add dashboard/app.py
git commit -m "feat: add dark_mode session state and theme color variables"
```

---

### Task 2: CSS 주입 블록 전면 교체

**Files:**
- Modify: `dashboard/app.py:92-256` (현재 `st.markdown(f"""<style>...""")` 블록)

- [ ] **Step 1: 기존 CSS 블록 전체를 아래 코드로 교체**

`st.markdown(f"""<style>` 부터 `</style>\n""", unsafe_allow_html=True)` 끝까지를 아래로 교체:

```python
st.markdown(f"""
<style>
/* ── 전역 배경 ── */
.stApp {{ background: {_BG} !important; }}
.main .block-container {{
    padding: 2rem 2.2rem 2rem !important;
    max-width: 100% !important;
}}
header[data-testid="stHeader"] {{
    background: transparent !important;
    box-shadow: none !important;
}}

/* ── 사이드바 ── */
section[data-testid="stSidebar"] {{
    min-width: {_sw} !important;
    max-width: {_sw} !important;
    background: #0064FF !important;
    transition: min-width .2s ease, max-width .2s ease;
}}
section[data-testid="stSidebar"] > div:first-child {{
    background: #0064FF !important;
    padding: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    height: 100vh !important;
}}
[data-testid="collapsedControl"] {{ display: none !important; }}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] small {{
    color: rgba(255,255,255,0.85) !important;
}}

/* ── 사이드바 nav 버튼 ── */
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
section[data-testid="stSidebar"] .stButton > button strong,
section[data-testid="stSidebar"] .stButton > button b {{
    color: #0064FF !important;
    font-weight: 700 !important;
}}
section[data-testid="stSidebar"] .stButton > button:has(strong),
section[data-testid="stSidebar"] .stButton > button:has(b) {{
    background: white !important;
    color: #0064FF !important;
}}

/* ── 사이드바 토글 버튼 ── */
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

/* ── flex 성장 (설정 버튼 하단 고정) ── */
.sb-spacer {{ flex: 1 !important; min-height: 0 !important; }}

/* ── 탭 ── */
.stTabs [data-baseweb="tab-list"] {{
    background: {"#1a1a22" if dark else "white"} !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 2px !important;
    box-shadow: {"none" if dark else "0 1px 4px rgba(0,0,0,.06)"} !important;
    border-bottom: none !important;
    margin-bottom: 14px !important;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 15px !important;
    color: {_SUB} !important;
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
    color: {_TEXT} !important;
    font-weight: 900 !important;
    letter-spacing: -0.6px !important;
    font-size: 1.5rem !important;
    margin-bottom: 0 !important;
}}
h2 {{ color: {_TEXT} !important; font-weight: 700 !important; }}
h3 {{ color: {_TEXT} !important; font-weight: 700 !important; font-size: 1.05rem !important; }}
p {{ color: {_TEXT} !important; }}

/* ── 구분선 ── */
hr {{ border-color: {_LINE} !important; margin: 1.2rem 0 !important; }}

/* ── 알림 ── */
.stAlert {{ border-radius: 10px !important; font-size: 14px !important; }}

/* ── Selectbox ── */
[data-baseweb="select"] > div:first-child {{
    border-radius: 8px !important;
    border-color: {_LINE} !important;
    font-size: 15px !important;
    background: {"#1a1a22" if dark else "white"} !important;
    color: {_TEXT} !important;
}}

/* ── DataFrame ── */
[data-testid="stDataFrame"] {{
    border-radius: 12px !important;
    overflow: hidden !important;
}}

/* ── Multiselect ── */
[data-baseweb="tag"] {{ background: #0064FF !important; }}
</style>
""", unsafe_allow_html=True)
```

- [ ] **Step 2: 앱 실행 후 시각 확인**

```bash
streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501
```

- 페이지 배경이 `#fafafa`(연한 흰색)으로 변경됨을 확인
- 사이드바 파란색 유지 확인
- 콘솔 에러 없음 확인

- [ ] **Step 3: 커밋**

```bash
git add dashboard/app.py
git commit -m "feat: replace CSS injection with theme-aware variables (light/dark)"
```

---

### Task 3: 헬퍼 함수 교체 — `_section_header`, `_status_bar`

**Files:**
- Modify: `dashboard/app.py:315-330` (`_section_header`, `_status_bar` 함수)

- [ ] **Step 1: `_section_header` 함수를 플랫 타이포 스타일로 교체**

현재:
```python
def _section_header(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div style="margin:18px 0 10px">'
        f'<span style="font-size:17px;font-weight:700;color:#191F28">{title}</span>'
        + (f'<span style="font-size:14px;color:#8B95A1;margin-left:8px">{subtitle}</span>' if subtitle else "")
        + '</div>',
        unsafe_allow_html=True,
    )
```

교체:
```python
def _section_header(title: str, subtitle: str = "") -> None:
    sub_html = (f'<span style="font-size:12px;color:{_SUB};margin-left:8px;'
                f'font-weight:500;text-transform:none;letter-spacing:normal">{subtitle}</span>'
                if subtitle else "")
    st.markdown(
        f'<div style="margin:22px 0 8px;padding-bottom:6px;'
        f'border-bottom:2px solid {_TEXT}">'
        f'<span style="font-size:10px;font-weight:700;color:{_SUB};'
        f'text-transform:uppercase;letter-spacing:0.8px">{title}</span>'
        f'{sub_html}'
        f'</div>',
        unsafe_allow_html=True,
    )
```

- [ ] **Step 2: `_status_bar` 함수를 인라인 텍스트 스타일로 교체**

현재:
```python
def _status_bar(text: str, color: str = "#0064FF", bg: str = "#EBF2FF") -> None:
    st.markdown(
        f'<div style="background:{bg};border-radius:8px;padding:10px 14px;margin:10px 0;'
        f'font-size:14px;color:{color};font-weight:500">{text}</div>',
        unsafe_allow_html=True,
    )
```

교체:
```python
def _status_bar(text: str, color: str = "#0064FF", bg: str = "#EBF2FF") -> None:
    st.markdown(
        f'<div style="padding:8px 0;margin:6px 0;font-size:13px;'
        f'color:{color};font-weight:600;display:flex;align-items:center;gap:6px">'
        f'<span style="width:6px;height:6px;border-radius:50%;background:{color};'
        f'display:inline-block;flex-shrink:0"></span>{text}'
        f'</div>',
        unsafe_allow_html=True,
    )
```

- [ ] **Step 3: 앱에서 홈 → 섹션 헤더 시각 확인**

브라우저에서 "카테고리별 지출", "최근 거래내역" 섹션 헤더가 작은 대문자 + 파란 하단선으로 바뀌는지 확인.

- [ ] **Step 4: 커밋**

```bash
git add dashboard/app.py
git commit -m "feat: redesign section_header (flat uppercase) and status_bar (inline dot)"
```

---

### Task 4: 홈 — 다크모드 토글 버튼 + 헤더 레이아웃

**Files:**
- Modify: `dashboard/app.py:402-421` (홈 페이지 헤더 블록)

- [ ] **Step 1: 홈 페이지 헤더를 3-컬럼 레이아웃으로 교체**

현재:
```python
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
            ...
        st.markdown("</div>", unsafe_allow_html=True)
```

교체 (동기화 버튼 로직은 그대로 유지, 레이아웃만 변경):
```python
if page == "홈":
    today = date.today()
    c_title, c_toggle, c_sync = st.columns([4, 1, 1])
    with c_title:
        st.markdown(f"<h1>이번달 요약</h1>", unsafe_allow_html=True)
        st.markdown(
            f'<p style="color:{_SUB};font-size:14px;margin-top:2px;font-weight:500">'
            f'{today.year}년 {today.month}월</p>',
            unsafe_allow_html=True,
        )
    with c_toggle:
        st.markdown('<div style="padding-top:16px">', unsafe_allow_html=True)
        _toggle_label = "🌙 다크" if not dark else "☀ 라이트"
        if st.button(_toggle_label, use_container_width=True):
            st.session_state.dark_mode = not dark
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with c_sync:
        st.markdown('<div style="padding-top:16px">', unsafe_allow_html=True)
        if st.button("🔄 동기화", use_container_width=True, type="primary"):
            try:
                urllib.request.urlopen(
                    urllib.request.Request("http://127.0.0.1:9000/run", method="POST"), timeout=5
                )
                st.success("동기화 요청 완료!")
            except Exception as e:
                st.error(f"webhook_server.py가 실행 중인지 확인하세요: {e}")
        st.markdown("</div>", unsafe_allow_html=True)
```

- [ ] **Step 2: 토글 클릭 동작 확인**

브라우저에서 "🌙 다크" 버튼 클릭 → 배경이 `#0f0f13`으로 전환, 텍스트 흰색으로 전환 확인.
다시 "☀ 라이트" 클릭 → 원래대로 복귀 확인.

- [ ] **Step 3: 커밋**

```bash
git add dashboard/app.py
git commit -m "feat: add dark mode toggle button to home header"
```

---

### Task 5: 홈 — 수입/지출/순수익 플랫 그리드

**Files:**
- Modify: `dashboard/app.py:452-465` (`_metric_card` 함수 + 사용 부분)

- [ ] **Step 1: `_metric_card` 함수를 플랫 스타일로 교체**

현재:
```python
def _metric_card(label: str, value: str, val_color: str, delta_html: str) -> str:
    return (
        f'<div style="background:white;border-radius:14px;padding:20px 22px;'
        f'box-shadow:0 1px 8px rgba(0,0,0,.07)">'
        f'<div style="font-size:14px;color:#8B95A1;font-weight:500;margin-bottom:10px">{label}</div>'
        f'<div style="font-size:24px;font-weight:800;letter-spacing:-.5px;color:{val_color}">{value}</div>'
        f'<div style="margin-top:6px">{delta_html}</div>'
        f'</div>'
    )
```

교체:
```python
def _metric_card(label: str, value: str, val_color: str, delta_html: str) -> str:
    return (
        f'<div style="padding:14px 0 14px 0">'
        f'<div style="font-size:9px;font-weight:700;color:{_SUB};text-transform:uppercase;'
        f'letter-spacing:0.8px;margin-bottom:6px">{label}</div>'
        f'<div style="font-size:22px;font-weight:900;letter-spacing:-0.6px;color:{val_color}">{value}</div>'
        f'<div style="margin-top:4px">{delta_html}</div>'
        f'</div>'
    )
```

- [ ] **Step 2: 메트릭 3개를 선 구분 그리드로 감싸기**

현재:
```python
c1, c2, c3 = st.columns(3)
c1.markdown(_metric_card("수입",   ...), unsafe_allow_html=True)
c2.markdown(_metric_card("지출",   ...), unsafe_allow_html=True)
c3.markdown(_metric_card("순수익", ...), unsafe_allow_html=True)
```

교체 (3개 컬럼 대신 단일 HTML 그리드):
```python
m1 = _metric_card("수입",   f"{inc_this:,}원",      "#00B493", _delta(inc_this - inc_last))
m2 = _metric_card("지출",   f"{abs(exp_this):,}원", "#F03C3C", _delta(abs(exp_this) - abs(exp_last), bad_if_positive=True))
m3 = _metric_card("순수익", f"{net_this:,}원",       _TEXT,     _delta(net_this - net_last))

st.markdown(
    f'<div style="display:grid;grid-template-columns:repeat(3,1fr);'
    f'border-top:1px solid {_LINE};border-bottom:1px solid {_LINE};margin:8px 0">'
    f'<div style="border-right:1px solid {_LINE};padding-right:20px">{m1}</div>'
    f'<div style="border-right:1px solid {_LINE};padding:0 20px">{m2}</div>'
    f'<div style="padding-left:20px">{m3}</div>'
    f'</div>',
    unsafe_allow_html=True,
)
st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
```

- [ ] **Step 3: 시각 확인**

홈 페이지에서 수입/지출/순수익이 카드 없이 선으로 구분된 3개 셀로 표시되는지 확인.

- [ ] **Step 4: 커밋**

```bash
git add dashboard/app.py
git commit -m "feat: replace metric cards with flat bordered grid"
```

---

### Task 6: 홈 — 카테고리별 지출 플랫 그리드

**Files:**
- Modify: `dashboard/app.py:469-489` (카테고리 그리드 블록)

- [ ] **Step 1: 카테고리 카드 박스를 플랫 행으로 교체**

현재 (카드 박스):
```python
cols = st.columns(min(len(top_cats), 4))
for i, (cat, amount) in enumerate(top_cats):
    icon = CAT_ICON.get(cat, "💳")
    cols[i % 4].markdown(
        f'<div style="background:white;border-radius:12px;padding:14px 12px;'
        f'text-align:center;box-shadow:0 1px 6px rgba(0,0,0,.05)">'
        ...
        f'</div>',
        unsafe_allow_html=True,
    )
```

교체 (플랫 리스트 → 전체를 하나의 HTML 블록으로):
```python
rows_html = ""
for cat, amount in top_cats:
    icon = CAT_ICON.get(cat, "💳")
    rows_html += (
        f'<div style="display:flex;align-items:center;padding:10px 0;'
        f'border-bottom:1px solid {_LINE}">'
        f'<span style="font-size:20px;width:32px;flex-shrink:0">{icon}</span>'
        f'<span style="font-size:13px;color:{_SUB};flex:1;margin-left:10px">{cat}</span>'
        f'<span style="font-size:15px;font-weight:800;color:{_TEXT};letter-spacing:-0.3px">'
        f'{amount:,}원</span>'
        f'</div>'
    )
st.markdown(
    f'<div style="margin-bottom:8px">{rows_html}</div>',
    unsafe_allow_html=True,
)
```

- [ ] **Step 2: 시각 확인**

홈에서 카테고리 지출이 아이콘 + 이름 + 금액의 플랫 행 리스트로 표시되는지 확인.

- [ ] **Step 3: 커밋**

```bash
git add dashboard/app.py
git commit -m "feat: replace category cards with flat row list"
```

---

### Task 7: 홈 — 예산 달성률 플랫 행

**Files:**
- Modify: `dashboard/app.py:491-527` (예산 달성률 블록)

- [ ] **Step 1: 예산 카드 박스를 플랫 행으로 교체**

현재 `budget_cols[i % 4].markdown(...)` 블록 전체를 아래로 교체:

```python
if budgets:
    _section_header("예산 달성률")
    _cat_totals: dict[str, int] = {}
    for r in this_month:
        if r["amount"] < 0:
            _cat_totals[r["category"]] = _cat_totals.get(r["category"], 0) + abs(r["amount"])

    budget_html = ""
    for cat, limit in budgets.items():
        spent = _cat_totals.get(cat, 0)
        pct = min(spent / limit * 100, 100) if limit > 0 else 0
        over = spent > limit
        bar_color = "#F03C3C" if over else "#0064FF"
        val_color = "#F03C3C" if over else _TEXT
        icon = CAT_ICON.get(cat, "💳")
        cat_safe = _html.escape(cat)
        budget_html += (
            f'<div style="padding:10px 0;border-bottom:1px solid {_LINE}">'
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">'
            f'<div style="display:flex;align-items:center;gap:8px">'
            f'<span style="font-size:18px">{icon}</span>'
            f'<span style="font-size:13px;color:{_SUB}">{cat_safe}</span>'
            f'</div>'
            f'<span style="font-size:13px;font-weight:800;color:{val_color}">'
            f'{spent:,} / {limit:,}원</span>'
            f'</div>'
            f'<div style="background:{_LINE};border-radius:2px;height:3px">'
            f'<div style="background:{bar_color};width:{pct:.1f}%;height:100%;border-radius:2px"></div>'
            f'</div>'
            f'<div style="font-size:10px;color:{"#F03C3C" if over else _SUB};text-align:right;margin-top:3px">'
            f'{"초과 " if over else ""}{pct:.0f}%</div>'
            f'</div>'
        )
    st.markdown(f'<div>{budget_html}</div>', unsafe_allow_html=True)
```

- [ ] **Step 2: 시각 확인**

예산이 설정된 경우 홈에서 예산 행이 플랫하게 표시되는지 확인. 예산이 없으면 이 섹션 자체가 표시 안 됨.

- [ ] **Step 3: 커밋**

```bash
git add dashboard/app.py
git commit -m "feat: replace budget cards with flat progress rows"
```

---

### Task 8: 홈 — 최근 거래내역 플랫 리스트

**Files:**
- Modify: `dashboard/app.py:529-560` (최근 거래내역 블록)

- [ ] **Step 1: 거래 리스트 카드 박스 제거**

현재:
```python
tx_html = (
    '<div style="background:white;border-radius:14px;overflow:hidden;'
    'box-shadow:0 1px 8px rgba(0,0,0,.07)">'
)
for i, r in enumerate(recent):
    sep = "" if i == len(recent) - 1 else "border-bottom:1px solid #F2F4F7;"
    ...
    tx_html += (
        f'<div style="display:flex;align-items:center;padding:13px 18px;{sep}">'
        f'<div style="width:38px;height:38px;background:#EBF2FF;border-radius:50%;...">...'
        ...
    )
tx_html += "</div>"
```

교체:
```python
tx_html = '<div>'
for i, r in enumerate(recent):
    sep = "" if i == len(recent) - 1 else f"border-bottom:1px solid {_LINE};"
    icon = CAT_ICON.get(r["category"], "💳")
    amt_col = "#00B493" if r["amount"] > 0 else "#F03C3C"
    sign = "+" if r["amount"] > 0 else ""
    place = r["place"] or r["description"] or "알수없음"
    tx_html += (
        f'<div style="display:flex;align-items:center;padding:11px 0;{sep}">'
        f'<span style="font-size:20px;width:28px;flex-shrink:0">{icon}</span>'
        f'<div style="flex:1;min-width:0;margin-left:12px">'
        f'<div style="font-size:14px;font-weight:700;color:{_TEXT};'
        f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{place}</div>'
        f'<div style="font-size:11px;color:{_SUB};margin-top:2px">'
        f'{r["category"]} · {r["date"]}</div>'
        f'</div>'
        f'<div style="font-size:14px;font-weight:800;color:{amt_col};'
        f'flex-shrink:0;letter-spacing:-0.3px">'
        f'{sign}{r["amount"]:,}원</div>'
        f'</div>'
    )
tx_html += '</div>'
st.markdown(tx_html, unsafe_allow_html=True)
```

- [ ] **Step 2: 시각 확인**

최근 거래 리스트가 흰 카드 박스 없이 선 구분 행으로 표시되는지 확인.

- [ ] **Step 3: 커밋**

```bash
git add dashboard/app.py
git commit -m "feat: replace transaction card box with flat separator rows"
```

---

### Task 9: 거래내역 페이지 — 합계 플랫 표시

**Files:**
- Modify: `dashboard/app.py:676-686` (합계 표시 블록)

- [ ] **Step 1: 합계 카드 박스를 플랫 인라인으로 교체**

현재:
```python
st.markdown(
    f'<div style="background:white;border-radius:10px;padding:10px 16px;margin-top:8px;'
    f'display:flex;gap:24px;font-size:15px;box-shadow:0 1px 4px rgba(0,0,0,.05)">'
    ...
    f'</div>',
    unsafe_allow_html=True,
)
```

교체:
```python
st.markdown(
    f'<div style="padding:10px 0;margin-top:8px;border-top:1px solid {_LINE};'
    f'display:flex;gap:24px;font-size:14px">'
    f'<span style="color:{_SUB}">총 {len(df)}건</span>'
    f'<span style="color:#00B493;font-weight:700">수입 +{total_inc:,}원</span>'
    f'<span style="color:#F03C3C;font-weight:700">지출 {total_exp:,}원</span>'
    f'</div>',
    unsafe_allow_html=True,
)
```

- [ ] **Step 2: 시각 확인**

거래내역 페이지 하단 합계 행이 흰 카드 없이 선 + 인라인 텍스트로 표시되는지 확인.

- [ ] **Step 3: 커밋**

```bash
git add dashboard/app.py
git commit -m "feat: replace transaction summary card with flat inline row"
```

---

### Task 10: 임시 HTML 파일 삭제 + 전체 테스트

**Files:**
- Delete: `dashboard/sidebar-options.html`
- Delete: `dashboard/card-options.html`
- Delete: `dashboard/approach-options.html`

- [ ] **Step 1: 임시 파일 삭제**

```bash
rm dashboard/sidebar-options.html dashboard/card-options.html dashboard/approach-options.html
```

- [ ] **Step 2: 전체 테스트 실행**

```bash
cd /path/to/personal-finance
source .venv/bin/activate
pytest -v
```

Expected: 모든 테스트 PASS. 실패 시 오류 메시지 확인 후 수정.

- [ ] **Step 3: 라이트/다크 전체 페이지 수동 확인**

다음 체크리스트를 라이트 + 다크 각각 확인:
- [ ] 홈: 수입/지출/순수익 플랫 그리드
- [ ] 홈: 카테고리별 지출 플랫 행
- [ ] 홈: 예산 달성률 플랫 행 (예산 있을 경우)
- [ ] 홈: 최근 거래내역 플랫 행
- [ ] 거래내역: 합계 플랫 인라인
- [ ] 차트: 배경/텍스트 색상 전환
- [ ] 설정: 배경/텍스트 색상 전환
- [ ] 사이드바: 라이트/다크 무관하게 파란색 유지

- [ ] **Step 4: 최종 커밋**

```bash
git add -A
git commit -m "feat: remove temp HTML files, complete Toss-style redesign"
```

---

## 성공 기준 체크리스트

- [ ] 라이트/다크 토글이 모든 페이지에서 즉시 전환됨
- [ ] 카드 박스가 사라지고 선+타이포 기반 레이아웃으로 표시됨
- [ ] 사이드바는 기존 블루 유지
- [ ] 기존 모든 기능(데이터 표시, 편집, CSV, 예산, 차트)이 정상 동작
- [ ] `pytest -v` 전체 통과
