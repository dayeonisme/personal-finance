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
    load_dotenv()
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
        return

    log_id = db.start_crawl_log()
    status = "failed"
    error_msg = None
    rows_added = 0
    exit_code = 1
    try:
        with TossCrawler(headless=not login) as crawler:
            crawler.login()
            transactions = crawler.fetch_transactions(start_date, end_date)
        categorized = categorize(transactions)
        rows_added = db.insert_transactions(categorized)
        logger.info("Inserted %d new transactions", rows_added)
        status = "success"
        exit_code = 0
    except AuthenticationError as e:
        logger.error("Authentication failed: %s", e)
        error_msg = str(e)
        exit_code = 2
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        error_msg = str(e)
        exit_code = 1
    finally:
        db.finish_crawl_log(log_id, status=status, rows_added=rows_added, error_msg=error_msg)
    sys.exit(exit_code)


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
