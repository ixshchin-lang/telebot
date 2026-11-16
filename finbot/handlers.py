from __future__ import annotations

import logging
import tempfile
import re
from datetime import timedelta
from html import escape
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from finbot import reports
from finbot.categorize import EXPENSE, INCOME, KIND_NAMES, TRANSFER
from finbot.db import DB
from finbot.manual import parse_entry
from finbot.parsers.detect import parse_statement

log = logging.getLogger(__name__)
router = Router()

KIND_WORDS = {"доход": INCOME, "расход": EXPENSE, "перевод": TRANSFER, "свои": TRANSFER}

HELP = """<b>Финансовый помощник</b>

<b>Записать вручную</b> — просто напишите:
<code>500 продукты</code> — расход
<code>1.5к такси с вокзала</code> — расход с комментарием
<code>+80000 зп</code> — доход

<b>Загрузить выписку</b> — пришлите файлом:
• PDF «Справка о движении средств» из Т-Банка
• CSV-выгрузку операций из ВТБ Онлайн
Повторная загрузка не создаёт дублей. Переводы между вашими картами находятся сами и не считаются доходом/расходом.

<b>Отчёты</b>
/report — текущий месяц (/report прошлый, неделя, год, 2026-10, октябрь, всё)
/months — по месяцам (/months 2026, всё)
/export — выгрузка в CSV (тот же выбор периода)

<b>Настройка</b>
/accounts — счета и обороты
/rename 2 ВТБ зарплатная — переименовать счёт
/rule 5722835740 = Жена — правило: всё, где встречается текст, → категория
/rule Иван Николаевич Щ = свои перевод — пометить переводы себе
/rules, /delrule 3 — список и удаление правил
/find текст — поиск операций (номер, имя, магазин)
/cat 123 Подарки расход — поменять категорию одной операции
/undo — удалить последнюю ручную запись
/wipe — удалить все свои данные"""


@router.message(CommandStart())
@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP)


def _period(arg: str | None):
    return reports.parse_period(arg or "")


@router.message(Command("report"))
async def cmd_report(message: Message, command: CommandObject, db: DB) -> None:
    try:
        start, end, title = _period(command.args)
    except ValueError as e:
        await message.answer(str(e))
        return
    rows = db.transactions(message.from_user.id, start, end)
    await message.answer(reports.summary(rows, title))


@router.message(Command("months"))
async def cmd_months(message: Message, command: CommandObject, db: DB) -> None:
    try:
        start, end, _ = _period(command.args or "всё")
    except ValueError as e:
        await message.answer(str(e))
        return
    await message.answer(reports.monthly(db.transactions(message.from_user.id, start, end)))


@router.message(Command("export"))
async def cmd_export(message: Message, command: CommandObject, db: DB) -> None:
    try:
        start, end, title = _period(command.args or "всё")
    except ValueError as e:
        await message.answer(str(e))
        return
    rows = db.transactions(message.from_user.id, start, end)
    if not rows:
        await message.answer("Операций за период нет.")
        return
    await message.answer_document(
        BufferedInputFile(reports.to_csv(rows), filename=f"операции_{title.replace(' ', '_')}.csv"),
        caption=f"{len(rows)} операций, {title}. Открывается в Excel.",
    )


@router.message(Command("accounts"))
async def cmd_accounts(message: Message, db: DB) -> None:
    accs = db.accounts(message.from_user.id)
    if not accs:
        await message.answer("Счетов пока нет. Пришлите выписку или запишите трату, например «500 продукты».")
        return
    lines = ["<b>💳 Счета</b>", ""]
    for a in accs:
        kind = " (кредитка)" if a["is_credit"] else ""
        period = f"{a['first_dt'][:10]} — {a['last_dt'][:10]}" if a["n"] else "нет операций"
        lines.append(
            f"<b>{a['id']}. {escape(a['name'])}</b>{kind}\n"
            f"   операций: {a['n']}, {period}\n"
            f"   изменение остатка за период: {reports.money(a['balance'])}"
        )
    lines.append("\nПереименовать: /rename &lt;номер&gt; &lt;название&gt;")
    await message.answer("\n".join(lines))


@router.message(Command("rename"))
async def cmd_rename(message: Message, command: CommandObject, db: DB) -> None:
    parts = (command.args or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[0].isdigit():
        await message.answer("Пример: /rename 2 ВТБ зарплатная")
        return
    name = parts[1].strip()
    is_credit = True if "кредит" in name.lower() else None
    ok = db.rename_account(message.from_user.id, int(parts[0]), name, is_credit)
    await message.answer("Готово ✅" if ok else "Нет такого счёта. Смотрите /accounts")


@router.message(Command("rule"))
async def cmd_rule(message: Message, command: CommandObject, db: DB) -> None:
    args = command.args or ""
    if "=" not in args:
        await message.answer(
            "Формат: /rule &lt;текст&gt; = &lt;категория&gt; [доход|расход|перевод]\n"
            "Примеры:\n<code>/rule 5722835740 = Жена</code>\n<code>/rule Иван Николаевич Щ = Между своими счетами перевод</code>"
        )
        return
    pattern, right = (x.strip() for x in args.split("=", 1))
    words = right.split()
    kind = None
    if words and words[-1].lower() in KIND_WORDS:
        kind = KIND_WORDS[words.pop().lower()]
    category = " ".join(words) or "Без категории"
    if category.lower() == "свои":
        category, kind = "Между своими счетами", TRANSFER
    rule_id = db.add_rule(message.from_user.id, re.escape(pattern), category, kind)
    found = db.search(message.from_user.id, pattern, limit=1000)
    await message.answer(
        f"Правило #{rule_id} добавлено: «{escape(pattern)}» → {escape(category)}"
        f"{' (' + KIND_NAMES[kind] + ')' if kind else ''}. Пересчитано операций: {len(found)}."
    )


@router.message(Command("rules"))
async def cmd_rules(message: Message, db: DB) -> None:
    rows = db.list_rules(message.from_user.id)
    if not rows:
        await message.answer("Своих правил пока нет. Добавить: /rule")
        return
    lines = ["<b>Правила</b> (новые важнее старых)"]
    for r in rows:
        pat = re.sub(r"\\(.)", r"\1", r["pattern"])
        lines.append(f"{r['id']}. «{escape(pat)}» → {escape(r['category'])}{' (' + KIND_NAMES.get(r['kind'], '') + ')' if r['kind'] else ''}")
    lines.append("\nУдалить: /delrule &lt;номер&gt;")
    await message.answer("\n".join(lines))


@router.message(Command("delrule"))
async def cmd_delrule(message: Message, command: CommandObject, db: DB) -> None:
    arg = (command.args or "").strip()
    ok = arg.isdigit() and db.delete_rule(message.from_user.id, int(arg))
    await message.answer("Удалено ✅" if ok else "Пример: /delrule 3 (номера в /rules)")


@router.message(Command("find"))
async def cmd_find(message: Message, command: CommandObject, db: DB) -> None:
    text = (command.args or "").strip()
    if not text:
        await message.answer("Пример: /find 79213394825 или /find пятерочка")
        return
    rows = db.search(message.from_user.id, text)
    if not rows:
        await message.answer("Ничего не нашёл.")
        return
    total = sum(r["amount"] for r in rows)
    lines = [f"<b>Найдено {len(rows)}</b> (показаны последние), сумма {reports.money(total)}", ""]
    for r in rows:
        lines.append(f"#{r['id']} {r['dt'][:10]} <b>{reports.money(r['amount'])}</b> {escape(r['category'])} — {escape(r['description'][:60])}")
    lines.append("\nПоменять категорию: /cat &lt;#&gt; &lt;категория&gt; [доход|расход|перевод]")
    await message.answer("\n".join(lines)[:4000])


@router.message(Command("cat"))
async def cmd_cat(message: Message, command: CommandObject, db: DB) -> None:
    parts = (command.args or "").split()
    if len(parts) < 2 or not parts[0].lstrip("#").isdigit():
        await message.answer("Пример: /cat 123 Подарки расход")
        return
    tx_id = int(parts[0].lstrip("#"))
    words = parts[1:]
    kind = KIND_WORDS.get(words[-1].lower()) if len(words) > 1 else None
    if kind:
        words = words[:-1]
    category = " ".join(words)
    if not kind:
        kind = TRANSFER if category.lower() in ("свои", "между своими счетами") else None
    row = db.conn.execute("SELECT amount FROM transactions WHERE id=? AND user_id=?", (tx_id, message.from_user.id)).fetchone()
    if not row:
        await message.answer("Нет такой операции.")
        return
    kind = kind or (INCOME if row["amount"] > 0 else EXPENSE)
    db.set_tx_category(message.from_user.id, tx_id, category, kind)
    await message.answer(f"#{tx_id} → {escape(category)} ({KIND_NAMES[kind]}) ✅")


@router.message(Command("undo"))
async def cmd_undo(message: Message, db: DB) -> None:
    row = db.last_manual(message.from_user.id)
    if not row:
        await message.answer("Ручных записей нет.")
        return
    db.delete_tx(message.from_user.id, row["id"])
    await message.answer(f"Удалено: {reports.money(row['amount'])} {escape(row['category'])}")


@router.message(Command("wipe"))
async def cmd_wipe(message: Message) -> None:
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Да, удалить всё", callback_data="wipe:yes"),
        InlineKeyboardButton(text="Отмена", callback_data="wipe:no"),
    ]])
    await message.answer("Удалить ВСЕ ваши счета, операции и правила? Это нельзя отменить.", reply_markup=kb)


@router.callback_query(F.data.startswith("wipe:"))
async def cb_wipe(cb: CallbackQuery, db: DB) -> None:
    if cb.data == "wipe:yes":
        db.wipe(cb.from_user.id)
        await cb.message.edit_text("Все данные удалены.")
    else:
        await cb.message.edit_text("Отменено.")
    await cb.answer()


@router.callback_query(F.data.startswith("del:"))
async def cb_delete(cb: CallbackQuery, db: DB) -> None:
    tx_id = int(cb.data.split(":")[1])
    ok = db.delete_tx(cb.from_user.id, tx_id)
    await cb.message.edit_text(cb.message.html_text + ("\n<i>Удалено</i>" if ok else ""))
    await cb.answer()


def _account_name(bank: str, number: str, product: str) -> str:
    tail = number.lstrip("*")[-4:]
    if bank == "tbank":
        return f"Т-Банк …{tail}"
    if bank == "vtb":
        return f"ВТБ {product or 'счёт'} …{tail}"
    return f"{bank} …{tail}"


@router.message(F.document)
async def on_document(message: Message, bot: Bot, db: DB) -> None:
    doc = message.document
    suffix = Path(doc.file_name or "file").suffix.lower()
    if suffix not in (".pdf", ".csv", ".txt"):
        await message.answer("Пришлите PDF-справку Т-Банка или CSV-выгрузку ВТБ.")
        return
    if doc.file_size and doc.file_size > 20 * 1024 * 1024:
        await message.answer("Файл больше 20 МБ — Telegram не даст его скачать боту.")
        return
    status = await message.answer("⏳ Разбираю выписку…")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"statement{suffix}"
        await bot.download(doc, destination=path)
        try:
            st = parse_statement(str(path))
        except Exception as e:  # noqa: BLE001
            log.exception("parse failed")
            await status.edit_text(f"Не получилось разобрать файл: {escape(str(e))}")
            return
    uid = message.from_user.id
    res = db.import_statement(uid, st, _account_name(st.bank, st.account_number, st.product))

    check = ""
    if st.bank_total_in is not None and st.bank_total_out is not None:
        ok = abs(st.total_in - st.bank_total_in) < 0.01 and abs(st.total_out - st.bank_total_out) < 0.01
        check = "\n✅ Итоги совпадают со справкой банка" if ok else (
            f"\n⚠️ Итоги не совпали с банком: у меня +{reports.money(st.total_in)} / −{reports.money(st.total_out)}, "
            f"в справке +{reports.money(st.bank_total_in)} / −{reports.money(st.bank_total_out)}"
        )
    warn = ""
    if st.bank == "vtb" and st.total_out > st.total_in * 3:
        warn = ("\n\n⚠️ Списаний сильно больше, чем зачислений. Похоже, в выгрузке не все поступления "
                "(например, зарплата приходит на другой счёт). Пришлите выписку и по нему.")
    dts = [t.dt for t in st.transactions]
    rows = db.transactions(uid, min(dts), max(dts) + timedelta(minutes=1))
    await status.edit_text(
        f"<b>📥 Выписка загружена</b> — {escape(_account_name(st.bank, st.account_number, st.product))}\n"
        f"Период: {st.period}\nОпераций: {len(st.transactions)} (новых {res['added']}, уже были {res['skipped']})\n"
        f"Пополнения: {reports.money(st.total_in)}, списания: {reports.money(st.total_out)}{check}{warn}"
    )
    await message.answer(reports.summary(rows, f"период выписки {st.period}")[:4000])


@router.message(F.text & ~F.text.startswith("/"))
async def on_text(message: Message, db: DB) -> None:
    entry = parse_entry(message.text)
    if not entry:
        await message.answer("Не понял 🤔 Напишите, например, «500 продукты» или «+80000 зп». Все команды: /help")
        return
    tx_id = db.add_manual(message.from_user.id, entry.amount, entry.category, entry.comment)
    sign = "💰 Доход" if entry.amount > 0 else "💸 Расход"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отменить", callback_data=f"del:{tx_id}")]])
    comment = f" — {escape(entry.comment)}" if entry.comment else ""
    await message.answer(f"{sign}: <b>{reports.money(abs(entry.amount))}</b>, {escape(entry.category)}{comment}", reply_markup=kb)
