# Personal Finance Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first personal finance tracker that auto-crawls Toss daily, categorizes transactions, stores them in SQLite, and displays them via a Streamlit dashboard.

**Architecture:** Playwright crawls Toss web (session persistence for OTP-free daily runs), a categorizer applies YAML rules, a SQLite DB stores all data, and Streamlit renders 4 dashboard pages. n8n (Docker) calls a host-side webhook server daily to trigger the crawl.

**Tech Stack:** Python 3.11+, Playwright, SQLite (stdlib), Streamlit, PyYAML, python-dotenv, pytest, n8n (Docker)

---

## File Map

| File | Responsibility |
|------|---------------|
| `models.py` | `Transaction` and `CategorizedTransaction` dataclasses — shared data contract |
| `db/database.py` | SQLite schema init, insert/query transactions, crawl_log two-phase write |
| `parser/categorizer.py` | Load `config/categories.yaml`, apply rules, return `CategorizedTransaction` list |
| `crawler/base.py` | `BaseCrawler` abstract context manager |
| `crawler/toss.py` | Playwright-based Toss crawler with session persistence |
| `run.py` | CLI entrypoint (`--login`, `--days`, `--dry-run`), exit codes 0/1/2 |
| `webhook_server.py` | Tiny HTTP server bound to `127.0.0.1:9000`, runs `run.py` as subprocess |
| `dashboard/app.py` | Streamlit multi-page app (홈, 거래내역, 차트, 설정) |
| `config/categories.yaml` | Default categorization rules |
| `docker-compose.yml` | n8n service bound to `127.0.0.1:5678` |
| `requirements.txt` | All Python dependencies pinned |
| `.gitignore` | Exclude `data/`, `logs/`, `.env`, `n8n_data/` |
| `.env.example` | Template for `.env` (no real credentials) |
| `tests/test_models.py` | Unit tests for dataclasses |
| `tests/test_database.py` | DB layer tests using a temp file |
| `tests/test_categorizer.py` | Categorizer unit tests |
| `tests/test_crawler_base.py` | BaseCrawler context manager tests |
| `tests/test_run.py` | run.py exit code tests with mocked crawler+db |
| `tests/test_webhook_server.py` | Webhook HTTP endpoint tests |

---

## Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `config/categories.yaml`
- Create: `docker-compose.yml`
- Create: `data/.gitkeep`
- Create: `logs/.gitkeep`

- [ ] **Step 1: Create `requirements.txt`**

```
playwright==1.43.0
streamlit==1.33.0
pyyaml==6.0.1
python-dotenv==1.0.1
pytest==8.1.1
pytest-asyncio==0.23.6
```

- [ ] **Step 2: Create `.gitignore`**

```
data/
logs/
.env
n8n_data/
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 3: Create `.env.example`**

```
TOSS_PHONE=010-0000-0000
TOSS_PASSWORD=your_password_here
```

- [ ] **Step 4: Create `config/categories.yaml`**

```yaml
rules:
  - match: ["스타벅스", "카페베네", "투썸", "이디야", "커피"]
    category: 식비
  - match: ["맥도날드", "버거킹", "롯데리아", "배달의민족", "쿠팡이츠", "요기요"]
    category: 식비
  - match: ["쿠팡", "마켓컬리", "11번가", "지마켓", "옥션"]
    category: 쇼핑
  - match: ["버스", "지하철", "티머니", "택시", "카카오택시"]
    category: 교통
  - match: ["CGV", "롯데시네마", "메가박스", "넷플릭스", "유튜브"]
    category: 문화/여가
  - match: ["병원", "약국", "의원", "클리닉"]
    category: 의료
  - match: ["관리비", "전기", "가스", "수도", "인터넷", "통신"]
    category: 주거/공과금
  - match: ["급여", "월급", "이자수입"]
    category: 수입
default_category: "미분류"
```

- [ ] **Step 5: Create `docker-compose.yml`**

```yaml
services:
  n8n:
    image: n8nio/n8n
    ports:
      - "127.0.0.1:5678:5678"
    volumes:
      - ./n8n_data:/home/node/.n8n
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=changeme
```

- [ ] **Step 6: Create placeholder directories**

```bash
mkdir -p data logs tests
touch data/.gitkeep logs/.gitkeep tests/__init__.py
```

- [ ] **Step 7: Install dependencies**

```bash
pip install -r requirements.txt
playwright install chromium
```

- [ ] **Step 8: Commit**

```bash
git init
git add requirements.txt .gitignore .env.example config/ docker-compose.yml data/.gitkeep logs/.gitkeep tests/__init__.py
git commit -m "chore: project scaffold"
```

---

## Task 2: Data Models

**Files:**
- Create: `models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_models.py
from datetime import date
from models import Transaction, CategorizedTransaction

def test_transaction_fields():
    t = Transaction(
        date=date(2026, 3, 1),
        amount=-5000,
        description="스타벅스",
        source="kb_card",
        raw_source="toss",
    )
    assert t.date == date(2026, 3, 1)
    assert t.amount == -5000
    assert t.description == "스타벅스"
    assert t.source == "kb_card"
    assert t.raw_source == "toss"

def test_categorized_transaction_default_category():
    t = CategorizedTransaction(
        date=date(2026, 3, 1),
        amount=-5000,
        description="알수없음",
        source="kb_card",
        raw_source="toss",
    )
    assert t.category == "미분류"

def test_categorized_transaction_explicit_category():
    t = CategorizedTransaction(
        date=date(2026, 3, 1),
        amount=-5000,
        description="스타벅스",
        source="kb_card",
        raw_source="toss",
        category="식비",
    )
    assert t.category == "식비"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_models.py -v
```
Expected: `ModuleNotFoundError: No module named 'models'`

- [ ] **Step 3: Create `models.py`**

```python
from dataclasses import dataclass, field
from datetime import date


@dataclass
class Transaction:
    date: date
    amount: int          # negative = expense, positive = income (KRW)
    description: str     # merchant name or memo from source app
    source: str          # sub-account: 'kb_card', 'woori_bank', 'tmoneys', etc.
    raw_source: str      # aggregator: 'toss', 'naver_pay', 'manual', 'csv'


@dataclass
class CategorizedTransaction(Transaction):
    category: str = "미분류"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add models.py tests/test_models.py
git commit -m "feat: add Transaction and CategorizedTransaction data models"
```

---

## Task 3: Database Layer

**Files:**
- Create: `db/__init__.py`
- Create: `db/database.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_database.py
import tempfile
import os
from datetime import date, datetime
import pytest
from db.database import Database
from models import CategorizedTransaction


@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    d = Database(path)
    yield d
    os.unlink(path)


def make_tx(**kwargs):
    defaults = dict(
        date=date(2026, 3, 1),
        amount=-5000,
        description="스타벅스",
        source="kb_card",
        raw_source="toss",
        category="식비",
    )
    defaults.update(kwargs)
    return CategorizedTransaction(**defaults)


def test_insert_and_query(db):
    tx = make_tx()
    inserted = db.insert_transactions([tx])
    assert inserted == 1
    rows = db.get_transactions()
    assert len(rows) == 1
    assert rows[0]["description"] == "스타벅스"


def test_deduplication(db):
    tx = make_tx()
    first = db.insert_transactions([tx])
    second = db.insert_transactions([tx])
    assert first == 1
    assert second == 0  # duplicate — not inserted


def test_is_edited_preserves_category(db):
    tx = make_tx(category="식비")
    db.insert_transactions([tx])
    db.update_category(date=tx.date, amount=tx.amount, description=tx.description,
                       source=tx.source, category="쇼핑")
    rows = db.get_transactions()
    assert rows[0]["category"] == "쇼핑"
    assert rows[0]["is_edited"] == 1
    # re-inserting same tx should NOT overwrite the edited category
    db.insert_transactions([tx])
    rows = db.get_transactions()
    assert rows[0]["category"] == "쇼핑"


def test_crawl_log_two_phase(db):
    log_id = db.start_crawl_log()
    db.finish_crawl_log(log_id, status="success", rows_added=5)
    log = db.get_latest_crawl_log()
    assert log["status"] == "success"
    assert log["rows_added"] == 5
    assert log["finished_at"] is not None


def test_stale_running_treated_as_failed(db):
    log_id = db.start_crawl_log()
    # simulate a stale running log by backdating started_at
    db._conn.execute(
        "UPDATE crawl_log SET started_at = datetime('now', '-31 minutes') WHERE id = ?",
        (log_id,)
    )
    db._conn.commit()
    log = db.get_latest_crawl_log()
    assert log["status"] == "failed"


def test_get_transactions_filter_by_month(db):
    db.insert_transactions([make_tx(date=date(2026, 3, 1))])
    db.insert_transactions([make_tx(date=date(2026, 2, 1), description="편의점")])
    march = db.get_transactions(year=2026, month=3)
    assert len(march) == 1
    assert march[0]["description"] == "스타벅스"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_database.py -v
```
Expected: `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 3: Create `db/__init__.py`** (empty file)

- [ ] **Step 4: Create `db/database.py`**

```python
import sqlite3
from datetime import date, datetime
from pathlib import Path
from models import CategorizedTransaction

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        DATE NOT NULL,
    amount      INTEGER NOT NULL,
    description TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT '미분류',
    source      TEXT NOT NULL,
    raw_source  TEXT NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_edited   BOOLEAN DEFAULT 0,
    UNIQUE(date, amount, description, source)
);

CREATE TABLE IF NOT EXISTS crawl_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  DATETIME NOT NULL,
    finished_at DATETIME,
    status      TEXT NOT NULL,
    rows_added  INTEGER DEFAULT 0,
    error_msg   TEXT
);
"""


class Database:
    def __init__(self, path: str = "data/finance.db"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def insert_transactions(self, transactions: list[CategorizedTransaction]) -> int:
        inserted = 0
        for tx in transactions:
            existing = self._conn.execute(
                "SELECT is_edited FROM transactions WHERE date=? AND amount=? AND description=? AND source=?",
                (tx.date.isoformat(), tx.amount, tx.description, tx.source),
            ).fetchone()
            if existing:
                if existing["is_edited"]:
                    # User has manually overridden the category — preserve it, skip re-insert
                    continue
                else:
                    # Pure deduplication — row already exists, nothing to do
                    continue
            self._conn.execute(
                """INSERT INTO transactions
                   (date, amount, description, category, source, raw_source)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (tx.date.isoformat(), tx.amount, tx.description,
                 tx.category, tx.source, tx.raw_source),
            )
            inserted += 1
        self._conn.commit()
        return inserted

    def update_category(self, *, date: date, amount: int, description: str,
                        source: str, category: str) -> None:
        self._conn.execute(
            """UPDATE transactions SET category=?, is_edited=1
               WHERE date=? AND amount=? AND description=? AND source=?""",
            (category, date.isoformat(), amount, description, source),
        )
        self._conn.commit()

    def get_transactions(self, year: int = None, month: int = None) -> list[dict]:
        query = "SELECT * FROM transactions WHERE 1=1"
        params: list = []
        if year and month:
            query += " AND strftime('%Y', date)=? AND strftime('%m', date)=?"
            params.extend([str(year), f"{month:02d}"])
        elif year:
            query += " AND strftime('%Y', date)=?"
            params.append(str(year))
        query += " ORDER BY date DESC"
        rows = self._conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def start_crawl_log(self) -> int:
        cur = self._conn.execute(
            "INSERT INTO crawl_log (started_at, status) VALUES (datetime('now'), 'running')"
        )
        self._conn.commit()
        return cur.lastrowid

    def finish_crawl_log(self, log_id: int, *, status: str,
                         rows_added: int = 0, error_msg: str = None) -> None:
        self._conn.execute(
            """UPDATE crawl_log SET status=?, finished_at=datetime('now'),
               rows_added=?, error_msg=? WHERE id=?""",
            (status, rows_added, error_msg, log_id),
        )
        self._conn.commit()

    def get_latest_crawl_log(self) -> dict | None:
        row = self._conn.execute(
            """SELECT *,
               CASE
                 WHEN status='running' AND
                      (julianday('now') - julianday(started_at)) * 24 * 60 > 30
                 THEN 'failed'
                 ELSE status
               END AS status
               FROM crawl_log ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        return dict(row) if row else None
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_database.py -v
```
Expected: 6 PASSED

- [ ] **Step 6: Commit**

```bash
git add db/ tests/test_database.py
git commit -m "feat: add SQLite database layer with deduplication and crawl logging"
```

---

## Task 4: Categorizer

**Files:**
- Create: `parser/__init__.py`
- Create: `parser/categorizer.py`
- Create: `tests/test_categorizer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_categorizer.py
from datetime import date
import pytest
from models import Transaction, CategorizedTransaction
from parser.categorizer import categorize, load_rules


def make_tx(description: str) -> Transaction:
    return Transaction(
        date=date(2026, 3, 1),
        amount=-5000,
        description=description,
        source="kb_card",
        raw_source="toss",
    )


def test_known_keyword_matches(tmp_path):
    rules_yaml = tmp_path / "categories.yaml"
    rules_yaml.write_text(
        "rules:\n  - match: ['스타벅스']\n    category: 식비\ndefault_category: 미분류\n"
    )
    rules = load_rules(str(rules_yaml))
    result = categorize([make_tx("스타벅스 강남점")], rules)
    assert result[0].category == "식비"


def test_default_category_when_no_match(tmp_path):
    rules_yaml = tmp_path / "categories.yaml"
    rules_yaml.write_text("rules: []\ndefault_category: 미분류\n")
    rules = load_rules(str(rules_yaml))
    result = categorize([make_tx("알수없는가게")], rules)
    assert result[0].category == "미분류"


def test_first_match_wins(tmp_path):
    rules_yaml = tmp_path / "categories.yaml"
    rules_yaml.write_text(
        "rules:\n"
        "  - match: ['카페']\n    category: 식비\n"
        "  - match: ['카페']\n    category: 쇼핑\n"
        "default_category: 미분류\n"
    )
    rules = load_rules(str(rules_yaml))
    result = categorize([make_tx("카페베네")], rules)
    assert result[0].category == "식비"


def test_returns_categorized_transaction_type(tmp_path):
    rules_yaml = tmp_path / "categories.yaml"
    rules_yaml.write_text("rules: []\ndefault_category: 미분류\n")
    rules = load_rules(str(rules_yaml))
    result = categorize([make_tx("테스트")], rules)
    assert isinstance(result[0], CategorizedTransaction)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_categorizer.py -v
```
Expected: `ModuleNotFoundError: No module named 'parser'`

- [ ] **Step 3: Create `parser/__init__.py`** (empty)

- [ ] **Step 4: Create `parser/categorizer.py`**

```python
import yaml
from models import Transaction, CategorizedTransaction


def load_rules(path: str = "config/categories.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def categorize(
    transactions: list[Transaction],
    rules: dict = None,
    rules_path: str = "config/categories.yaml",
) -> list[CategorizedTransaction]:
    if rules is None:
        rules = load_rules(rules_path)

    default = rules.get("default_category", "미분류")
    rule_list = rules.get("rules", [])

    result = []
    for tx in transactions:
        category = default
        for rule in rule_list:
            if any(kw in tx.description for kw in rule["match"]):
                category = rule["category"]
                break
        result.append(CategorizedTransaction(
            date=tx.date,
            amount=tx.amount,
            description=tx.description,
            source=tx.source,
            raw_source=tx.raw_source,
            category=category,
        ))
    return result
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_categorizer.py -v
```
Expected: 4 PASSED

- [ ] **Step 6: Commit**

```bash
git add parser/ tests/test_categorizer.py
git commit -m "feat: add YAML-based transaction categorizer"
```

---

## Task 5: Crawler Base Class

**Files:**
- Create: `crawler/__init__.py`
- Create: `crawler/base.py`
- Create: `tests/test_crawler_base.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_crawler_base.py
from datetime import date
import pytest
from models import Transaction
from crawler.base import BaseCrawler


class MockCrawler(BaseCrawler):
    def __init__(self):
        self.logged_in = False
        self.logged_out = False
        self.logout_raises = False

    def login(self):
        self.logged_in = True

    def fetch_transactions(self, start_date, end_date):
        return [Transaction(
            date=date(2026, 3, 1), amount=-1000,
            description="테스트", source="test", raw_source="test"
        )]

    def logout(self):
        if self.logout_raises:
            raise RuntimeError("browser crashed")
        self.logged_out = True


def test_context_manager_calls_login_and_logout():
    crawler = MockCrawler()
    with crawler as c:
        c.login()
    assert crawler.logged_out is True


def test_logout_called_even_on_exception():
    crawler = MockCrawler()
    with pytest.raises(ValueError):
        with crawler:
            raise ValueError("something failed")
    assert crawler.logged_out is True


def test_logout_exception_does_not_mask_original():
    crawler = MockCrawler()
    crawler.logout_raises = True
    with pytest.raises(ValueError, match="original error"):
        with crawler:
            raise ValueError("original error")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_crawler_base.py -v
```
Expected: `ModuleNotFoundError: No module named 'crawler'`

- [ ] **Step 3: Create `crawler/__init__.py`**

```python
from crawler.base import AuthenticationError

__all__ = ["AuthenticationError"]
```

- [ ] **Step 4: Create `crawler/base.py`**

```python
from abc import ABC, abstractmethod
from datetime import date
from models import Transaction


class AuthenticationError(Exception):
    """Raised when crawler session is expired or login fails."""


class BaseCrawler(ABC):
    def __enter__(self) -> "BaseCrawler":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        try:
            self.logout()
        except Exception:
            pass  # never mask the original exception
        return False  # re-raise any exception from the with block

    @abstractmethod
    def login(self) -> None: ...

    @abstractmethod
    def fetch_transactions(self, start_date: date, end_date: date) -> list[Transaction]: ...

    @abstractmethod
    def logout(self) -> None: ...
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_crawler_base.py -v
```
Expected: 3 PASSED

- [ ] **Step 6: Commit**

```bash
git add crawler/ tests/test_crawler_base.py
git commit -m "feat: add BaseCrawler abstract context manager"
```

---

## Task 6: Toss Crawler

**Files:**
- Create: `crawler/toss.py`

> No automated tests for the live crawler — it requires a real Toss account and browser.
> Manual verification steps are provided below.

- [ ] **Step 1: Create `crawler/toss.py`**

```python
import json
import logging
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright, Page
from dotenv import load_dotenv
import os

from crawler.base import AuthenticationError, BaseCrawler
from models import Transaction

load_dotenv()
logger = logging.getLogger(__name__)

SESSION_PATH = Path("data/toss_session.json")
TOSS_URL = "https://toss.im"


class TossCrawler(BaseCrawler):
    def __init__(self, headless: bool = True):
        self._headless = headless
        self._playwright = None
        self._browser = None
        self._page: Page | None = None

    def login(self) -> None:
        self._playwright = sync_playwright().start()
        launch_kwargs = {"headless": self._headless}
        self._browser = self._playwright.chromium.launch(**launch_kwargs)
        if SESSION_PATH.exists():
            context = self._browser.new_context(storage_state=str(SESSION_PATH))
        else:
            context = self._browser.new_context()

        self._page = context.new_page()
        self._page.goto(f"{TOSS_URL}/my-account")

        # Check if already logged in
        if self._page.url.startswith(f"{TOSS_URL}/my-account"):
            logger.info("Session valid — skipping login")
            return

        # Perform login
        phone = os.environ["TOSS_PHONE"]
        password = os.environ["TOSS_PASSWORD"]
        self._page.fill('[placeholder*="전화번호"]', phone)
        self._page.click('button:has-text("다음")')
        self._page.fill('[placeholder*="비밀번호"]', password)
        self._page.click('button:has-text("로그인")')

        try:
            # Wait for OTP completion (manual step when headless=False)
            self._page.wait_for_url(f"{TOSS_URL}/my-account**", timeout=120_000)
        except Exception as e:
            raise AuthenticationError(
                "Toss login timed out — session may be expired. Run: python run.py --login"
            ) from e

        # Save session
        SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._page.context.storage_state(path=str(SESSION_PATH))
        logger.info("Session saved to %s", SESSION_PATH)

    def fetch_transactions(self, start_date: date, end_date: date) -> list[Transaction]:
        if self._page is None:
            raise RuntimeError("Call login() first or use as context manager")

        transactions: list[Transaction] = []

        # Navigate to transaction history
        self._page.goto(f"{TOSS_URL}/my-account/transaction-list")
        self._page.wait_for_load_state("networkidle")

        # Toss renders transactions as JSON in the page or via API calls.
        # Intercept the internal API response.
        # NOTE: Toss UI changes frequently — this selector may need updating.
        items = self._page.evaluate("""() => {
            const elements = document.querySelectorAll('[data-testid="transaction-item"]');
            return Array.from(elements).map(el => ({
                date: el.getAttribute('data-date'),
                amount: parseInt(el.getAttribute('data-amount')),
                description: el.querySelector('.description')?.textContent?.trim(),
                source: el.getAttribute('data-account-id'),
            }));
        }""")

        for item in items:
            try:
                tx_date = date.fromisoformat(item["date"][:10])
                if not (start_date <= tx_date <= end_date):
                    continue
                transactions.append(Transaction(
                    date=tx_date,
                    amount=item["amount"],
                    description=item["description"] or "알수없음",
                    source=item.get("source") or "toss_unknown",
                    raw_source="toss",
                ))
            except Exception as e:
                logger.warning("Failed to parse transaction item: %s — %s", item, e)

        logger.info("Fetched %d transactions from Toss", len(transactions))
        return transactions

    def logout(self) -> None:
        if self._page:
            try:
                self._page.context.close()
            finally:
                self._page = None
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
```

- [ ] **Step 2: Create `.env` from template (manual step)**

```bash
cp .env.example .env
# Edit .env and fill in your real Toss phone and password
```

- [ ] **Step 3: Manual smoke test — first login**

```bash
python -c "
from crawler.toss import TossCrawler
from datetime import date, timedelta
c = TossCrawler(headless=False)
c.login()
txs = c.fetch_transactions(date.today() - timedelta(days=7), date.today())
print(f'Fetched {len(txs)} transactions')
for tx in txs[:3]:
    print(tx)
c.logout()
"
```
Expected: Browser opens, user completes OTP, session saved, transactions printed.

- [ ] **Step 4: Manual smoke test — session reuse**

```bash
python -c "
from crawler.toss import TossCrawler
from datetime import date, timedelta
with TossCrawler(headless=True) as c:
    c.login()
    txs = c.fetch_transactions(date.today() - timedelta(days=3), date.today())
    print(f'Fetched {len(txs)} transactions (no OTP required)')
"
```
Expected: No browser window, transactions printed.

- [ ] **Step 5: Commit**

```bash
git add crawler/toss.py
git commit -m "feat: add Toss Playwright crawler with session persistence"
```

---

## Task 7: run.py Entrypoint

**Files:**
- Create: `run.py`
- Create: `tests/test_run.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_run.py
import sys
from datetime import date
from unittest.mock import MagicMock, patch
import pytest

import run  # import at module level — logging setup is inside main(), no side effects
from crawler.base import AuthenticationError
from models import CategorizedTransaction


def make_tx():
    return CategorizedTransaction(
        date=date(2026, 3, 1), amount=-5000,
        description="스타벅스", source="kb_card",
        raw_source="toss", category="식비",
    )


def _mock_crawler(fetch_return=None, raise_on_login=None):
    mock = MagicMock()
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    if raise_on_login:
        mock.login.side_effect = raise_on_login
    else:
        mock.fetch_transactions.return_value = fetch_return or [make_tx()]
    return mock


def test_run_success_exits_0(tmp_path):
    mock_db = MagicMock()
    mock_db.start_crawl_log.return_value = 1
    mock_db.insert_transactions.return_value = 3

    with patch("run.Database", return_value=mock_db), \
         patch("run.TossCrawler", return_value=_mock_crawler()), \
         patch("run.categorize", return_value=[make_tx()]), \
         patch("run._setup_logging"), \
         patch("sys.exit") as mock_exit:
        run.main(days=7, dry_run=False, login=False)
        mock_exit.assert_called_with(0)


def test_auth_failure_exits_2(tmp_path):
    mock_db = MagicMock()
    mock_db.start_crawl_log.return_value = 1

    with patch("run.Database", return_value=mock_db), \
         patch("run.TossCrawler", return_value=_mock_crawler(raise_on_login=AuthenticationError("expired"))), \
         patch("run._setup_logging"), \
         patch("sys.exit") as mock_exit:
        run.main(days=7, dry_run=False, login=False)
        mock_exit.assert_called_with(2)
        mock_db.finish_crawl_log.assert_called_once()
        call_kwargs = mock_db.finish_crawl_log.call_args.kwargs
        assert call_kwargs["status"] == "failed"


def test_dry_run_does_not_write_to_db(tmp_path):
    mock_db = MagicMock()

    with patch("run.Database", return_value=mock_db), \
         patch("run.TossCrawler", return_value=_mock_crawler()), \
         patch("run.categorize", return_value=[make_tx()]), \
         patch("run._setup_logging"), \
         patch("sys.exit"):
        run.main(days=7, dry_run=True, login=False)
        mock_db.insert_transactions.assert_not_called()
        mock_db.start_crawl_log.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_run.py -v
```
Expected: `ModuleNotFoundError: No module named 'run'`

- [ ] **Step 3: Create `run.py`**

```python
import argparse
import logging
import sys
from datetime import date, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

from crawler.base import AuthenticationError
from crawler.toss import TossCrawler
from db.database import Database
from parser.categorizer import categorize

load_dotenv()

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    Path("logs").mkdir(exist_ok=True)
    handler = RotatingFileHandler("logs/crawl.log", maxBytes=10 * 1024 * 1024, backupCount=3)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[handler, logging.StreamHandler()],
    )


def main(days: int = 7, dry_run: bool = False, login: bool = False) -> None:
    _setup_logging()
    db = Database()
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    if dry_run:
        logger.info("[dry-run] Fetching %d days without writing to DB", days)
        with TossCrawler(headless=not login) as crawler:
            crawler.login()
            transactions = crawler.fetch_transactions(start_date, end_date)
        categorized = categorize(transactions)
        for tx in categorized:
            print(tx)
        sys.exit(0)

    log_id = db.start_crawl_log()
    rows_added = 0
    try:
        with TossCrawler(headless=not login) as crawler:
            crawler.login()
            transactions = crawler.fetch_transactions(start_date, end_date)
        categorized = categorize(transactions)
        rows_added = db.insert_transactions(categorized)
        logger.info("Inserted %d new transactions", rows_added)
        db.finish_crawl_log(log_id, status="success", rows_added=rows_added)
        sys.exit(0)
    except AuthenticationError as e:
        logger.error("Authentication failed: %s", e)
        db.finish_crawl_log(log_id, status="failed", error_msg=str(e))
        sys.exit(2)
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        db.finish_crawl_log(log_id, status="failed", error_msg=str(e))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Personal finance crawler")
    parser.add_argument("--login", action="store_true",
                        help="Open visible browser for manual OTP")
    parser.add_argument("--days", type=int, default=7,
                        help="Fetch last N days (default: 7)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and parse without writing to DB or crawl_log")
    args = parser.parse_args()
    main(days=args.days, dry_run=args.dry_run, login=args.login)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_run.py -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add run.py tests/test_run.py
git commit -m "feat: add run.py CLI entrypoint with exit codes and dry-run support"
```

---

## Task 8: Webhook Server

**Files:**
- Create: `webhook_server.py`
- Create: `tests/test_webhook_server.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_webhook_server.py
import subprocess
import threading
from unittest.mock import patch, MagicMock
import urllib.request
import time
import pytest


def test_post_to_run_endpoint_returns_200():
    from webhook_server import create_app
    app = create_app(dry_run=True)

    with patch("webhook_server.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        # Test that the handler works
        result = app.handle_run_request()
        assert result["exit_code"] == 0


def test_server_binds_to_localhost():
    from webhook_server import HOST
    assert HOST == "127.0.0.1"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_webhook_server.py -v
```
Expected: `ModuleNotFoundError: No module named 'webhook_server'`

- [ ] **Step 3: Create `webhook_server.py`**

```python
import json
import logging
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

logger = logging.getLogger(__name__)

HOST = "127.0.0.1"
PORT = 9000


class _App:
    def handle_run_request(self) -> dict:
        result = subprocess.run(
            [sys.executable, "run.py"],
            capture_output=True,
            text=True,
        )
        logger.info("run.py exited with code %d", result.returncode)
        if result.stderr:
            logger.error(result.stderr)
        return {"exit_code": result.returncode, "stdout": result.stdout}


def create_app(dry_run: bool = False) -> _App:
    return _App()


def _make_handler(app: _App):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path == "/run":
                result = app.handle_run_request()
                body = json.dumps(result).encode()
                status = 200 if result["exit_code"] == 0 else 500
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            logger.info(format, *args)

    return Handler


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    app = create_app()
    server = HTTPServer((HOST, PORT), _make_handler(app))
    logger.info("Webhook server running at http://%s:%d", HOST, PORT)
    server.serve_forever()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_webhook_server.py -v
```
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add webhook_server.py tests/test_webhook_server.py
git commit -m "feat: add webhook server for n8n integration, bound to 127.0.0.1:9000"
```

---

## Task 9: Dashboard

**Files:**
- Create: `dashboard/__init__.py`
- Create: `dashboard/app.py`

> Streamlit UI is not unit-tested (requires a running Streamlit server). Verify manually.

- [ ] **Step 1: Create `dashboard/__init__.py`** (empty)

- [ ] **Step 2: Create `dashboard/app.py`**

```python
import subprocess
import sys
from datetime import date

import pandas as pd
import streamlit as st

from db.database import Database
from models import CategorizedTransaction
from parser.categorizer import load_rules

db = Database()

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

    col1, col2, col3 = st.columns(3)
    col1.metric("수입", f"{inc_this:,}원", f"{inc_this - inc_last:+,}원 vs 지난달")
    col2.metric("지출", f"{abs(exp_this):,}원", f"{abs(exp_this) - abs(exp_last):+,}원 vs 지난달")
    col3.metric("순수익", f"{inc_this + exp_this:,}원")

    log = db.get_latest_crawl_log()
    if log:
        status_emoji = "✅" if log["status"] == "success" else "❌"
        st.caption(f"{status_emoji} 마지막 동기화: {log['started_at']} ({log['status']})")

    if st.button("🔄 지금 동기화"):
        import urllib.request
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
                matching = [r for r in rows if r["id"] == int(idx)]
                if matching:
                    r = matching[0]
                    db.update_category(
                        date=date.fromisoformat(r["date"]),
                        amount=r["amount"],
                        description=r["description"],
                        source=r["source"],
                        category=new_cat,
                    )
                    st.success("저장되었습니다.")
                    st.rerun()

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
        import io
        df = pd.read_csv(io.BytesIO(uploaded.read()))
        st.dataframe(df.head())
        st.info(f"{len(df)}개 행 감지됨. 아래 컬럼 매핑을 확인하세요.")
        # Basic column mapping
        col_map = {}
        for field in ["date", "amount", "description", "source"]:
            col_map[field] = st.selectbox(f"{field} 컬럼", df.columns.tolist(), key=field)
        if st.button("가져오기"):
            from parser.categorizer import categorize
            txs = []
            for _, row in df.iterrows():
                try:
                    from models import Transaction
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
            from models import CategorizedTransaction
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
```

- [ ] **Step 3: Manual verification — run the dashboard**

```bash
streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501
```
Open `http://127.0.0.1:8501` and verify:
- 홈 page shows monthly summary (may be empty on first run)
- 거래내역 page loads without errors
- 차트 page shows empty state message
- 설정 page shows category rules

- [ ] **Step 4: Commit**

```bash
git add dashboard/
git commit -m "feat: add Streamlit dashboard (홈, 거래내역, 차트, 설정)"
```

---

## Task 10: n8n Workflow Setup

> This is a manual configuration step inside the n8n UI.

- [ ] **Step 1: Start n8n**

```bash
docker-compose up -d
```

- [ ] **Step 2: Change the default n8n password**

Open `http://127.0.0.1:5678` → login with `admin / changeme` → go to Settings → Change Password → set a strong password.

> This step is not optional. The default password is publicly known.

- [ ] **Step 3: Start webhook server**

```bash
python webhook_server.py
```
Keep this running (or add it to Windows startup later).

- [ ] **Step 4: Create n8n workflow**

In n8n UI:
1. New workflow → Add node: **Schedule Trigger** → set to daily at 09:00
2. Add node: **HTTP Request**
   - Method: POST
   - URL: `http://host.docker.internal:9000/run`
3. Add node: **IF** — check `exit_code == 0`
4. (Optional) Add **notification node** on failure (email, Slack, etc.)
5. Save and activate the workflow

- [ ] **Step 5: Test the workflow manually**

Click "Execute Workflow" in n8n UI and verify:
- Webhook server log shows the request
- `run.py` executes
- DB gets new transactions (or 0 if already up to date)

- [ ] **Step 6: Commit n8n_data to gitignore verification**

```bash
git status
# n8n_data/ should NOT appear in git status
```

---

## Task 11: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md**

```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Run all tests
pytest -v

# Run a single test file
pytest tests/test_database.py -v

# First-time Toss login (opens browser, save session)
python run.py --login

# Daily sync (automated via n8n, or run manually)
python run.py --days 7

# Dry run (no DB writes)
python run.py --dry-run

# Start dashboard
streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501

# Start webhook server (for n8n integration)
python webhook_server.py

# Start n8n
docker-compose up -d
```

## Architecture

Data flows: Playwright (Toss) → `models.Transaction` list → `parser/categorizer.py` → `models.CategorizedTransaction` list → `db/database.py` (SQLite) → Streamlit dashboard.

`run.py` is the crawl entrypoint. It writes a two-phase `crawl_log` entry (INSERT on start, UPDATE on finish). Exit codes: 0=success, 1=unexpected error, 2=auth failure.

`webhook_server.py` is a tiny HTTP server at `127.0.0.1:9000` that n8n calls daily to trigger `run.py`. The Streamlit dashboard's "지금 동기화" button also POSTs to this endpoint.

All crawlers inherit `BaseCrawler` (context manager). To add a new source (Naver Pay etc.), create `crawler/naver_pay.py` implementing `login()`, `fetch_transactions()`, `logout()`.

## Security

- `data/`, `logs/`, `.env`, `n8n_data/` are gitignored — never commit them
- All local servers bound to `127.0.0.1` only (ports 8501, 9000, 5678)
- `.env` contains Toss credentials — restrict permissions: `icacls .env /inheritance:r /grant:r "%USERNAME%:F"`
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with commands and architecture"
```

---

## Final Verification

- [ ] Run full test suite: `pytest -v` — all tests pass
- [ ] Confirm gitignore: `git status` shows no `data/`, `logs/`, `.env`, `n8n_data/`
- [ ] Manual end-to-end: `python run.py --login` → open dashboard → verify transactions appear
- [ ] n8n daily workflow activated and tested
