"""Разбор CSV-выгрузки операций из ВТБ Онлайн (разделитель «;»)."""
from __future__ import annotations

import csv
import io
from datetime import datetime

from finbot.models import ParsedStatement, ParsedTx

REQUIRED = {"Дата и время операции", "Сумма в валюте операции", "Наименование операции"}


def _num(s: str) -> float:
    s = (s or "").strip().replace(" ", "").replace(" ", "").replace(",", ".")
    return float(s) if s else 0.0


def parse_vtb_text(text: str) -> ParsedStatement:
    text = text.lstrip("﻿")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
        raise ValueError("Не похоже на выгрузку ВТБ: нет нужных колонок")
    st = ParsedStatement(bank="vtb", account_number="")
    for row in reader:
        if not row.get("Дата и время операции"):
            continue
        status = (row.get("Статус операции") or "").strip()
        if status and status != "Выполнено":
            continue
        st.account_number = st.account_number or (row.get("Номер счёта/Кредитного договора") or "").strip()
        st.product = st.product or (row.get("Название продукта") or "").strip()
        amount = _num(row["Сумма в валюте операции"])
        if (row.get("Списание/Зачисление") or "").strip() == "Списание" and amount > 0:
            amount = -amount
        name = (row.get("Наименование операции") or "").strip()
        op_type = (row.get("Тип операции") or "").strip()
        merchant = (row.get("Наименование ТСП") or "").strip()
        desc = " ".join(x for x in [op_type, name, merchant] if x)
        st.transactions.append(
            ParsedTx(
                dt=datetime.strptime(row["Дата и время операции"].strip(), "%d.%m.%Y %H:%M"),
                amount=amount,
                description=desc,
                counterparty=name,
                bank_category=(row.get("Категория") or "").strip(),
                comment=(row.get("Комментарий к операции") or "").strip().strip('"').strip(),
            )
        )
    if not st.transactions:
        raise ValueError("В файле не нашлось операций")
    dts = [t.dt for t in st.transactions]
    st.period = f"{min(dts):%d.%m.%Y}–{max(dts):%d.%m.%Y}"
    return st


def parse_vtb_csv(path: str) -> ParsedStatement:
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp1251"):
        try:
            return parse_vtb_text(raw.decode(enc))
        except UnicodeDecodeError:
            continue
    raise ValueError("Не удалось прочитать кодировку файла")
