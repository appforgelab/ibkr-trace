from __future__ import annotations

import csv
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from sqlalchemy import Connection, Result, Select, func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from ibkr_trace.db import ensure_database
from ibkr_trace.schema import (
    cash_income_events,
    code_definitions,
    import_runs,
    instruments,
    raw_section_headers,
    raw_section_rows,
    source_files,
    trade_event_codes,
    trade_events,
)
from ibkr_trace.util import (
    canonical_decimal_text,
    clean_text,
    file_sha256,
    json_dumps,
    parse_broker_datetime,
    parse_iso_date,
    parse_option_symbol,
    row_mapping,
    split_codes,
    stable_hash,
    utc_now,
)


SUPPORTED_CASH_SECTIONS = {"Dividends", "Interest"}


def _insert_or_ignore(conn: Connection, table, values: dict, conflict_columns: list[str]) -> None:
    stmt = sqlite_insert(table).values(**values).on_conflict_do_nothing(index_elements=conflict_columns)
    conn.execute(stmt)


def _scalar(conn: Connection, stmt: Select) -> object:
    return conn.execute(stmt).scalar_one()


def _detect_statement_type(first_rows: list[list[str]]) -> str | None:
    for row in first_rows:
        if len(row) >= 4 and row[0] == "Statement" and row[2] == "Title":
            return row[3]
    return None


def _iter_csv_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    for child in sorted(path.rglob("*.csv")):
        if child.is_file():
            yield child


def _start_import_run(conn: Connection, importer: str, input_path: Path) -> int:
    result: Result = conn.execute(
        import_runs.insert().values(
            importer=importer,
            input_path=str(input_path),
            status="running",
            started_at=utc_now(),
            source_files_seen=0,
            source_files_new=0,
        )
    )
    return int(result.inserted_primary_key[0])


def _finish_import_run(
    conn: Connection,
    run_id: int,
    status: str,
    source_files_seen: int,
    source_files_new: int,
    notes: str | None = None,
) -> None:
    conn.execute(
        update(import_runs)
        .where(import_runs.c.id == run_id)
        .values(
            status=status,
            completed_at=utc_now(),
            source_files_seen=source_files_seen,
            source_files_new=source_files_new,
            notes=notes,
        )
    )


def _get_or_create_source_file(conn: Connection, importer: str, path: Path) -> tuple[int, bool]:
    sha256 = file_sha256(str(path))
    source_file_id = conn.execute(select(source_files.c.id).where(source_files.c.sha256 == sha256)).scalar_one_or_none()
    if source_file_id is not None:
        return int(source_file_id), False

    preview: list[list[str]] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        for _, row in zip(range(20), reader):
            preview.append(row)

    stmt = sqlite_insert(source_files).values(
        sha256=sha256,
        file_path=str(path),
        file_name=path.name,
        file_size_bytes=path.stat().st_size,
        importer=importer,
        detected_statement_type=_detect_statement_type(preview),
        created_at=utc_now(),
    )
    conn.execute(stmt)
    source_file_id = _scalar(conn, select(source_files.c.id).where(source_files.c.sha256 == sha256))
    return int(source_file_id), True


def _upsert_code_definition(conn: Connection, row: dict[str, str]) -> None:
    code = clean_text(row.get("Code"))
    if code is None:
        return
    stmt = sqlite_insert(code_definitions).values(
        code=code,
        meaning=clean_text(row.get("Meaning")),
        meaning_cont=clean_text(row.get("Meaning (Cont.)")),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[code_definitions.c.code],
        set_={
            "meaning": stmt.excluded.meaning,
            "meaning_cont": stmt.excluded.meaning_cont,
        },
    )
    conn.execute(stmt)


def _instrument_key(asset_category: str | None, symbol: str | None) -> str | None:
    if not asset_category or not symbol:
        return None
    return f"{asset_category}|{symbol}"


def _upsert_instrument(conn: Connection, row: dict[str, str]) -> int | None:
    asset_category = clean_text(row.get("Asset Category"))
    symbol = clean_text(row.get("Symbol"))
    instrument_key = _instrument_key(asset_category, symbol)
    if instrument_key is None:
        return None

    option_parts = parse_option_symbol(symbol)
    expiry = parse_iso_date(clean_text(row.get("Expiry")) or option_parts["expiry"])
    strike = canonical_decimal_text(clean_text(row.get("Strike")) or option_parts["strike"])
    right = clean_text(option_parts["right"])
    stmt = sqlite_insert(instruments).values(
        instrument_key=instrument_key,
        asset_category=asset_category,
        symbol=symbol,
        description=clean_text(row.get("Description")),
        conid=clean_text(row.get("Conid")),
        security_id=clean_text(row.get("Security ID")),
        underlying_symbol=clean_text(row.get("Underlying")) or clean_text(option_parts["underlying"]),
        listing_exchange=clean_text(row.get("Listing Exch")),
        multiplier_text=canonical_decimal_text(row.get("Multiplier")),
        instrument_type=clean_text(row.get("Type")),
        expiry_date=expiry,
        option_right=right,
        strike_text=strike,
        raw_code_text=clean_text(row.get("Code")),
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[instruments.c.instrument_key],
        set_={
            "description": stmt.excluded.description,
            "conid": stmt.excluded.conid,
            "security_id": stmt.excluded.security_id,
            "underlying_symbol": stmt.excluded.underlying_symbol,
            "listing_exchange": stmt.excluded.listing_exchange,
            "multiplier_text": stmt.excluded.multiplier_text,
            "instrument_type": stmt.excluded.instrument_type,
            "expiry_date": stmt.excluded.expiry_date,
            "option_right": stmt.excluded.option_right,
            "strike_text": stmt.excluded.strike_text,
            "raw_code_text": stmt.excluded.raw_code_text,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    conn.execute(stmt)
    return int(_scalar(conn, select(instruments.c.id).where(instruments.c.instrument_key == instrument_key)))


def _ensure_trade_instrument(conn: Connection, row: dict[str, str]) -> int | None:
    instrument_id = _upsert_instrument(
        conn,
        {
            "Asset Category": row.get("Asset Category", ""),
            "Symbol": row.get("Symbol", ""),
            "Description": row.get("Symbol", ""),
            "Underlying": parse_option_symbol(row.get("Symbol")).get("underlying") or row.get("Symbol"),
            "Multiplier": "1",
            "Type": row.get("Asset Category", ""),
        },
    )
    return instrument_id


def _normalize_trade(conn: Connection, source_file_id: int, row_index: int, row: dict[str, str], payload: list[str]) -> None:
    instrument_id = _ensure_trade_instrument(conn, row)
    if instrument_id is None:
        return

    asset_category = clean_text(row.get("Asset Category")) or ""
    symbol = clean_text(row.get("Symbol")) or ""
    timestamp_text = clean_text(row.get("Date/Time")) or ""
    timestamp = parse_broker_datetime(timestamp_text)
    values = {
        "data_discriminator": clean_text(row.get("DataDiscriminator")),
        "asset_category": asset_category,
        "currency": clean_text(row.get("Currency")),
        "symbol": symbol,
        "broker_timestamp_text": timestamp_text,
        "broker_timestamp": timestamp,
        "event_date": timestamp.date() if timestamp else None,
        "quantity_text": canonical_decimal_text(row.get("Quantity")) or "0",
        "trade_price_text": canonical_decimal_text(row.get("T. Price")),
        "close_price_text": canonical_decimal_text(row.get("C. Price")),
        "proceeds_text": canonical_decimal_text(row.get("Proceeds")),
        "comm_fee_text": canonical_decimal_text(row.get("Comm/Fee") or row.get("Comm in USD")),
        "basis_text": canonical_decimal_text(row.get("Basis")),
        "realized_pl_text": canonical_decimal_text(row.get("Realized P/L")),
        "realized_pl_percent_text": canonical_decimal_text(row.get("Realized P/L %")),
        "mtm_pl_text": canonical_decimal_text(row.get("MTM P/L") or row.get("MTM in USD")),
        "code_text": clean_text(row.get("Code")),
    }
    fingerprint = stable_hash(
        "trade",
        values["data_discriminator"],
        values["asset_category"],
        values["currency"],
        values["symbol"],
        values["broker_timestamp_text"],
        values["quantity_text"],
        values["trade_price_text"],
        values["close_price_text"],
        values["proceeds_text"],
        values["comm_fee_text"],
        values["basis_text"],
        values["realized_pl_text"],
        values["realized_pl_percent_text"],
        values["mtm_pl_text"],
        values["code_text"],
    )
    _insert_or_ignore(
        conn,
        trade_events,
        {
            "event_fingerprint": fingerprint,
            "source_file_id": source_file_id,
            "source_row_index": row_index,
            "instrument_id": instrument_id,
            **values,
            "raw_payload_json": json_dumps(payload),
            "created_at": utc_now(),
        },
        ["event_fingerprint"],
    )
    trade_event_id = int(_scalar(conn, select(trade_events.c.id).where(trade_events.c.event_fingerprint == fingerprint)))
    for code in split_codes(values["code_text"]):
        _insert_or_ignore(conn, trade_event_codes, {"trade_event_id": trade_event_id, "code": code}, ["trade_event_id", "code"])


def _normalize_cash_income(
    conn: Connection,
    section_name: str,
    source_file_id: int,
    row_index: int,
    row: dict[str, str],
    payload: list[str],
) -> None:
    currency = clean_text(row.get("Currency"))
    if currency is None or currency.startswith("Total") or len(currency) != 3:
        return
    event_date = parse_iso_date(row.get("Date"))
    description = clean_text(row.get("Description"))
    amount = canonical_decimal_text(row.get("Amount"))
    if event_date is None or description is None or amount is None:
        return
    fingerprint = stable_hash(section_name, currency, event_date.isoformat(), description, amount)
    _insert_or_ignore(
        conn,
        cash_income_events,
        {
            "event_fingerprint": fingerprint,
            "source_file_id": source_file_id,
            "source_row_index": row_index,
            "section_name": section_name,
            "currency": currency,
            "event_date": event_date,
            "description": description,
            "amount_text": amount,
            "raw_payload_json": json_dumps(payload),
            "created_at": utc_now(),
        },
        ["event_fingerprint"],
    )


def _stage_header(conn: Connection, source_file_id: int, row_index: int, section_name: str, header_signature: str, payload: list[str]) -> None:
    _insert_or_ignore(
        conn,
        raw_section_headers,
        {
            "source_file_id": source_file_id,
            "row_index": row_index,
            "section_name": section_name,
            "header_signature": header_signature,
            "header_json": json_dumps(payload),
        },
        ["source_file_id", "row_index"],
    )


def _stage_row(
    conn: Connection,
    source_file_id: int,
    row_index: int,
    section_name: str,
    row_kind: str,
    header_signature: str | None,
    payload: list[str],
) -> None:
    _insert_or_ignore(
        conn,
        raw_section_rows,
        {
            "source_file_id": source_file_id,
            "row_index": row_index,
            "section_name": section_name,
            "row_kind": row_kind,
            "header_signature": header_signature,
            "payload_json": json_dumps(payload),
        },
        ["source_file_id", "row_index"],
    )


def _process_ibkr_file(conn: Connection, source_file_id: int, path: Path) -> None:
    current_headers: dict[str, tuple[str, list[str]]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        for row_index, row in enumerate(reader, start=1):
            if not row:
                continue
            section_name = row[0]
            row_kind = row[1] if len(row) > 1 else ""
            payload = row[2:]
            header_signature: str | None = None

            if row_kind == "Header":
                header_signature = stable_hash(*payload)
                current_headers[section_name] = (header_signature, payload)
                _stage_header(conn, source_file_id, row_index, section_name, header_signature, payload)
            else:
                current = current_headers.get(section_name)
                if current is not None:
                    header_signature = current[0]

            _stage_row(conn, source_file_id, row_index, section_name, row_kind, header_signature, payload)

            if row_kind != "Data":
                continue
            current = current_headers.get(section_name)
            if current is None:
                continue
            mapped = row_mapping(current[1], payload)

            if section_name == "Codes":
                _upsert_code_definition(conn, mapped)
            elif section_name == "Financial Instrument Information":
                _upsert_instrument(conn, mapped)
            elif section_name == "Trades":
                _normalize_trade(conn, source_file_id, row_index, mapped, payload)
            elif section_name in SUPPORTED_CASH_SECTIONS:
                _normalize_cash_income(conn, section_name, source_file_id, row_index, mapped, payload)


def import_ibkr_activity(engine: Engine, path: str) -> dict[str, int | str]:
    ensure_database(engine)
    input_path = Path(path).expanduser().resolve()
    files = list(_iter_csv_files(input_path))
    if not files:
        raise FileNotFoundError(f"No CSV files found at {input_path}")

    with engine.begin() as conn:
        run_id = _start_import_run(conn, "ibkr", input_path)

    seen = 0
    created = 0
    try:
        for file_path in files:
            with engine.begin() as conn:
                source_file_id, is_new = _get_or_create_source_file(conn, "ibkr", file_path)
                seen += 1
                created += 1 if is_new else 0
                _process_ibkr_file(conn, source_file_id, file_path)
        with engine.begin() as conn:
            _finish_import_run(conn, run_id, "completed", seen, created)
    except Exception as exc:
        with engine.begin() as conn:
            _finish_import_run(conn, run_id, "failed", seen, created, notes=str(exc))
        raise

    with engine.connect() as conn:
        trade_count = conn.execute(select(func.count()).select_from(trade_events)).scalar_one()
        income_count = conn.execute(select(func.count()).select_from(cash_income_events)).scalar_one()

    return {
        "run_id": run_id,
        "files_seen": seen,
        "files_new": created,
        "trade_events": int(trade_count),
        "cash_income_events": int(income_count),
        "input_path": str(input_path),
    }
