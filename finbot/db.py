"""Хранилище на SQLite. Все данные разделены по user_id Telegram."""
from __future__ import annotations

import hashlib
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from finbot.categorize import EXPENSE, INCOME, TRANSFER, Rule, classify
from finbot.models import ParsedStatement

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    bank TEXT NOT NULL DEFAULT '',
    number TEXT NOT NULL DEFAULT '',
    is_credit INTEGER NOT NULL DEFAULT 0,
    UNIQUE(user_id, bank, number)
);
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    dt TEXT NOT NULL,
    amount REAL NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    counterparty TEXT NOT NULL DEFAULT '',
    bank_category TEXT NOT NULL DEFAULT '',
    comment TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL,
    category TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual',
    pair_id INTEGER,
    manual_override INTEGER NOT NULL DEFAULT 0,
    hash TEXT NOT NULL,
    UNIQUE(user_id, hash)
);
CREATE INDEX IF NOT EXISTS ix_tx_user_dt ON transactions(user_id, dt);
CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    pattern TEXT NOT NULL,
    category TEXT NOT NULL,
    kind TEXT
);
"""

DT_FMT = "%Y-%m-%d %H:%M"
MANUAL_ACCOUNT = "Наличные / вручную"
# Категории, которые могут оказаться половинками перевода между своими счетами
PAIRABLE_OUT = ("Переводы людям", "Между своими счетами")
PAIRABLE_IN = ("Пополнения", "Переводы от людей", "Между своими счетами", "Прочие поступления")


class DB:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)

    # ---------- счета ----------
    def get_or_create_account(self, user_id: int, bank: str, number: str, name: str, is_credit: bool = False) -> int:
        row = self.conn.execute(
            "SELECT id FROM accounts WHERE user_id=? AND bank=? AND number=?", (user_id, bank, number)
        ).fetchone()
        if row:
            return row["id"]
        cur = self.conn.execute(
            "INSERT INTO accounts(user_id, name, bank, number, is_credit) VALUES (?,?,?,?,?)",
            (user_id, name, bank, number, int(is_credit)),
        )
        self.conn.commit()
        return cur.lastrowid

    def accounts(self, user_id: int) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT a.*, COALESCE(SUM(t.amount),0) AS balance, COUNT(t.id) AS n,
                      MIN(t.dt) AS first_dt, MAX(t.dt) AS last_dt
               FROM accounts a LEFT JOIN transactions t ON t.account_id=a.id
               WHERE a.user_id=? GROUP BY a.id ORDER BY a.id""",
            (user_id,),
        ).fetchall()

    def rename_account(self, user_id: int, account_id: int, name: str, is_credit: bool | None = None) -> bool:
        cur = self.conn.execute("UPDATE accounts SET name=? WHERE id=? AND user_id=?", (name, account_id, user_id))
        if is_credit is not None:
            self.conn.execute("UPDATE accounts SET is_credit=? WHERE id=? AND user_id=?", (int(is_credit), account_id, user_id))
        self.conn.commit()
        return cur.rowcount > 0

    def own_numbers(self, user_id: int) -> set[str]:
        return {r["number"] for r in self.conn.execute("SELECT number FROM accounts WHERE user_id=?", (user_id,))}

    # ---------- правила ----------
    def user_rules(self, user_id: int) -> list[Rule]:
        rows = self.conn.execute("SELECT pattern, category, kind FROM rules WHERE user_id=? ORDER BY id DESC", (user_id,))
        return [Rule(r["pattern"], r["category"], r["kind"]) for r in rows]

    def list_rules(self, user_id: int) -> list[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM rules WHERE user_id=? ORDER BY id", (user_id,)).fetchall()

    def add_rule(self, user_id: int, pattern: str, category: str, kind: str | None) -> int:
        cur = self.conn.execute(
            "INSERT INTO rules(user_id, pattern, category, kind) VALUES (?,?,?,?)", (user_id, pattern, category, kind)
        )
        self.conn.commit()
        self.reclassify(user_id)
        return cur.lastrowid

    def delete_rule(self, user_id: int, rule_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM rules WHERE id=? AND user_id=?", (rule_id, user_id))
        self.conn.commit()
        if cur.rowcount:
            self.reclassify(user_id)
        return cur.rowcount > 0

    def reclassify(self, user_id: int) -> None:
        rules, own = self.user_rules(user_id), self.own_numbers(user_id)
        rows = self.conn.execute(
            "SELECT * FROM transactions WHERE user_id=? AND manual_override=0", (user_id,)
        ).fetchall()
        self.conn.execute("UPDATE transactions SET pair_id=NULL WHERE user_id=? AND manual_override=0", (user_id,))
        for r in rows:
            kind, cat = classify(r["amount"], r["description"], r["counterparty"], r["bank_category"], r["comment"], rules, own)
            self.conn.execute("UPDATE transactions SET kind=?, category=? WHERE id=?", (kind, cat, r["id"]))
        self.conn.commit()
        self.match_transfers(user_id)

    # ---------- операции ----------
    @staticmethod
    def _hash(account_id: int, dt: str, amount: float, desc: str, n: int) -> str:
        return hashlib.sha1(f"{account_id}|{dt}|{amount:.2f}|{desc}|{n}".encode()).hexdigest()

    def import_statement(self, user_id: int, st: ParsedStatement, account_name: str) -> dict:
        is_credit = st.bank == "tbank" and any("Проценты по кредиту" in t.description for t in st.transactions)
        acc = self.get_or_create_account(user_id, st.bank, st.account_number, account_name, is_credit)
        rules, own = self.user_rules(user_id), self.own_numbers(user_id)
        seen: Counter = Counter()
        added = skipped = 0
        for t in st.transactions:
            dt = t.dt.strftime(DT_FMT)
            key = (dt, round(t.amount, 2), t.description)
            seen[key] += 1
            h = self._hash(acc, dt, t.amount, t.description, seen[key])
            kind, cat = classify(t.amount, t.description, t.counterparty, t.bank_category, t.comment, rules, own)
            cur = self.conn.execute(
                """INSERT OR IGNORE INTO transactions
                   (user_id, account_id, dt, amount, description, counterparty, bank_category, comment, kind, category, source, hash)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (user_id, acc, dt, t.amount, t.description, t.counterparty, t.bank_category, t.comment, kind, cat, st.bank, h),
            )
            if cur.rowcount:
                added += 1
            else:
                skipped += 1
        self.conn.commit()
        # новый счёт мог сделать «своими» переводы на его договор — пересчитаем
        self.reclassify(user_id)
        return {"account_id": acc, "added": added, "skipped": skipped}

    def add_manual(self, user_id: int, amount: float, category: str, comment: str, dt: datetime | None = None) -> int:
        acc = self.get_or_create_account(user_id, "manual", "", MANUAL_ACCOUNT)
        dt_s = (dt or datetime.now()).strftime(DT_FMT)
        kind = INCOME if amount > 0 else EXPENSE
        h = hashlib.sha1(f"manual|{user_id}|{datetime.now().isoformat()}|{amount}|{comment}".encode()).hexdigest()
        cur = self.conn.execute(
            """INSERT INTO transactions(user_id, account_id, dt, amount, description, comment, kind, category, source, manual_override, hash)
               VALUES (?,?,?,?,?,?,?,?,'manual',1,?)""",
            (user_id, acc, dt_s, amount, comment or category, comment, kind, category, h),
        )
        self.conn.commit()
        return cur.lastrowid

    def delete_tx(self, user_id: int, tx_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (tx_id, user_id))
        self.conn.commit()
        return cur.rowcount > 0

    def last_manual(self, user_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM transactions WHERE user_id=? AND source='manual' ORDER BY id DESC LIMIT 1", (user_id,)
        ).fetchone()

    def set_tx_category(self, user_id: int, tx_id: int, category: str, kind: str) -> bool:
        cur = self.conn.execute(
            "UPDATE transactions SET category=?, kind=?, manual_override=1 WHERE id=? AND user_id=?",
            (category, kind, tx_id, user_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def match_transfers(self, user_id: int, window_minutes: int = 60) -> int:
        """Склеивает списание с одного своего счёта и зачисление той же суммы на другой."""
        q_out = f"SELECT * FROM transactions WHERE user_id=? AND amount<0 AND pair_id IS NULL AND category IN ({','.join('?'*len(PAIRABLE_OUT))}) ORDER BY dt"
        q_in = f"SELECT * FROM transactions WHERE user_id=? AND amount>0 AND pair_id IS NULL AND category IN ({','.join('?'*len(PAIRABLE_IN))}) ORDER BY dt"
        outs = self.conn.execute(q_out, (user_id, *PAIRABLE_OUT)).fetchall()
        ins = self.conn.execute(q_in, (user_id, *PAIRABLE_IN)).fetchall()
        by_amount: dict[float, list[sqlite3.Row]] = {}
        for r in ins:
            by_amount.setdefault(round(r["amount"], 2), []).append(r)
        used: set[int] = set()
        pairs = 0
        win = timedelta(minutes=window_minutes)
        for o in outs:
            odt = datetime.strptime(o["dt"], DT_FMT)
            best = None
            for i in by_amount.get(round(-o["amount"], 2), []):
                if i["id"] in used or i["account_id"] == o["account_id"]:
                    continue
                delta = abs(datetime.strptime(i["dt"], DT_FMT) - odt)
                if delta <= win and (best is None or delta < best[0]):
                    best = (delta, i)
            if best:
                i = best[1]
                used.add(i["id"])
                for a, b in ((o, i), (i, o)):
                    self.conn.execute(
                        "UPDATE transactions SET pair_id=?, kind=?, category=? WHERE id=? AND manual_override=0",
                        (b["id"], TRANSFER, "Между своими счетами", a["id"]),
                    )
                pairs += 1
        self.conn.commit()
        return pairs

    def transactions(self, user_id: int, start: datetime, end: datetime) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT t.*, a.name AS account_name, a.is_credit FROM transactions t JOIN accounts a ON a.id=t.account_id
               WHERE t.user_id=? AND t.dt>=? AND t.dt<? ORDER BY t.dt""",
            (user_id, start.strftime(DT_FMT), end.strftime(DT_FMT)),
        ).fetchall()

    def search(self, user_id: int, text: str, limit: int = 30) -> list[sqlite3.Row]:
        like = f"%{text}%"
        return self.conn.execute(
            """SELECT * FROM transactions WHERE user_id=? AND (description LIKE ? OR counterparty LIKE ? OR comment LIKE ? OR category LIKE ?)
               ORDER BY dt DESC LIMIT ?""",
            (user_id, like, like, like, like, limit),
        ).fetchall()

    def wipe(self, user_id: int) -> None:
        for table in ("transactions", "rules", "accounts"):
            self.conn.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))
        self.conn.commit()
