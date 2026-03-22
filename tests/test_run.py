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


def test_unexpected_error_exits_1(tmp_path):
    mock_db = MagicMock()
    mock_db.start_crawl_log.return_value = 1

    with patch("run.Database", return_value=mock_db), \
         patch("run.TossCrawler", return_value=_mock_crawler(raise_on_login=RuntimeError("network failure"))), \
         patch("run._setup_logging"), \
         patch("sys.exit") as mock_exit:
        run.main(days=7, dry_run=False, login=False)
        mock_exit.assert_called_with(1)
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
