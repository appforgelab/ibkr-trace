from __future__ import annotations

from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, MetaData, String, Table, Text, UniqueConstraint


metadata = MetaData()

import_runs = Table(
    "import_runs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("importer", String(32), nullable=False),
    Column("input_path", Text, nullable=False),
    Column("status", String(32), nullable=False),
    Column("started_at", DateTime, nullable=False),
    Column("completed_at", DateTime),
    Column("source_files_seen", Integer, nullable=False, default=0),
    Column("source_files_new", Integer, nullable=False, default=0),
    Column("notes", Text),
)

source_files = Table(
    "source_files",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("sha256", String(64), nullable=False, unique=True),
    Column("file_path", Text, nullable=False),
    Column("file_name", Text, nullable=False),
    Column("file_size_bytes", Integer, nullable=False),
    Column("importer", String(32), nullable=False),
    Column("detected_statement_type", Text),
    Column("created_at", DateTime, nullable=False),
)

raw_section_headers = Table(
    "raw_section_headers",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("source_file_id", Integer, ForeignKey("source_files.id"), nullable=False),
    Column("row_index", Integer, nullable=False),
    Column("section_name", Text, nullable=False),
    Column("header_signature", String(64), nullable=False),
    Column("header_json", Text, nullable=False),
    UniqueConstraint("source_file_id", "row_index"),
)

raw_section_rows = Table(
    "raw_section_rows",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("source_file_id", Integer, ForeignKey("source_files.id"), nullable=False),
    Column("row_index", Integer, nullable=False),
    Column("section_name", Text, nullable=False),
    Column("row_kind", Text, nullable=False),
    Column("header_signature", String(64)),
    Column("payload_json", Text, nullable=False),
    UniqueConstraint("source_file_id", "row_index"),
)

code_definitions = Table(
    "code_definitions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("code", String(32), nullable=False, unique=True),
    Column("meaning", Text),
    Column("meaning_cont", Text),
)

instruments = Table(
    "instruments",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("instrument_key", String(255), nullable=False, unique=True),
    Column("asset_category", Text, nullable=False),
    Column("symbol", Text, nullable=False),
    Column("description", Text),
    Column("conid", Text),
    Column("security_id", Text),
    Column("underlying_symbol", Text),
    Column("listing_exchange", Text),
    Column("multiplier_text", Text),
    Column("instrument_type", Text),
    Column("expiry_date", Date),
    Column("option_right", String(1)),
    Column("strike_text", Text),
    Column("raw_code_text", Text),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)

trade_events = Table(
    "trade_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("event_fingerprint", String(64), nullable=False, unique=True),
    Column("source_file_id", Integer, ForeignKey("source_files.id"), nullable=False),
    Column("source_row_index", Integer, nullable=False),
    Column("instrument_id", Integer, ForeignKey("instruments.id"), nullable=False),
    Column("data_discriminator", Text),
    Column("asset_category", Text, nullable=False),
    Column("currency", Text),
    Column("symbol", Text, nullable=False),
    Column("broker_timestamp_text", Text, nullable=False),
    Column("broker_timestamp", DateTime),
    Column("event_date", Date),
    Column("quantity_text", Text, nullable=False),
    Column("trade_price_text", Text),
    Column("close_price_text", Text),
    Column("proceeds_text", Text),
    Column("comm_fee_text", Text),
    Column("basis_text", Text),
    Column("realized_pl_text", Text),
    Column("realized_pl_percent_text", Text),
    Column("mtm_pl_text", Text),
    Column("code_text", Text),
    Column("raw_payload_json", Text, nullable=False),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("source_file_id", "source_row_index"),
)
Index("ix_trade_events_event_date", trade_events.c.event_date)
Index("ix_trade_events_symbol", trade_events.c.symbol)

trade_event_codes = Table(
    "trade_event_codes",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("trade_event_id", Integer, ForeignKey("trade_events.id"), nullable=False),
    Column("code", String(32), nullable=False),
    UniqueConstraint("trade_event_id", "code"),
)

cash_income_events = Table(
    "cash_income_events",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("event_fingerprint", String(64), nullable=False, unique=True),
    Column("source_file_id", Integer, ForeignKey("source_files.id"), nullable=False),
    Column("source_row_index", Integer, nullable=False),
    Column("section_name", String(32), nullable=False),
    Column("currency", Text, nullable=False),
    Column("event_date", Date, nullable=False),
    Column("description", Text, nullable=False),
    Column("amount_text", Text, nullable=False),
    Column("raw_payload_json", Text, nullable=False),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("source_file_id", "source_row_index"),
)
Index("ix_cash_income_events_event_date", cash_income_events.c.event_date)

trace_runs = Table(
    "trace_runs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("started_at", DateTime, nullable=False),
    Column("completed_at", DateTime),
    Column("start_date", Date, nullable=False),
    Column("end_date", Date, nullable=False),
    Column("symbol_filter", Text),
    Column("notes", Text),
)

trace_edges = Table(
    "trace_edges",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("trace_run_id", Integer, ForeignKey("trace_runs.id"), nullable=False),
    Column("reducing_trade_event_id", Integer, ForeignKey("trade_events.id"), nullable=False),
    Column("opening_trade_event_id", Integer, ForeignKey("trade_events.id"), nullable=False),
    Column("instrument_id", Integer, ForeignKey("instruments.id"), nullable=False),
    Column("match_sequence", Integer, nullable=False),
    Column("matched_quantity_text", Text, nullable=False),
    Column("reducing_position_side", String(16), nullable=False),
    Column("opening_position_side", String(16), nullable=False),
    Column("opening_remaining_after_text", Text),
    UniqueConstraint("trace_run_id", "reducing_trade_event_id", "match_sequence"),
)

fx_rates = Table(
    "fx_rates",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("source_file_id", Integer, ForeignKey("source_files.id"), nullable=False),
    Column("rate_date", Date, nullable=False),
    Column("base_currency", String(3), nullable=False),
    Column("quote_currency", String(3), nullable=False),
    Column("rate_text", Text, nullable=False),
    Column("source_name", Text),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("rate_date", "base_currency", "quote_currency"),
)
Index("ix_fx_rates_rate_date", fx_rates.c.rate_date)
