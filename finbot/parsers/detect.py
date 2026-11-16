from __future__ import annotations

from pathlib import Path

from finbot.models import ParsedStatement
from finbot.parsers.tbank_pdf import parse_tbank_pdf
from finbot.parsers.vtb_csv import parse_vtb_csv


def parse_statement(path: str) -> ParsedStatement:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return parse_tbank_pdf(path)
    if ext in (".csv", ".txt"):
        return parse_vtb_csv(path)
    raise ValueError("Поддерживаются PDF-справки Т-Банка и CSV-выгрузки ВТБ")
