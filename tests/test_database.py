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
    d.close()
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
