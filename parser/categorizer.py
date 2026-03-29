from pathlib import Path

import yaml
from models import Transaction, CategorizedTransaction

_DEFAULT_RULES_PATH = Path(__file__).parent.parent / "config" / "categories.yaml"


def load_rules(path: str | Path = _DEFAULT_RULES_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def categorize(
    transactions: list[Transaction],
    rules: dict | None = None,
    rules_path: str | Path = _DEFAULT_RULES_PATH,
) -> list[CategorizedTransaction]:
    if rules is None:
        rules = load_rules(rules_path)

    default = rules.get("default_category", "미분류")
    rule_list = rules.get("rules", [])

    result = []
    for tx in transactions:
        category = default
        # place를 먼저 검사 (우선순위 높음), 매칭 없으면 description 검사
        for rule in rule_list:
            if any(kw in tx.place for kw in rule["match"]):
                category = rule["category"]
                break
        else:
            for rule in rule_list:
                if any(kw in tx.description for kw in rule["match"]):
                    category = rule["category"]
                    break
        result.append(CategorizedTransaction(
            date=tx.date,
            amount=tx.amount,
            description=tx.description,
            place=tx.place,
            source=tx.source,
            raw_source=tx.raw_source,
            category=category,
        ))
    return result
