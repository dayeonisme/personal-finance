from datetime import date
import pytest
from models import Transaction, CategorizedTransaction
from parser.categorizer import categorize, load_rules


def make_tx(description: str, place: str = "") -> Transaction:
    return Transaction(
        date=date(2026, 3, 1),
        amount=-5000,
        description=description,
        place=place,
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


def _make_rules(tmp_path, content: str) -> dict:
    rules_yaml = tmp_path / "categories.yaml"
    rules_yaml.write_text(content, encoding="utf-8")
    return load_rules(str(rules_yaml))


def test_place_matches_before_description(tmp_path):
    """place에 키워드 있으면 description 무시하고 place 기준으로 분류"""
    rules = _make_rules(tmp_path,
        "rules:\n  - match: ['스타벅스']\n    category: 식비\ndefault_category: 미분류\n"
    )
    tx = make_tx(description="카드결제", place="스타벅스 강남점")
    result = categorize([tx], rules)
    assert result[0].category == "식비"


def test_description_used_when_place_empty(tmp_path):
    """place가 비어 있으면 description으로 폴백"""
    rules = _make_rules(tmp_path,
        "rules:\n  - match: ['맥도날드']\n    category: 식비\ndefault_category: 미분류\n"
    )
    tx = make_tx(description="맥도날드 홍대점", place="")
    result = categorize([tx], rules)
    assert result[0].category == "식비"


def test_place_match_takes_priority_over_description_match(tmp_path):
    """place와 description 둘 다 매칭될 때 place 카테고리가 우선"""
    rules = _make_rules(tmp_path,
        "rules:\n"
        "  - match: ['스타벅스']\n    category: 카페\n"
        "  - match: ['결제']\n    category: 기타\n"
        "default_category: 미분류\n"
    )
    tx = make_tx(description="카드결제", place="스타벅스 삼성점")
    result = categorize([tx], rules)
    assert result[0].category == "카페"
