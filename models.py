from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Transaction:
    """Unified transaction model"""
    date: datetime
    description: str
    amount: float
    card_provider: str
    category: Optional[str] = None

    def __str__(self):
        return f"{self.date.strftime('%Y-%m-%d')} | {self.card_provider:5} | ${self.amount:8.2f} | {self.description[:40]:40} | {self.category or 'Uncategorized'}"
