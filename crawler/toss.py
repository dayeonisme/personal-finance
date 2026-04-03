import json
import logging
from datetime import date
from pathlib import Path

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


def _item_to_transaction(item: dict) -> Transaction | None:
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
        self._page: Page | None = None
        self._captured: list[Transaction] = []

    def login(self) -> None:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._headless)
        if SESSION_PATH.exists():
            self._context = self._browser.new_context(storage_state=str(SESSION_PATH))
        else:
            self._context = self._browser.new_context()

        self._page = self._context.new_page()
        self._page.goto(f"{TOSS_URL}/my-account")

        # Wait for any SPA redirect to settle, then check if already authenticated
        try:
            self._page.wait_for_url(f"{TOSS_URL}/my-account**", timeout=5_000)
            logger.info("Session valid — skipping login")
            return
        except Exception:
            pass  # session expired or never logged in — proceed with login flow

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
        self._context.storage_state(path=str(SESSION_PATH))
        logger.info("Session saved to %s", SESSION_PATH)

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

        # Navigate to the transaction list page to trigger the API calls
        self._page.goto(f"{TOSS_URL}/my-account/transaction-list")
        self._page.wait_for_load_state("networkidle")

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
