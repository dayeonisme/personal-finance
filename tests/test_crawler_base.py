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


def test_context_manager_calls_logout_on_exit():
    crawler = MockCrawler()
    with crawler as c:
        c.login()
    assert crawler.logged_in is True
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
