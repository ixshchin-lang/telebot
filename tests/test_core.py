from datetime import datetime

from finbot.categorize import EXPENSE, INCOME, TRANSFER, classify
from finbot.db import DB
from finbot.manual import parse_entry
from finbot.models import ParsedStatement, ParsedTx
from finbot.parsers.tbank_pdf import parse_pages_words
from finbot.parsers.vtb_csv import parse_vtb_text
from finbot.reports import parse_period, summary

HEADER = [("Дата", 56), ("и", 76), ("время", 82), ("Дата", 126), ("Сумма", 199), ("Сумма", 294), ("Описание", 389), ("Номер", 499)]


def _w(text, x, top):
    return {"text": text, "x0": x, "top": top}


def test_tbank_words_parser():
    words = [_w("Номер", 56, 100), _w("договора:", 85, 100), _w("1111111111", 128, 100)]
    words += [_w(t, x, 200) for t, x in HEADER]
    words += [_w("14.11.2026", 56, 220), _w("14.11.2026", 126, 220), _w("-1", 199, 220), _w("400.00", 210, 220), _w("₽", 240, 220),
              _w("-1", 294, 220), _w("400.00", 305, 220), _w("₽", 337, 220), _w("Внешний", 389, 220), _w("перевод", 430, 220), _w("0001", 499, 220),
              _w("09:56", 56, 230), _w("+79990000000", 389, 230)]
    words += [_w("Пополнения:", 56, 300), _w("0,00", 126, 300), _w("₽", 150, 300),
              _w("Расходы:", 56, 310), _w("1", 126, 310), _w("400,00", 132, 310), _w("₽", 160, 310)]
    st = parse_pages_words([words])
    assert st.account_number == "1111111111"
    assert len(st.transactions) == 1
    t = st.transactions[0]
    assert t.amount == -1400.0 and t.dt == datetime(2026, 11, 14, 9, 56)
    assert t.counterparty == "+79990000000"
    assert st.bank_total_out == st.total_out == 1400.0


VTB = """Название продукта;Карта;Номер счёта/Кредитного договора;Дата и время операции;Списание/Зачисление;Сумма в валюте операции;Валюта операции;Сумма в валюте счёта;Валюта счёта;Комиссия в валюте счёта;Кешбэк;Наименование операции;Тип операции;Категория;Наименование ТСП;Код МСС;Комментарий к операции;Статус операции
Мастер-счет;;*0001;10.11.2026 09:28;Списание;-44000,0;RUB;-44000,0;RUB;0,0;;Тест Т.;Исходящий перевод СБП;Между счетами;;;;Выполнено
Мастер-счет;;*0001;10.11.2026 08:59;Зачисление;44753,75;RUB;44753,75;RUB;;;Зачисление заработной платы;Денежный перевод на карту;Зарплата;;;;Выполнено
"""


def test_vtb_parser_and_classify():
    st = parse_vtb_text(VTB)
    assert st.account_number == "*0001" and len(st.transactions) == 2
    out, inc = st.transactions
    assert classify(out.amount, out.description, out.counterparty, out.bank_category)[0] == TRANSFER
    assert classify(inc.amount, inc.description, inc.counterparty, inc.bank_category) == (INCOME, "Зарплата")


def test_classify_merchants():
    assert classify(-500, "Оплата в PYATEROCHKA 4184") == (EXPENSE, "Продукты")
    assert classify(-623, "Комиссия за внешний перевод") == (EXPENSE, "Комиссии банка")
    assert classify(-81, "Внутренний перевод на договор 5342983086", own_accounts={"5342983086"})[0] == TRANSFER


def test_manual_entry():
    e = parse_entry("1.5к такси с вокзала")
    assert e.amount == -1500 and e.category == "Такси" and e.comment == "с вокзала"
    assert parse_entry("+80000 зп").amount == 80000
    assert parse_entry("привет") is None


def test_import_dedup_and_transfer_matching(tmp_path):
    db = DB(str(tmp_path / "t.db"))
    vtb = parse_vtb_text(VTB)
    tb = ParsedStatement(bank="tbank", account_number="2222222222", transactions=[
        ParsedTx(datetime(2026, 11, 10, 9, 28), 44000.0, "Пополнение. Система быстрых платежей"),
        ParsedTx(datetime(2026, 11, 10, 12, 0), -500.0, "Оплата в PYATEROCHKA"),
    ])
    assert db.import_statement(1, vtb, "ВТБ")["added"] == 2
    assert db.import_statement(1, vtb, "ВТБ")["skipped"] == 2
    db.import_statement(1, tb, "Т-Банк")
    rows = db.transactions(1, datetime(2026, 11, 1), datetime(2026, 12, 1))
    kinds = {r["description"][:20]: r["kind"] for r in rows}
    assert kinds["Пополнение. Система "] == TRANSFER
    text = summary(rows, "тест")
    assert "Доходы: <b>44 754 ₽" in text and "Расходы: <b>500 ₽" in text


def test_period():
    s, e, _ = parse_period("2026-10")
    assert s == datetime(2026, 10, 1) and e == datetime(2026, 11, 1)
