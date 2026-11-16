"""Автоматическая разметка операций: тип (доход/расход/перевод) и категория."""
from __future__ import annotations

import re
from dataclasses import dataclass

INCOME = "income"
EXPENSE = "expense"
TRANSFER = "transfer"  # между своими счетами — не доход и не расход

KIND_NAMES = {INCOME: "доход", EXPENSE: "расход", TRANSFER: "перевод между своими"}


@dataclass
class Rule:
    pattern: str
    category: str
    kind: str | None = None  # None — определить по знаку суммы

    def matches(self, text: str) -> bool:
        return re.search(self.pattern, text, re.IGNORECASE) is not None


# Порядок важен: первое совпадение побеждает.
DEFAULT_RULES: list[Rule] = [
    # Свои переводы и накопления
    Rule(r"перевод себе|^между счетами", "Между своими счетами", TRANSFER),
    Rule(r"инвесткопилк|брокерск|закрытие вклада|перевод на вклад|вклады и накопления.*перевод", "Накопления и инвестиции", TRANSFER),
    # Стоимость кредитов и банка
    Rule(r"проценты по кредиту", "Проценты по кредиту", EXPENSE),
    Rule(r"комиссия|плата за перевод|плата за обслуживание|плата за программу", "Комиссии банка", EXPENSE),
    Rule(r"страхов|космовизаком", "Страхование", EXPENSE),
    # Доходы
    Rule(r"заработной платы|зарплата|дополнительных\s+выплат", "Зарплата", INCOME),
    Rule(r"ветеранам|пенсион", "Соцвыплаты", INCOME),
    Rule(r"кэшбэк|кешбэк", "Кэшбэк", INCOME),
    Rule(r"выплата %|начисление процентов", "Проценты по вкладам", INCOME),
    Rule(r"возврат|отмена", "Возвраты", INCOME),
    # Наличные
    Rule(r"снятие наличных", "Наличные", EXPENSE),
    # Покупки
    Rule(r"yandex\*4121\*go|taxi|такси|citymobil", "Такси", EXPENSE),
    Rule(r"tutu|izhavia|railways|ржд|kupibilet|onetwotrip|aeroflot|pobeda|blablacar|aviasales", "Поездки и билеты", EXPENSE),
    Rule(r"practicum|синерги|skillbox|netology|geekbrains", "Обучение", EXPENSE),
    Rule(r"pyaterochka|пят[её]рочка|magnit|магнит|lenta|лента|vernyj|perekrest|перекр[её]сток|produkty|продукты|supermarket|супермаркет|ашан|auchan|fix price|samokat|lavka|dixy|дикси|\bokey\b|окей|сельский маркет|энгельс-торг|kvaligate|вкусвилл|vkusvill", "Продукты", EXPENSE),
    Rule(r"krasnoe&beloe|красное.?белое|winelab|smoke|tabak|табак|наша сеть|бристоль|bristol", "Алкоголь и табак", EXPENSE),
    Rule(r"\beda\b|\*eda|coffee|кофе|caf[eé]|кафе|burger|vkusnoitochka|kfc|rostics|bon thai|dodo|ресторан|restoran|буше|русский аппетит|surfcoffee|realcoff", "Кафе и еда вне дома", EXPENSE),
    Rule(r"megafon|мегафон|beeline|билайн|t-mobile|\bmts\b|мтс|tele2|теле2|сотовая связь|услуги связи|t-bundle|telegram", "Связь и подписки", EXPENSE),
    Rule(r"apteka|аптека|clinic|клиник|стоматолог|медицин", "Здоровье", EXPENSE),
    Rule(r"azs|азс|lukoil|лукойл|gazprom|газпром|rosneft|роснефть|shell", "Авто и топливо", EXPENSE),
    Rule(r"avito|ozon|wildberries|\bdns\b|gold apple|intimissimi|befree|crockid|котофей|flowwow|plati|leroy|лм_sbp|дм спб|детский мир|misha&teddy|game-shop", "Покупки", EXPENSE),
    # Переводы людям (если не свои счета)
    Rule(r"перевод по номеру|переводы людям|внутренний перевод на договор|перевод на карту|перевод по номеру карты|банковский перевод", "Переводы людям", EXPENSE),
    Rule(r"входящие переводы|от клиента|внутрибанковский перевод с договора|перевод с договора", "Переводы от людей", INCOME),
    Rule(r"пополнение", "Пополнения", INCOME),
]

CONTRACT_RE = re.compile(r"договор[а]?\s+(\d{10})")


def classify(
    amount: float,
    description: str,
    counterparty: str = "",
    bank_category: str = "",
    comment: str = "",
    user_rules: list[Rule] | None = None,
    own_accounts: set[str] | None = None,
) -> tuple[str, str]:
    """Возвращает (kind, category)."""
    text = " ".join(x for x in [bank_category, description, counterparty, comment] if x)

    for rule in user_rules or []:
        if rule.matches(text):
            return rule.kind or (INCOME if amount > 0 else EXPENSE), rule.category

    m = CONTRACT_RE.search(description)
    if m and own_accounts and m.group(1) in own_accounts:
        return TRANSFER, "Между своими счетами"

    for rule in DEFAULT_RULES:
        if rule.matches(text):
            kind = rule.kind or (INCOME if amount > 0 else EXPENSE)
            # знак суммы важнее правила для доход/расход
            if kind == INCOME and amount < 0:
                kind = EXPENSE
            elif kind == EXPENSE and amount > 0:
                kind = INCOME
            category = rule.category
            if category == "Переводы людям" and amount > 0:
                category = "Переводы от людей"
            return kind, category

    return (INCOME, "Прочие поступления") if amount > 0 else (EXPENSE, "Прочие расходы")


MANUAL_ALIASES = {
    "еда": "Продукты", "продукты": "Продукты", "магазин": "Продукты",
    "кафе": "Кафе и еда вне дома", "кофе": "Кафе и еда вне дома", "обед": "Кафе и еда вне дома",
    "такси": "Такси", "бензин": "Авто и топливо", "авто": "Авто и топливо",
    "связь": "Связь и подписки", "телефон": "Связь и подписки", "подписка": "Связь и подписки",
    "аптека": "Здоровье", "врач": "Здоровье", "здоровье": "Здоровье",
    "одежда": "Покупки", "покупки": "Покупки",
    "сигареты": "Алкоголь и табак", "алкоголь": "Алкоголь и табак",
    "билеты": "Поездки и билеты", "поездка": "Поездки и билеты",
    "учеба": "Обучение", "учёба": "Обучение", "курсы": "Обучение",
    "зп": "Зарплата", "зарплата": "Зарплата", "аванс": "Зарплата", "премия": "Зарплата",
    "долг": "Долги", "подарок": "Подарки", "квартира": "Жильё", "аренда": "Жильё", "жкх": "Жильё",
}


def manual_category(word: str) -> str:
    w = word.strip().lower()
    if not w:
        return "Прочие расходы"
    return MANUAL_ALIASES.get(w, word.strip().capitalize())
