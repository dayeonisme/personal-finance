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
        "rules:\n  - match: ['스타벅스']\n    category: 식비\ndefault_category: 미분류\n",
        encoding="utf-8",
    )
    rules = load_rules(str(rules_yaml))
    result = categorize([make_tx("스타벅스 강남점")], rules)
    assert result[0].category == "식비"


def test_default_category_when_no_match(tmp_path):
    rules_yaml = tmp_path / "categories.yaml"
    rules_yaml.write_text("rules: []\ndefault_category: 미분류\n", encoding="utf-8")
    rules = load_rules(str(rules_yaml))
    result = categorize([make_tx("알수없는가게")], rules)
    assert result[0].category == "미분류"


def test_first_match_wins(tmp_path):
    rules_yaml = tmp_path / "categories.yaml"
    rules_yaml.write_text(
        "rules:\n"
        "  - match: ['카페']\n    category: 식비\n"
        "  - match: ['카페']\n    category: 쇼핑\n"
        "default_category: 미분류\n",
        encoding="utf-8",
    )
    rules = load_rules(str(rules_yaml))
    result = categorize([make_tx("카페베네")], rules)
    assert result[0].category == "식비"


def test_returns_categorized_transaction_type(tmp_path):
    rules_yaml = tmp_path / "categories.yaml"
    rules_yaml.write_text("rules: []\ndefault_category: 미분류\n", encoding="utf-8")
    rules = load_rules(str(rules_yaml))
    result = categorize([make_tx("테스트")], rules)
    assert isinstance(result[0], CategorizedTransaction)
