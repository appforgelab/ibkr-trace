from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from sqlalchemy import Connection, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from ibkr_trace.db import ensure_database
from ibkr_trace.import_ibkr import _finish_import_run, _get_or_create_source_file, _start_import_run
from ibkr_trace.schema import fx_rates
from ibkr_trace.util import canonical_decimal_text, clean_text, parse_iso_date, utc_now


HEADER_ALIASES = {
    "date": {"date", "rate_date"},
    "base_currency": {"base_currency", "base", "from_currency"},
    "quote_currency": {"quote_currency", "quote", "to_currency"},
    "rate": {"rate", "fx_rate", "close"},
    "source_name": {"source_name", "source"},
}


def _canonical_field(fieldnames: list[str], canonical_name: str) -> str:
    aliases = HEADER_ALIASES[canonical_name]
    for field in fieldnames:
        if field.strip().lower() in aliases:
            return field
    raise ValueError(f"Missing required FX column for {canonical_name}: expected one of {sorted(aliases)}")


def _insert_rate(conn: Connection, source_file_id: int, row: dict[str, str], fields: dict[str, str]) -> None:
    rate_date = parse_iso_date(row[fields["date"]])
    base_currency = clean_text(row[fields["base_currency"]])
    quote_currency = clean_text(row[fields["quote_currency"]])
    rate_text = canonical_decimal_text(row[fields["rate"]])
    source_name = clean_text(row.get(fields.get("source_name", ""), ""))
    if rate_date is None or base_currency is None or quote_currency is None or rate_text is None:
        return

    stmt = sqlite_insert(fx_rates).values(
        source_file_id=source_file_id,
        rate_date=rate_date,
        base_currency=base_currency.upper(),
        quote_currency=quote_currency.upper(),
        rate_text=rate_text,
        source_name=source_name,
        created_at=utc_now(),
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=["rate_date", "base_currency", "quote_currency"])
    conn.execute(stmt)


def import_fx_rates(engine: Engine, path: str) -> dict[str, int | str]:
    ensure_database(engine)
    input_path = Path(path).expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"FX file not found: {input_path}")

    with engine.begin() as conn:
        run_id = _start_import_run(conn, "fx", input_path)

    try:
        with engine.begin() as conn:
            source_file_id, is_new = _get_or_create_source_file(conn, "fx", input_path)
            with input_path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                if reader.fieldnames is None:
                    raise ValueError("FX CSV has no header row")
                fields = {
                    "date": _canonical_field(reader.fieldnames, "date"),
                    "base_currency": _canonical_field(reader.fieldnames, "base_currency"),
                    "quote_currency": _canonical_field(reader.fieldnames, "quote_currency"),
                    "rate": _canonical_field(reader.fieldnames, "rate"),
                }
                if any(name.strip().lower() in HEADER_ALIASES["source_name"] for name in reader.fieldnames):
                    fields["source_name"] = _canonical_field(reader.fieldnames, "source_name")
                for row in reader:
                    _insert_rate(conn, source_file_id, row, fields)
        with engine.begin() as conn:
            _finish_import_run(conn, run_id, "completed", 1, 1 if is_new else 0)
    except Exception as exc:
        with engine.begin() as conn:
            _finish_import_run(conn, run_id, "failed", 1, 0, notes=str(exc))
        raise

    with engine.connect() as conn:
        rate_count = conn.execute(select(fx_rates.c.id)).fetchall()
    return {
        "run_id": run_id,
        "files_seen": 1,
        "files_new": 1 if is_new else 0,
        "fx_rates": len(rate_count),
        "input_path": str(input_path),
    }
