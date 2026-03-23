# Personal Finance Tracker — Design Spec

**Date:** 2026-03-22
**Status:** Approved

---

## Overview

A local-first personal finance automation tool (가계부) that replaces manual bookkeeping. Automatically crawls transaction data from Toss (which aggregates KB Bank, KB Card, Woori Bank, Woori Card, T-money, local gift vouchers), categorizes transactions, stores them in a local SQLite database, and presents them via a Streamlit dashboard.

---

## Goals

- Automate daily transaction collection from Toss via web crawling
- Auto-categorize transactions based on configurable rules
- Provide a dashboard with monthly summaries, category breakdowns, and month-over-month comparisons
- Support manual entry and CSV upload as fallback input methods
- Keep financial data strictly local; only code goes to GitHub

---

## Architecture

```
personal_finance/
├── crawler/
│   ├── base.py          # Abstract base class with context manager protocol
│   ├── toss.py          # Toss crawler (Playwright)
│   └── ...              # Future: naver_pay.py, kakao_pay.py, etc.
├── parser/
│   └── categorizer.py   # Rule-based auto-categorization
├── db/
│   └── database.py      # SQLite CRUD layer
├── dashboard/
│   └── app.py           # Streamlit UI
├── config/
│   └── categories.yaml  # Categorization rules (e.g., "스타벅스" → 식비)
├── data/                # .gitignore — SQLite DB file lives here
├── logs/                # .gitignore — crawl log files
├── .env                 # .gitignore — Toss credentials
├── docker-compose.yml   # n8n scheduler
├── requirements.txt     # Python dependencies (Python 3.11+)
└── run.py               # Crawling entrypoint
```

---

## Data Flow

```
[n8n Scheduler: daily, calls HTTP webhook on host]
        ↓
[run.py] → exits 0 on success, non-zero on failure
        ↓
[Playwright Crawler] → Toss login (session reuse) → fetch transactions
        ↓
[Parser / Categorizer] → apply rules from categories.yaml
        ↓
[SQLite] → deduplicate → store
        ↓
[Streamlit Dashboard] → display

Manual fallbacks:
- Direct transaction entry in dashboard
- CSV file upload
- "지금 동기화" button → POST to local webhook → triggers run.py
```

---

## Database Schema

```sql
CREATE TABLE transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        DATE NOT NULL,
    amount      INTEGER NOT NULL,        -- negative = expense, positive = income
    description TEXT NOT NULL,
    category    TEXT,                    -- NULL displayed as "미분류" in dashboard
    source      TEXT NOT NULL,           -- sub-account level: 'kb_card', 'woori_bank', 'tmoneys', etc.
    raw_source  TEXT NOT NULL,           -- aggregator: 'toss', 'naver_pay', 'manual', 'csv'
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_edited   BOOLEAN DEFAULT 0,       -- set to 1 when user manually edits this row
    UNIQUE(date, amount, description, source)  -- source is sub-account to handle same-day same-amount dedup
);

CREATE TABLE crawl_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  DATETIME NOT NULL,
    finished_at DATETIME,
    status      TEXT NOT NULL,           -- 'running', 'success', 'failed'
    rows_added  INTEGER DEFAULT 0,
    error_msg   TEXT
);
```

---

## Transaction Data Contract

All crawlers return `list[Transaction]`. The categorizer adds the `category` field and returns `list[CategorizedTransaction]`. The DB layer inserts `CategorizedTransaction` objects.

```python
@dataclass
class Transaction:
    date:        date
    amount:      int          # negative = expense, positive = income (KRW)
    description: str          # merchant name or memo as shown in the source app
    source:      str          # sub-account identifier: 'kb_card', 'woori_bank', 'tmoneys', etc.
    raw_source:  str          # aggregator name: 'toss', 'naver_pay', 'manual', 'csv'

@dataclass
class CategorizedTransaction(Transaction):
    category: str = "미분류"  # never NULL; dataclass enforces this default
```

**Categorizer interface:**
```python
def categorize(transactions: list[Transaction]) -> list[CategorizedTransaction]: ...
```

Any crawler returning a different shape will fail at type-check time. The DB layer only accepts `CategorizedTransaction`.

---

## Crawler Design

Each crawler is a context manager inheriting from `BaseCrawler`:

```python
class BaseCrawler:
    def __enter__(self) -> "BaseCrawler": ...
    def __exit__(self, *args) -> None:
        try:
            self.logout()
        except Exception:
            pass  # log but never mask the original exception

    def login(self) -> None: ...
    def fetch_transactions(self, start_date: date, end_date: date) -> list[Transaction]: ...
    def logout(self) -> None: ...
```

Usage pattern enforced throughout the codebase:
```python
with TossCrawler() as crawler:
    transactions = crawler.fetch_transactions(start, end)
```

`__exit__` wraps `logout()` in a bare `try/except` so that a crash inside `logout()` (e.g., browser process already dead) never masks the original exception that caused the `with` block to exit. Logout failures are logged but not re-raised.

---

## Toss Authentication Strategy

Toss requires OTP or QR scan on first login. The approach:

1. **First run (manual)**: User runs `python run.py --login` which opens a visible browser. User completes OTP manually. Playwright saves the authenticated session to `data/toss_session.json` (gitignored).
2. **Subsequent runs (automated)**: Playwright loads `data/toss_session.json` via `storage_state`. No OTP required as long as the session is valid.
3. **Session expiry**: If the session has expired, `run.py` exits with code `2` (auth error). n8n detects the non-zero exit and sends an alert (desktop notification or log). The user re-runs `python run.py --login` to refresh the session.

`data/toss_session.json` is gitignored. Never committed.

---

## run.py Interface

```
python run.py [--login] [--days N] [--dry-run]

--login    Open browser visibly for manual OTP; save session after success
--days N   Fetch last N days of transactions (default: 7)
--dry-run  Fetch and parse but do not write to DB or crawl_log; print results to stdout

Exit codes:
  0  Success
  1  Unexpected error (see logs/crawl.log)
  2  Authentication failure (session expired — run with --login)
```

`run.py` always writes a row to the `crawl_log` table with status and error details.

---

## n8n ↔ Host Execution

n8n runs in Docker; `run.py` runs on the host. The integration uses a lightweight webhook:

1. A small host-side HTTP server (`webhook_server.py`) binds to `127.0.0.1:9000` and listens for POST requests.
2. On receiving a request it runs `python run.py` as a subprocess and returns the exit code.
3. n8n calls `http://host.docker.internal:9000/run` daily on schedule.
4. The "지금 동기화" Streamlit button also POSTs to the same endpoint.

`webhook_server.py` **must** bind to `127.0.0.1` only, not `0.0.0.0`. Binding to all interfaces would expose an unauthenticated code-execution endpoint to the local network.

This avoids mounting the host filesystem into Docker and keeps the Python environment on the host where it is already configured.

---

## Categorization

Rule-based matching defined in `config/categories.yaml`:

```yaml
rules:
  - match: ["스타벅스", "카페베네", "투썸"]
    category: 식비
  - match: ["쿠팡", "마켓컬리"]
    category: 쇼핑
  - match: ["버스", "지하철", "티머니"]
    category: 교통
default_category: "미분류"   # applied when no rule matches
```

Rules are applied top-down; first match wins. `NULL` is never stored — unmatched transactions receive `"미분류"`. Users can edit rules via the Settings page in the dashboard or directly in the YAML file.

---

## Dashboard Pages

| Page | Content |
|------|---------|
| **홈** | This month's income/expense summary, comparison vs. last month, last sync status |
| **거래내역** | Transaction list with date/category/source filters; editable field: **category only** (edits set `is_edited=1`; next crawl will not overwrite the category). `description` is read-only to preserve the deduplication key. |
| **차트** | Category pie chart, monthly bar chart |
| **설정** | Category rule management, CSV upload, manual transaction entry |

**Edit + deduplication rule**: Only `category` is editable in the dashboard. `description` is intentionally read-only because it is part of the UNIQUE deduplication key `(date, amount, description, source)` — editing it would cause the next crawl to insert a duplicate row under the original description. When a user edits a category, `is_edited=1` is set on that row. The DB upsert logic skips the category field for rows where `is_edited=1`, preserving the user's override across future crawls.

---

## Scheduling (n8n via Docker)

```yaml
# docker-compose.yml
services:
  n8n:
    image: n8nio/n8n
    ports:
      - "127.0.0.1:5678:5678"
    volumes:
      - ./n8n_data:/home/node/.n8n
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

`host.docker.internal` allows n8n to reach the host-side webhook server.

---

## Logging

- Every `run.py` execution writes to `logs/crawl.log` (rotating, max 10 MB).
- Every run uses a two-phase write to `crawl_log`:
  1. **On start**: INSERT a row with `status='running'`, `started_at=now`.
  2. **On finish** (in a `finally` block): UPDATE the row with `status='success'|'failed'`, `finished_at=now`, `rows_added`, `error_msg`.
- Stale `'running'` rows (started more than 30 minutes ago) are treated as `'failed'` by all dashboard queries. This handles crashes that prevent the UPDATE from executing.
- The Streamlit 홈 page shows "마지막 동기화: YYYY-MM-DD HH:MM (성공/실패)".

---

## Security & Git

| Item | Handling |
|------|---------|
| `data/` (SQLite, session JSON) | `.gitignore` — never committed |
| `.env` (Toss credentials) | `.gitignore` — never committed; restrict file to current Windows user via `icacls` |
| `logs/` | `.gitignore` |
| Source code | GitHub private repository only |
| Streamlit port | Bound to `127.0.0.1:8501` only — not exposed on the network |
| Webhook server port | Bound to `127.0.0.1:9000` only — not exposed on the network |
| n8n admin UI | Bound to `127.0.0.1:5678` only — not exposed on the network |
| SQLite encryption | Not encrypted at rest; BitLocker full-disk encryption is the recommended host-level protection |

**Credential risk note**: `.env` contains Toss login credentials. Toss is a financial super-app with payment capabilities. If these credentials are compromised, the attacker has access to the user's full financial account. Restrict `.env` permissions with: `icacls .env /inheritance:r /grant:r "%USERNAME%:F"`

**New machine setup**: clone repo → copy `.env`, `data/`, `logs/` manually → run `pip install -r requirements.txt` → run `python run.py --login`.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Crawling | Python 3.11+ + Playwright |
| Storage | SQLite |
| Dashboard | Streamlit (localhost only) |
| Scheduling | n8n (Docker) + host webhook server |
| Version control | Git + GitHub (private) |

---

## Future Extensions

- Add Naver Pay, Kakao Pay crawlers (plugin pattern already in place)
- Push notifications on crawl completion or failure (n8n → KakaoTalk/Slack)
- Budget targets per category with overspend alerts
- ML-based categorization to supplement/replace YAML rules
