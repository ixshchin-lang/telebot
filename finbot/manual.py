"""Разбор ручного ввода: «500 продукты», «+80000 зп аванс», «1.5к такси»."""
from __future__ import annotations

import re
from dataclasses import dataclass

from finbot.categorize import manual_category

ENTRY_RE = re.compile(
    r"^\s*(?P<sign>[+-])?\s*(?P<num>\d[\d\s]*(?:[.,]\d+)?)\s*(?P<k>к|k|тыс)?\.?(?:\s+(?P<cat>\S+))?(?:\s+(?P<comment>.+))?\s*$",
    re.IGNORECASE,
)


@dataclass
class ManualEntry:
    amount: float
    category: str
    comment: str


def parse_entry(text: str) -> ManualEntry | None:
    m = ENTRY_RE.match(text)
    if not m:
        return None
    value = float(m.group("num").replace(" ", "").replace(",", "."))
    if m.group("k"):
        value *= 1000
    if value <= 0:
        return None
    amount = value if m.group("sign") == "+" else -value
    cat = manual_category(m.group("cat") or ("прочее" if amount < 0 else "доход"))
    if cat == "Прочее":
        cat = "Прочие расходы" if amount < 0 else "Прочие поступления"
    if cat == "Доход":
        cat = "Прочие поступления"
    return ManualEntry(amount=round(amount, 2), category=cat, comment=(m.group("comment") or "").strip())
