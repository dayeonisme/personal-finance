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
