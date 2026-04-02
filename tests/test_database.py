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


def test_get_transactions_month_without_year_raises(db):
    with pytest.raises(ValueError, match="year is required"):
        db.get_transactions(month=3)


def test_update_category_raises_if_not_found(db):
    with pytest.raises(LookupError):
        db.update_category(
            date=date(2026, 1, 1), amount=-999,
            description="없는가게", source="kb_card", category="식비"
        )


def test_delete_transactions(db):
    tx1 = make_tx(description="스타벅스")
    tx2 = make_tx(description="맥도날드", amount=-8000)
    db.insert_transactions([tx1, tx2])
    rows = db.get_transactions()
    assert len(rows) == 2
    target_id = rows[0]["id"]
    deleted = db.delete_transactions([target_id])
    assert deleted == 1
    remaining = db.get_transactions()
    assert len(remaining) == 1
    assert remaining[0]["id"] != target_id


def test_update_transaction_category_sets_is_edited(db):
    db.insert_transactions([make_tx(category="식비")])
    row_id = db.get_transactions()[0]["id"]
    db.update_transaction(row_id, category="쇼핑")
    updated = db.get_transactions()[0]
    assert updated["category"] == "쇼핑"
    assert updated["is_edited"] == 1


def test_update_transaction_place_does_not_set_is_edited(db):
    db.insert_transactions([make_tx()])
    row_id = db.get_transactions()[0]["id"]
    db.update_transaction(row_id, place="새장소")
    updated = db.get_transactions()[0]
    assert updated["place"] == "새장소"
    assert updated["is_edited"] == 0


def test_get_available_years(db):
    db.insert_transactions([make_tx(date=date(2025, 6, 1), description="편의점", amount=-1000)])
    db.insert_transactions([make_tx(date=date(2026, 3, 1))])
    years = db.get_available_years()
    assert years == [2026, 2025]
