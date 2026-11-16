from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from datetime import datetime, timedelta
from html import escape

from finbot.categorize import EXPENSE, INCOME, TRANSFER

CREDIT_COST = ("Комиссии банка", "Проценты по кредиту", "Страхование")
MONTHS = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]


def money(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ") + " ₽"


def parse_period(arg: str, now: datetime | None = None) -> tuple[datetime, datetime, str]:
    """'' / месяц / прошлый / неделя / сегодня / год / 2026-10 / 10.2026 / 2026."""
    now = now or datetime.now()
    a = (arg or "").strip().lower()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today.replace(day=1)

    def next_month(d: datetime) -> datetime:
        return d.replace(year=d.year + (d.month == 12), month=d.month % 12 + 1, day=1)

    if a in ("", "месяц", "м", "month"):
        return month_start, next_month(month_start), f"{MONTHS[now.month-1]} {now.year}"
    if a in ("прошлый", "прошлый месяц", "пм"):
        prev = (month_start - timedelta(days=1)).replace(day=1)
        return prev, month_start, f"{MONTHS[prev.month-1]} {prev.year}"
    if a in ("сегодня", "день", "д"):
        return today, today + timedelta(days=1), f"{today:%d.%m.%Y}"
    if a in ("неделя", "н", "week"):
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=7), f"неделя с {start:%d.%m}"
    if a in ("год", "г", "year"):
        start = today.replace(month=1, day=1)
        return start, start.replace(year=start.year + 1), f"{start.year} год"
    if a in ("всё", "все", "all"):
        return datetime(2000, 1, 1), datetime(2100, 1, 1), "всё время"
    if m := re.fullmatch(r"(\d{4})-(\d{1,2})", a) or re.fullmatch(r"(\d{1,2})\.(\d{4})", a):
        y, mo = (int(m.group(1)), int(m.group(2))) if len(m.group(1)) == 4 else (int(m.group(2)), int(m.group(1)))
        start = datetime(y, mo, 1)
        return start, next_month(start), f"{MONTHS[mo-1]} {y}"
    if m := re.fullmatch(r"(\d{4})", a):
        y = int(m.group(1))
        return datetime(y, 1, 1), datetime(y + 1, 1, 1), f"{y} год"
    for i, name in enumerate(MONTHS):
        if a.startswith(name[:3]):
            y = now.year if i + 1 <= now.month else now.year - 1
            start = datetime(y, i + 1, 1)
            return start, next_month(start), f"{name} {y}"
    raise ValueError("Не понял период. Примеры: месяц, прошлый, неделя, год, 2026-10, 10.2026, октябрь")


def summary(rows, title: str) -> str:
    inc = sum(r["amount"] for r in rows if r["kind"] == INCOME)
    exp = -sum(r["amount"] for r in rows if r["kind"] == EXPENSE)
    trans = sum(abs(r["amount"]) for r in rows if r["kind"] == TRANSFER) / 2
    by_cat: dict[str, float] = defaultdict(float)
    by_inc: dict[str, float] = defaultdict(float)
    people: dict[str, float] = defaultdict(float)
    for r in rows:
        if r["kind"] == EXPENSE:
            by_cat[r["category"]] -= r["amount"]
            if r["category"] == "Переводы людям":
                people[r["counterparty"] or r["description"][:30]] -= r["amount"]
        elif r["kind"] == INCOME:
            by_inc[r["category"]] += r["amount"]

    lines = [f"<b>📊 Отчёт: {escape(title)}</b>", ""]
    if not rows:
        return "\n".join(lines + ["Операций за период нет."])
    lines += [
        f"💰 Доходы: <b>{money(inc)}</b>",
        f"💸 Расходы: <b>{money(exp)}</b>",
        f"{'📈' if inc >= exp else '📉'} Итог: <b>{money(inc - exp)}</b>",
    ]
    if trans:
        lines.append(f"🔁 Переводы между своими счетами: {money(trans)} (не учитываются)")
    if by_cat:
        lines += ["", "<b>Расходы по категориям:</b>"]
        for cat, v in sorted(by_cat.items(), key=lambda x: -x[1]):
            share = v / exp * 100 if exp else 0
            lines.append(f"• {escape(cat)} — {money(v)} ({share:.0f}%)")
    if by_inc:
        lines += ["", "<b>Доходы:</b>"]
        for cat, v in sorted(by_inc.items(), key=lambda x: -x[1]):
            lines.append(f"• {escape(cat)} — {money(v)}")
    cost = sum(by_cat.get(c, 0) for c in CREDIT_COST)
    if cost:
        lines += ["", f"⚠️ <b>Стоимость банков и кредитов: {money(cost)}</b> (комиссии, проценты, страховка)"]
    if people:
        lines += ["", "<b>Кому больше всего переводили:</b>"]
        for who, v in sorted(people.items(), key=lambda x: -x[1])[:7]:
            lines.append(f"• {escape(who)} — {money(v)}")
    return "\n".join(lines)


def monthly(rows) -> str:
    per: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        key = r["dt"][:7]
        if r["kind"] == INCOME:
            per[key][0] += r["amount"]
        elif r["kind"] == EXPENSE:
            per[key][1] -= r["amount"]
    if not per:
        return "Операций нет."
    lines = ["<b>📅 По месяцам</b> (доход / расход / итог)", ""]
    for k in sorted(per):
        i, e = per[k]
        y, m = k.split("-")
        lines.append(f"{MONTHS[int(m)-1][:3]} {y}: {money(i)} / {money(e)} / <b>{money(i - e)}</b>")
    return "\n".join(lines)


def to_csv(rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Дата", "Счёт", "Сумма", "Тип", "Категория", "Описание", "Контрагент", "Комментарий"])
    kinds = {INCOME: "доход", EXPENSE: "расход", TRANSFER: "перевод"}
    for r in rows:
        w.writerow([r["dt"], r["account_name"], f"{r['amount']:.2f}".replace(".", ","), kinds.get(r["kind"], r["kind"]),
                    r["category"], r["description"], r["counterparty"], r["comment"]])
    return ("﻿" + buf.getvalue()).encode("utf-8")
