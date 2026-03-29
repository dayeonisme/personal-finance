from dataclasses import dataclass
from datetime import date


@dataclass
class Transaction:
    date: date
    amount: int          # negative = expense, positive = income (KRW)
    description: str     # memo
    source: str          # sub-account: 'kb_card', 'woori_bank', 'tmoneys', etc.
    raw_source: str      # aggregator: 'toss', 'naver_pay', 'manual', 'csv'
    place: str = ""      # merchant / location (사용 장소)


@dataclass
class CategorizedTransaction(Transaction):
    category: str = "미분류"
