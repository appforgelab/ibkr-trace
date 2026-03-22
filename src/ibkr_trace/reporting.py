from __future__ import annotations

import csv
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import and_, func, select
from sqlalchemy.engine import Engine

from ibkr_trace.config import DEFAULT_REPORTS_DIR, ensure_runtime_dirs
from ibkr_trace.db import ensure_database
from ibkr_trace.schema import cash_income_events, instruments, trade_events
from ibkr_trace.util import canonical_decimal_text, parse_decimal


SAFE_REPORT_TOKEN_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _safe_report_token(value: str) -> str:
    token = SAFE_REPORT_TOKEN_RE.sub("_", value.strip()).strip("_")
    return token or "report"


def write_year_reports(
    engine: Engine,
    start: date,
    end: date,
    symbol: str | None = None,
    output_dir: Path | None = None,
) -> dict[str, str]:
    ensure_database(engine)
    ensure_runtime_dirs()
    output_root = output_dir or DEFAULT_REPORTS_DIR
    suffix = f"{start.isoformat()}_{end.isoformat()}"
    symbol_value = symbol.strip() if symbol else None

    trade_rows: list[dict[str, object]] = []
    dividend_rows: list[dict[str, object]] = []
    interest_rows: list[dict[str, object]] = []

    with engine.connect() as conn:
        trade_stmt = (
            select(
                trade_events.c.id,
                trade_events.c.event_date,
                trade_events.c.broker_timestamp_text,
                trade_events.c.asset_category,
                trade_events.c.currency,
                trade_events.c.symbol,
                trade_events.c.quantity_text,
                trade_events.c.trade_price_text,
                trade_events.c.proceeds_text,
                trade_events.c.comm_fee_text,
                trade_events.c.basis_text,
                trade_events.c.realized_pl_text,
                trade_events.c.code_text,
                instruments.c.underlying_symbol,
                instruments.c.expiry_date,
                instruments.c.option_right,
                instruments.c.strike_text,
            )
            .select_from(trade_events.join(instruments, trade_events.c.instrument_id == instruments.c.id))
            .where(and_(trade_events.c.event_date >= start, trade_events.c.event_date <= end))
            .order_by(trade_events.c.broker_timestamp, trade_events.c.id)
        )
        if symbol_value:
            trade_stmt = trade_stmt.where(trade_events.c.symbol == symbol_value)
        for record in conn.execute(trade_stmt).mappings():
            trade_rows.append(dict(record))

        income_stmt = (
            select(
                cash_income_events.c.id,
                cash_income_events.c.section_name,
                cash_income_events.c.event_date,
                cash_income_events.c.currency,
                cash_income_events.c.description,
                cash_income_events.c.amount_text,
            )
            .where(and_(cash_income_events.c.event_date >= start, cash_income_events.c.event_date <= end))
            .order_by(cash_income_events.c.event_date, cash_income_events.c.id)
        )
        for record in conn.execute(income_stmt).mappings():
            target = dividend_rows if record["section_name"] == "Dividends" else interest_rows
            target.append(dict(record))

    trade_path = output_root / f"trades_{suffix}.csv"
    dividend_path = output_root / f"dividends_{suffix}.csv"
    interest_path = output_root / f"interest_{suffix}.csv"

    _write_csv(
        trade_path,
        trade_rows,
        [
            "id",
            "event_date",
            "broker_timestamp_text",
            "asset_category",
            "currency",
            "symbol",
            "quantity_text",
            "trade_price_text",
            "proceeds_text",
            "comm_fee_text",
            "basis_text",
            "realized_pl_text",
            "code_text",
            "underlying_symbol",
            "expiry_date",
            "option_right",
            "strike_text",
        ],
    )
    _write_csv(dividend_path, dividend_rows, ["id", "section_name", "event_date", "currency", "description", "amount_text"])
    _write_csv(interest_path, interest_rows, ["id", "section_name", "event_date", "currency", "description", "amount_text"])

    return {
        "trades": str(trade_path),
        "dividends": str(dividend_path),
        "interest": str(interest_path),
    }


def write_symbol_report(
    engine: Engine,
    start: date,
    end: date,
    output_dir: Path | None = None,
) -> str:
    ensure_database(engine)
    ensure_runtime_dirs()
    output_root = output_dir or DEFAULT_REPORTS_DIR
    suffix = f"{start.isoformat()}_{end.isoformat()}"
    symbol_rows: list[dict[str, object]] = []

    with engine.connect() as conn:
        stmt = (
            select(
                trade_events.c.asset_category,
                trade_events.c.symbol,
                func.count().label("trade_count"),
            )
            .where(and_(trade_events.c.event_date >= start, trade_events.c.event_date <= end))
            .group_by(trade_events.c.asset_category, trade_events.c.symbol)
            .order_by(trade_events.c.asset_category, trade_events.c.symbol)
        )
        for record in conn.execute(stmt).mappings():
            symbol_rows.append(dict(record))

    output_path = output_root / f"symbols_{suffix}.csv"
    _write_csv(output_path, symbol_rows, ["asset_category", "symbol", "trade_count"])
    return str(output_path)


def write_ledger_report(
    engine: Engine,
    symbol: str,
    end: date,
    output_dir: Path | None = None,
) -> str:
    ensure_database(engine)
    ensure_runtime_dirs()
    output_root = output_dir or DEFAULT_REPORTS_DIR
    symbol_value = symbol.strip()
    running_quantity = Decimal("0")
    ledger_rows: list[dict[str, object]] = []

    with engine.connect() as conn:
        stmt = (
            select(
                trade_events.c.id,
                trade_events.c.event_date,
                trade_events.c.broker_timestamp_text,
                trade_events.c.asset_category,
                trade_events.c.currency,
                trade_events.c.symbol,
                trade_events.c.quantity_text,
                trade_events.c.trade_price_text,
                trade_events.c.proceeds_text,
                trade_events.c.comm_fee_text,
                trade_events.c.code_text,
            )
            .where(and_(trade_events.c.symbol == symbol_value, trade_events.c.event_date <= end))
            .order_by(trade_events.c.broker_timestamp, trade_events.c.id)
        )
        for record in conn.execute(stmt).mappings():
            quantity = parse_decimal(record["quantity_text"]) or Decimal("0")
            running_quantity += quantity
            ledger_rows.append(
                {
                    **dict(record),
                    "direction": "BUY" if quantity > 0 else "SELL" if quantity < 0 else "",
                    "running_quantity_text": canonical_decimal_text(str(running_quantity)) or "0",
                }
            )

    output_path = output_root / f"ledger_{_safe_report_token(symbol_value)}_{end.isoformat()}.csv"
    _write_csv(
        output_path,
        ledger_rows,
        [
            "id",
            "event_date",
            "broker_timestamp_text",
            "asset_category",
            "currency",
            "symbol",
            "direction",
            "quantity_text",
            "trade_price_text",
            "comm_fee_text",
            "proceeds_text",
            "code_text",
            "running_quantity_text",
        ],
    )
    return str(output_path)
