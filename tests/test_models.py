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
