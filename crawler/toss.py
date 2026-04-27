import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, Page, Response
from dotenv import load_dotenv
import os

from crawler.base import AuthenticationError, BaseCrawler
from models import Transaction

load_dotenv()
logger = logging.getLogger(__name__)

SESSION_PATH = Path(__file__).parent.parent / "data" / "toss_session.json"
TOSS_URL = "https://toss.im"

# Toss internal API patterns that carry transaction data
_TX_API_PATTERNS = [
    "/api/v1/bank-account/transaction",
    "/api/v2/bank-account/transaction",
    "/api/v1/card/transaction",
    "/api/v2/card/transaction",
    "/api/v1/my-data/transactions",
    "/api/v2/my-data/transactions",
    "/api/v3/my-data/transactions",
    "/api/v1/user/activity-history",
]


def _parse_api_response(body: dict) -> list[Transaction]:
    """Try to extract Transaction objects from a Toss API response body.

    Toss API shapes are not publicly documented and change over time.
    This function tries common field names; extend as needed.
    """
    transactions: list[Transaction] = []

    # Collect candidate lists from common envelope keys
    candidates: list[list] = []
    for key in ("transactions", "items", "data", "list", "histories", "activities"):
        val = body.get(key)
        if isinstance(val, list):
            candidates.append(val)
    # Also try the root if it's already a list
    if isinstance(body, list):
        candidates.append(body)

    for items in candidates:
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                tx = _item_to_transaction(item)
                if tx:
                    transactions.append(tx)
            except Exception as e:
                logger.debug("Could not parse item %s: %s", item, e)

    return transactions


def _item_to_transaction(item: dict) -> Optional[Transaction]:
    """Convert a single API item dict to a Transaction, or return None."""
    # ── date ──────────────────────────────────────────────────────────────
    raw_date = (
        item.get("transactionDate")
        or item.get("date")
        or item.get("createdAt")
        or item.get("approvedAt")
        or item.get("settledAt")
    )
    if not raw_date:
        return None
    tx_date = date.fromisoformat(str(raw_date)[:10])

    # ── amount ────────────────────────────────────────────────────────────
    # Some APIs split into debit/credit; others give a signed value.
    raw_amount = (
        item.get("amount")
        or item.get("transactionAmount")
        or item.get("value")
    )
    if raw_amount is None:
        return None
    amount = int(raw_amount)

    # Toss sometimes separates withdrawal/deposit
    if amount == 0:
        withdraw = item.get("withdrawalAmount") or item.get("debitAmount") or 0
        deposit  = item.get("depositAmount")    or item.get("creditAmount") or 0
        if withdraw:
            amount = -int(withdraw)
        elif deposit:
            amount = int(deposit)

    # ── description / place ───────────────────────────────────────────────
    description = str(
        item.get("description")
        or item.get("memo")
        or item.get("transactionDescription")
        or item.get("title")
        or "알수없음"
    ).strip()

    place = str(
        item.get("merchantName")
        or item.get("storeName")
        or item.get("place")
        or item.get("shopName")
        or ""
    ).strip()

    # ── source ────────────────────────────────────────────────────────────
    source = str(
        item.get("accountId")
        or item.get("cardId")
        or item.get("sourceId")
        or item.get("productName")
        or "toss_unknown"
    ).strip()

    return Transaction(
        date=tx_date,
        amount=amount,
        description=description,
        place=place,
        source=source,
        raw_source="toss",
    )


class TossCrawler(BaseCrawler):
    def __init__(self, headless: bool = True):
        self._headless = headless
        self._playwright = None
        self._browser = None
        self._context = None
        self._page: Optional[Page] = None
        self._captured: list[Transaction] = []

    def login(self) -> None:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._headless)

        session_exists = SESSION_PATH.exists()
        if session_exists:
            self._context = self._browser.new_context(storage_state=str(SESSION_PATH))
        else:
            self._context = self._browser.new_context()

        self._page = self._context.new_page()
        self._page.goto(f"{TOSS_URL}/my-account")

        # Check if already authenticated
        try:
            self._page.wait_for_url(f"{TOSS_URL}/my-account**", timeout=5_000)
            logger.info("Session valid — skipping login")
            return
        except Exception:
            pass  # session expired or never logged in

        # Session expired: discard stale session file and reset context
        if session_exists:
            logger.info("Saved session expired — discarding %s and re-authenticating", SESSION_PATH)
            SESSION_PATH.unlink(missing_ok=True)
            self._page.close()
            self._context.close()
            self._context = self._browser.new_context()
            self._page = self._context.new_page()

        # headless=True means we're in automated mode — OTP is not possible
        if self._headless:
            raise AuthenticationError(
                "Toss session expired and cannot re-authenticate in headless mode. "
                "Run: python run.py --login"
            )

        # Interactive login (headless=False)
        phone = os.environ["TOSS_PHONE"]
        password = os.environ["TOSS_PASSWORD"]
        self._page.goto(f"{TOSS_URL}/my-account")
        self._page.fill('[placeholder*="전화번호"]', phone)
        self._page.click('button:has-text("다음")')
        self._page.fill('[placeholder*="비밀번호"]', password)
        self._page.click('button:has-text("로그인")')

        try:
            # Wait for OTP completion (manual step)
            self._page.wait_for_url(f"{TOSS_URL}/my-account**", timeout=120_000)
        except Exception as e:
            raise AuthenticationError(
                "Toss login timed out. Complete OTP within 2 minutes."
            ) from e

        # Save new session
        SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._context.storage_state(path=str(SESSION_PATH))
        logger.info("New session saved to %s", SESSION_PATH)

    # Scroll pagination constants
    _MAX_SCROLL_ATTEMPTS = 40   # hard cap to prevent infinite loops
    _SCROLL_PAUSE_MS     = 2_000  # ms to wait after each scroll for API responses
    _NO_NEW_DATA_LIMIT   = 3    # stop if N consecutive scrolls yield no new transactions

    def fetch_transactions(self, start_date: date, end_date: date) -> list[Transaction]:
        if self._page is None:
            raise RuntimeError("Call login() first or use as context manager")

        self._captured = []

        def _on_response(response: Response) -> None:
            url = response.url
            if not any(pat in url for pat in _TX_API_PATTERNS):
                return
            if response.status != 200:
                return
            try:
                body = response.json()
                txs = _parse_api_response(body)
                if txs:
                    logger.info("Captured %d items from %s", len(txs), url)
                    self._captured.extend(txs)
            except Exception as e:
                logger.debug("Response parse error for %s: %s", url, e)

        self._page.on("response", _on_response)

        # Navigate to the transaction list page to trigger initial API calls
        self._page.goto(f"{TOSS_URL}/my-account/transaction-list")
        self._page.wait_for_load_state("networkidle")

        # Scroll down repeatedly to trigger lazy-load API calls
        no_new_count = 0
        prev_count = 0

        for attempt in range(self._MAX_SCROLL_ATTEMPTS):
            # Scroll to bottom of page and any tall inner container
            self._page.evaluate(
                "() => {"
                "  window.scrollTo(0, document.body.scrollHeight);"
                "  const el = document.querySelector('[class*=\"transaction\"], [class*=\"list\"], main');"
                "  if (el) el.scrollTop = el.scrollHeight;"
                "}"
            )
            self._page.wait_for_timeout(self._SCROLL_PAUSE_MS)

            # Stop if oldest captured transaction is before start_date (checked after scroll)
            if self._captured:
                oldest = min(tx.date for tx in self._captured)
                if oldest < start_date:
                    logger.info(
                        "Oldest captured date %s is before start_date %s — stopping scroll",
                        oldest, start_date,
                    )
                    break

            current_count = len(self._captured)
            if current_count == prev_count:
                no_new_count += 1
                logger.debug("Scroll %d: no new transactions (%d/%d)",
                             attempt + 1, no_new_count, self._NO_NEW_DATA_LIMIT)
                if no_new_count >= self._NO_NEW_DATA_LIMIT:
                    logger.info("No new data after %d scrolls — stopping", no_new_count)
                    break
            else:
                no_new_count = 0
            prev_count = current_count

        self._page.remove_listener("response", _on_response)

        if not self._captured:
            logger.warning(
                "No transactions captured. Toss API endpoints may have changed. "
                "Run with --login (headless=False) and check logs/crawl.log for "
                "candidate URLs, then update _TX_API_PATTERNS in crawler/toss.py."
            )

        # Filter to requested date range
        transactions = [
            tx for tx in self._captured
            if start_date <= tx.date <= end_date
        ]
        logger.info(
            "Fetched %d transactions from Toss (%d total captured, date-filtered to %s–%s)",
            len(transactions), len(self._captured), start_date, end_date,
        )
        return transactions

    def logout(self) -> None:
        if self._context:
            try:
                self._context.close()
            finally:
                self._context = None
                self._page = None
        if self._browser:
            try:
                self._browser.close()
            finally:
                self._browser = None
        if self._playwright:
            try:
                self._playwright.stop()
            finally:
                self._playwright = None
