from __future__ import annotations

import csv
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import and_, select, update
from sqlalchemy.engine import Engine

from ibkr_trace.config import DEFAULT_REPORTS_DIR, ensure_runtime_dirs
from ibkr_trace.db import ensure_database
from ibkr_trace.schema import instruments, trace_edges, trace_runs, trade_events
from ibkr_trace.util import canonical_decimal_text, parse_decimal, split_codes, utc_now


@dataclass
class TradeRecord:
    id: int
    instrument_id: int
    symbol: str
    event_date: date | None
    broker_timestamp: datetime | None
    broker_timestamp_text: str
    quantity: Decimal
    code_text: str | None
    asset_category: str


@dataclass
class OpenLot:
    trade_id: int
    remaining_quantity: Decimal
    event_date: date | None
    broker_timestamp_text: str
    codes: str | None


def _classify_trade(trade: TradeRecord) -> tuple[str, str] | None:
    codes = set(split_codes(trade.code_text))
    if "O" in codes and "C" not in codes:
        if trade.quantity > 0:
            return ("open", "long")
        if trade.quantity < 0:
            return ("open", "short")
    if "C" in codes and "O" not in codes:
        if trade.quantity < 0:
            return ("close", "long")
        if trade.quantity > 0:
            return ("close", "short")
    return None


def write_trace_report(
    engine: Engine,
    start: date,
    end: date,
    symbol: str | None = None,
    output_dir: Path | None = None,
) -> dict[str, str | int]:
    ensure_database(engine)
    ensure_runtime_dirs()
    output_root = output_dir or DEFAULT_REPORTS_DIR
    symbol_value = symbol.strip() if symbol else None
    suffix = f"{start.isoformat()}_{end.isoformat()}"

    with engine.begin() as conn:
        trace_run_id = conn.execute(
            trace_runs.insert().values(
                started_at=utc_now(),
                start_date=start,
                end_date=end,
                symbol_filter=symbol_value,
            )
        ).inserted_primary_key[0]

    records: list[TradeRecord] = []
    with engine.connect() as conn:
        stmt = (
            select(
                trade_events.c.id,
                trade_events.c.instrument_id,
                trade_events.c.symbol,
                trade_events.c.event_date,
                trade_events.c.broker_timestamp,
                trade_events.c.broker_timestamp_text,
                trade_events.c.quantity_text,
                trade_events.c.code_text,
                trade_events.c.asset_category,
            )
            .where(trade_events.c.event_date <= end)
            .order_by(trade_events.c.broker_timestamp, trade_events.c.id)
        )
        if symbol_value:
            stmt = stmt.where(trade_events.c.symbol == symbol_value)
        for row in conn.execute(stmt).mappings():
            quantity = parse_decimal(row["quantity_text"])
            if quantity is None or quantity == 0:
                continue
            records.append(
                TradeRecord(
                    id=row["id"],
                    instrument_id=row["instrument_id"],
                    symbol=row["symbol"],
                    event_date=row["event_date"],
                    broker_timestamp=row["broker_timestamp"],
                    broker_timestamp_text=row["broker_timestamp_text"],
                    quantity=quantity,
                    code_text=row["code_text"],
                    asset_category=row["asset_category"],
                )
            )

    long_lots: dict[int, deque[OpenLot]] = defaultdict(deque)
    short_lots: dict[int, deque[OpenLot]] = defaultdict(deque)
    edges: list[dict[str, object]] = []
    unmatched_reductions = 0

    for trade in records:
        classification = _classify_trade(trade)
        if classification is None:
            continue
        action, side = classification
        if action == "open":
            lot = OpenLot(
                trade_id=trade.id,
                remaining_quantity=abs(trade.quantity),
                event_date=trade.event_date,
                broker_timestamp_text=trade.broker_timestamp_text,
                codes=trade.code_text,
            )
            target = long_lots if side == "long" else short_lots
            target[trade.instrument_id].append(lot)
            continue

        reduce_within_window = trade.event_date is not None and start <= trade.event_date <= end
        if not reduce_within_window:
            target = long_lots if side == "long" else short_lots
            needed = abs(trade.quantity)
            while needed > 0 and target[trade.instrument_id]:
                lot = target[trade.instrument_id][0]
                matched = min(needed, lot.remaining_quantity)
                lot.remaining_quantity -= matched
                needed -= matched
                if lot.remaining_quantity == 0:
                    target[trade.instrument_id].popleft()
            continue

        target = long_lots if side == "long" else short_lots
        needed = abs(trade.quantity)
        sequence = 0
        while needed > 0 and target[trade.instrument_id]:
            lot = target[trade.instrument_id][0]
            matched = min(needed, lot.remaining_quantity)
            lot.remaining_quantity -= matched
            needed -= matched
            sequence += 1
            edges.append(
                {
                    "trace_run_id": trace_run_id,
                    "reducing_trade_event_id": trade.id,
                    "opening_trade_event_id": lot.trade_id,
                    "instrument_id": trade.instrument_id,
                    "match_sequence": sequence,
                    "matched_quantity_text": canonical_decimal_text(str(matched)) or "0",
                    "reducing_position_side": side,
                    "opening_position_side": side,
                    "opening_remaining_after_text": canonical_decimal_text(str(lot.remaining_quantity)) or "0",
                }
            )
            if lot.remaining_quantity == 0:
                target[trade.instrument_id].popleft()
        if needed > 0:
            unmatched_reductions += 1

    with engine.begin() as conn:
        if edges:
            conn.execute(trace_edges.insert(), edges)
        conn.execute(
            update(trace_runs)
            .where(trace_runs.c.id == trace_run_id)
            .values(completed_at=utc_now(), notes=f"unmatched_reductions={unmatched_reductions}")
        )

    output_path = output_root / f"trace_edges_{suffix}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with engine.connect() as conn:
        reducing_event = trade_events.alias("reducing_event")
        opening_event = trade_events.alias("opening_event")
        stmt = (
            select(
                trace_edges.c.match_sequence,
                trace_edges.c.matched_quantity_text,
                trace_edges.c.reducing_position_side,
                trace_edges.c.opening_position_side,
                trace_edges.c.opening_remaining_after_text,
                reducing_event.c.id.label("reducing_trade_id"),
                reducing_event.c.symbol.label("reducing_symbol"),
                reducing_event.c.broker_timestamp_text.label("reducing_timestamp"),
                reducing_event.c.quantity_text.label("reducing_quantity"),
                reducing_event.c.code_text.label("reducing_codes"),
                opening_event.c.id.label("opening_trade_id"),
                opening_event.c.broker_timestamp_text.label("opening_timestamp"),
                opening_event.c.quantity_text.label("opening_quantity"),
                opening_event.c.code_text.label("opening_codes"),
                instruments.c.underlying_symbol,
                instruments.c.expiry_date,
                instruments.c.option_right,
                instruments.c.strike_text,
            )
            .select_from(
                trace_edges.join(reducing_event, trace_edges.c.reducing_trade_event_id == reducing_event.c.id)
                .join(opening_event, trace_edges.c.opening_trade_event_id == opening_event.c.id)
                .join(instruments, trace_edges.c.instrument_id == instruments.c.id)
            )
            .where(trace_edges.c.trace_run_id == trace_run_id)
            .order_by(trace_edges.c.reducing_trade_event_id, trace_edges.c.match_sequence)
        )
        reducing_rows = [dict(row) for row in conn.execute(stmt).mappings()]

    if not reducing_rows:
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "match_sequence",
                    "matched_quantity_text",
                    "reducing_position_side",
                    "opening_position_side",
                    "opening_remaining_after_text",
                    "reducing_trade_id",
                    "reducing_symbol",
                    "reducing_timestamp",
                    "reducing_quantity",
                    "reducing_codes",
                    "opening_trade_id",
                    "opening_timestamp",
                    "opening_quantity",
                    "opening_codes",
                    "underlying_symbol",
                    "expiry_date",
                    "option_right",
                    "strike_text",
                ],
            )
            writer.writeheader()
    else:
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(reducing_rows[0].keys()))
            writer.writeheader()
            writer.writerows(reducing_rows)

    return {
        "trace_run_id": int(trace_run_id),
        "trace_edges": len(edges),
        "unmatched_reductions": unmatched_reductions,
        "output_path": str(output_path),
    }
