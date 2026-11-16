"""Разбор PDF «Справка о движении средств» Т-Банка.

Таблица имеет фиксированные колонки:
дата/время операции | дата списания | сумма в валюте операции |
сумма в валюте карты | описание | номер карты.
Одна операция занимает несколько строк: в первой — даты, суммы и начало
описания, в следующих — время и продолжение описания.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable

from finbot.models import ParsedStatement, ParsedTx

DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")
CONTRACT_RE = re.compile(r"Номер договора:\s*(\d+)")
PERIOD_RE = re.compile(r"за период с (\d{2}\.\d{2}\.\d{4}) по (\d{2}\.\d{2}\.\d{4})")
TOTAL_RE = re.compile(r"^(Пополнения|Расходы):\s*([\d\s ]+,\d{2})")
PHONE_RE = re.compile(r"\+7\d{10}")


def _money(text: str) -> float:
    text = text.replace("₽", "").replace(" ", "").replace(" ", "")
    return float(text.replace(",", "."))


def _group_lines(words: Iterable[dict], tol: float = 3.0) -> list[list[dict]]:
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if lines and abs(lines[-1][0]["top"] - w["top"]) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def _columns(header: list[dict]) -> dict[str, float] | None:
    """Определяет левые границы колонок по строке заголовка таблицы."""
    xs = {}
    texts = [w["text"] for w in header]
    if "Описание" not in texts or "Номер" not in texts:
        return None
    sums = [w["x0"] for w in header if w["text"] == "Сумма"]
    dates = [w["x0"] for w in header if w["text"] == "Дата"]
    if len(sums) < 2 or len(dates) < 2:
        return None
    xs["date2"] = dates[1]
    xs["amt1"] = sums[0]
    xs["amt2"] = sums[1]
    xs["desc"] = next(w["x0"] for w in header if w["text"] == "Описание")
    xs["card"] = next(w["x0"] for w in header if w["text"] == "Номер")
    return xs


def _col(x: float, cols: dict[str, float]) -> str:
    eps = 4
    if x >= cols["card"] - eps:
        return "card"
    if x >= cols["desc"] - eps:
        return "desc"
    if x >= cols["amt2"] - eps:
        return "amt2"
    if x >= cols["amt1"] - eps:
        return "amt1"
    if x >= cols["date2"] - eps:
        return "date2"
    return "date1"


def parse_pages_words(pages_words: list[list[dict]]) -> ParsedStatement:
    """Чистая функция разбора: на вход — слова pdfplumber по страницам."""
    st = ParsedStatement(bank="tbank", account_number="")
    rows: list[dict] = []
    cur: dict | None = None
    cols: dict[str, float] | None = None

    for words in pages_words:
        for line in _group_lines(words):
            text = " ".join(w["text"] for w in line)
            if not st.account_number and (m := CONTRACT_RE.search(text)):
                st.account_number = m.group(1)
            if not st.period and (m := PERIOD_RE.search(text)):
                st.period = f"{m.group(1)}–{m.group(2)}"
            if m := TOTAL_RE.match(text):
                val = _money(m.group(2))
                if m.group(1) == "Пополнения":
                    st.bank_total_in = val
                else:
                    st.bank_total_out = val
                cur = None
                continue
            if (c := _columns(line)) is not None:
                cols = c
                cur = None
                continue
            if cols is None:
                continue
            if text.startswith("АО «ТБанк»") or text.startswith("БИК "):
                cur = None
                continue

            cells: dict[str, list[str]] = {}
            for w in line:
                cells.setdefault(_col(w["x0"], cols), []).append(w["text"])
            first = cells.get("date1", [""])[0]
            if DATE_RE.match(first) and "amt2" in cells:
                cur = {
                    "date": first,
                    "time": "00:00",
                    "amount": _money("".join(cells["amt2"])),
                    "desc": " ".join(cells.get("desc", [])),
                }
                rows.append(cur)
            elif cur is not None:
                if TIME_RE.match(first) and cur["time"] == "00:00":
                    cur["time"] = first
                extra = " ".join(cells.get("desc", []))
                if extra:
                    cur["desc"] += " " + extra

    for r in rows:
        desc = re.sub(r"\s+", " ", r["desc"]).strip()
        desc = desc.replace("T- Mobile", "T-Mobile").replace("T- Bundle", "T-Bundle")
        phone = PHONE_RE.search(desc)
        contract = re.search(r"договор[а]?\s+(\d{10})", desc)
        counterparty = phone.group(0) if phone else (contract.group(1) if contract else "")
        st.transactions.append(
            ParsedTx(
                dt=datetime.strptime(f"{r['date']} {r['time']}", "%d.%m.%Y %H:%M"),
                amount=r["amount"],
                description=desc,
                counterparty=counterparty,
            )
        )
    return st


def parse_tbank_pdf(path: str) -> ParsedStatement:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        pages = [p.extract_words(keep_blank_chars=False) for p in pdf.pages]
    st = parse_pages_words(pages)
    if not st.transactions:
        raise ValueError("Не нашёл операций — это точно справка о движении средств Т-Банка?")
    return st
