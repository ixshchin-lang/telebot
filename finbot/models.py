from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ParsedTx:
    """Операция, извлечённая из выписки, до сохранения в БД."""

    dt: datetime
    amount: float  # >0 зачисление, <0 списание
    description: str
    counterparty: str = ""
    bank_category: str = ""
    comment: str = ""


@dataclass
class ParsedStatement:
    bank: str  # "tbank" | "vtb"
    account_number: str  # номер договора / маска счёта
    product: str = ""
    period: str = ""
    transactions: list[ParsedTx] = field(default_factory=list)
    # Итоги, напечатанные банком (для сверки), если есть
    bank_total_in: float | None = None
    bank_total_out: float | None = None

    @property
    def total_in(self) -> float:
        return round(sum(t.amount for t in self.transactions if t.amount > 0), 2)

    @property
    def total_out(self) -> float:
        return round(-sum(t.amount for t in self.transactions if t.amount < 0), 2)
