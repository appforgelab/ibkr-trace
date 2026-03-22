"""initial schema"""

from alembic import op
import sqlalchemy as sa


revision = "20260321_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("importer", sa.String(length=32), nullable=False),
        sa.Column("input_path", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("source_files_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_files_new", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_table(
        "source_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("importer", sa.String(length=32), nullable=False),
        sa.Column("detected_statement_type", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("sha256"),
    )
    op.create_table(
        "raw_section_headers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_file_id", sa.Integer(), sa.ForeignKey("source_files.id"), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("section_name", sa.Text(), nullable=False),
        sa.Column("header_signature", sa.String(length=64), nullable=False),
        sa.Column("header_json", sa.Text(), nullable=False),
        sa.UniqueConstraint("source_file_id", "row_index"),
    )
    op.create_table(
        "raw_section_rows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_file_id", sa.Integer(), sa.ForeignKey("source_files.id"), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("section_name", sa.Text(), nullable=False),
        sa.Column("row_kind", sa.Text(), nullable=False),
        sa.Column("header_signature", sa.String(length=64), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.UniqueConstraint("source_file_id", "row_index"),
    )
    op.create_table(
        "code_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("meaning", sa.Text(), nullable=True),
        sa.Column("meaning_cont", sa.Text(), nullable=True),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_key", sa.String(length=255), nullable=False),
        sa.Column("asset_category", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("conid", sa.Text(), nullable=True),
        sa.Column("security_id", sa.Text(), nullable=True),
        sa.Column("underlying_symbol", sa.Text(), nullable=True),
        sa.Column("listing_exchange", sa.Text(), nullable=True),
        sa.Column("multiplier_text", sa.Text(), nullable=True),
        sa.Column("instrument_type", sa.Text(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("option_right", sa.String(length=1), nullable=True),
        sa.Column("strike_text", sa.Text(), nullable=True),
        sa.Column("raw_code_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("instrument_key"),
    )
    op.create_table(
        "trade_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_file_id", sa.Integer(), sa.ForeignKey("source_files.id"), nullable=False),
        sa.Column("source_row_index", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("data_discriminator", sa.Text(), nullable=True),
        sa.Column("asset_category", sa.Text(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("broker_timestamp_text", sa.Text(), nullable=False),
        sa.Column("broker_timestamp", sa.DateTime(), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("quantity_text", sa.Text(), nullable=False),
        sa.Column("trade_price_text", sa.Text(), nullable=True),
        sa.Column("close_price_text", sa.Text(), nullable=True),
        sa.Column("proceeds_text", sa.Text(), nullable=True),
        sa.Column("comm_fee_text", sa.Text(), nullable=True),
        sa.Column("basis_text", sa.Text(), nullable=True),
        sa.Column("realized_pl_text", sa.Text(), nullable=True),
        sa.Column("realized_pl_percent_text", sa.Text(), nullable=True),
        sa.Column("mtm_pl_text", sa.Text(), nullable=True),
        sa.Column("code_text", sa.Text(), nullable=True),
        sa.Column("raw_payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("event_fingerprint"),
        sa.UniqueConstraint("source_file_id", "source_row_index"),
    )
    op.create_table(
        "trade_event_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trade_event_id", sa.Integer(), sa.ForeignKey("trade_events.id"), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("trade_event_id", "code"),
    )
    op.create_table(
        "cash_income_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_file_id", sa.Integer(), sa.ForeignKey("source_files.id"), nullable=False),
        sa.Column("source_row_index", sa.Integer(), nullable=False),
        sa.Column("section_name", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount_text", sa.Text(), nullable=False),
        sa.Column("raw_payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("event_fingerprint"),
        sa.UniqueConstraint("source_file_id", "source_row_index"),
    )
    op.create_table(
        "trace_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("symbol_filter", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_table(
        "trace_edges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trace_run_id", sa.Integer(), sa.ForeignKey("trace_runs.id"), nullable=False),
        sa.Column("reducing_trade_event_id", sa.Integer(), sa.ForeignKey("trade_events.id"), nullable=False),
        sa.Column("opening_trade_event_id", sa.Integer(), sa.ForeignKey("trade_events.id"), nullable=False),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("match_sequence", sa.Integer(), nullable=False),
        sa.Column("matched_quantity_text", sa.Text(), nullable=False),
        sa.Column("reducing_position_side", sa.String(length=16), nullable=False),
        sa.Column("opening_position_side", sa.String(length=16), nullable=False),
        sa.Column("opening_remaining_after_text", sa.Text(), nullable=True),
        sa.UniqueConstraint("trace_run_id", "reducing_trade_event_id", "match_sequence"),
    )
    op.create_table(
        "fx_rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_file_id", sa.Integer(), sa.ForeignKey("source_files.id"), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("quote_currency", sa.String(length=3), nullable=False),
        sa.Column("rate_text", sa.Text(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("rate_date", "base_currency", "quote_currency"),
    )
    op.create_index("ix_trade_events_event_date", "trade_events", ["event_date"])
    op.create_index("ix_trade_events_symbol", "trade_events", ["symbol"])
    op.create_index("ix_cash_income_events_event_date", "cash_income_events", ["event_date"])
    op.create_index("ix_fx_rates_rate_date", "fx_rates", ["rate_date"])


def downgrade() -> None:
    op.drop_index("ix_fx_rates_rate_date", table_name="fx_rates")
    op.drop_index("ix_cash_income_events_event_date", table_name="cash_income_events")
    op.drop_index("ix_trade_events_symbol", table_name="trade_events")
    op.drop_index("ix_trade_events_event_date", table_name="trade_events")
    op.drop_table("fx_rates")
    op.drop_table("trace_edges")
    op.drop_table("trace_runs")
    op.drop_table("cash_income_events")
    op.drop_table("trade_event_codes")
    op.drop_table("trade_events")
    op.drop_table("instruments")
    op.drop_table("code_definitions")
    op.drop_table("raw_section_rows")
    op.drop_table("raw_section_headers")
    op.drop_table("source_files")
    op.drop_table("import_runs")
