from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, select
from typer.testing import CliRunner

from ibkr_trace.cli import app
from ibkr_trace.import_fx import import_fx_rates
from ibkr_trace.import_ibkr import import_ibkr_activity
from ibkr_trace.reporting import _safe_report_token, write_ledger_report, write_symbol_report, write_year_reports
from ibkr_trace.schema import cash_income_events, fx_rates, instruments, raw_section_headers, trade_event_codes, trade_events


def _row_count(engine, table) -> int:
    with engine.connect() as conn:
        return int(conn.execute(select(func.count()).select_from(table)).scalar_one())


def test_import_same_file_is_idempotent(engine, fixture_dir: Path) -> None:
    file_path = fixture_dir / "ib_activity_part1.csv"
    summary_one = import_ibkr_activity(engine, str(file_path))
    summary_two = import_ibkr_activity(engine, str(file_path))

    assert summary_one["files_seen"] == 1
    assert summary_two["files_new"] == 0
    assert _row_count(engine, trade_events) == 6
    assert _row_count(engine, cash_income_events) == 2


def test_import_later_ytd_only_adds_new_rows(engine, fixture_dir: Path) -> None:
    import_ibkr_activity(engine, str(fixture_dir / "ib_activity_part1.csv"))
    import_ibkr_activity(engine, str(fixture_dir / "ib_activity_part2_ytd.csv"))

    assert _row_count(engine, trade_events) == 8
    assert _row_count(engine, cash_income_events) == 4


def test_repeated_section_headers_are_staged(engine, fixture_dir: Path) -> None:
    import_ibkr_activity(engine, str(fixture_dir / "ib_activity_part1.csv"))
    with engine.connect() as conn:
        count = conn.execute(
            select(func.count())
            .select_from(raw_section_headers)
            .where(raw_section_headers.c.section_name == "Trades")
        ).scalar_one()
    assert int(count) == 2


def test_codes_survive_normalization(engine, fixture_dir: Path) -> None:
    import_ibkr_activity(engine, str(fixture_dir / "ib_activity_part2_ytd.csv"))
    with engine.connect() as conn:
        codes = {
            row[0]
            for row in conn.execute(select(trade_event_codes.c.code).distinct()).all()
        }
    assert {"O", "C", "Ep"} <= codes


def test_year_report_filters_by_date(engine, fixture_dir: Path, tmp_path: Path) -> None:
    import_ibkr_activity(engine, str(fixture_dir / "ib_activity_part2_ytd.csv"))
    output_dir = tmp_path / "reports"
    outputs = write_year_reports(engine, start=date(2025, 4, 1), end=date(2025, 4, 30), output_dir=output_dir)

    with open(outputs["trades"], newline="", encoding="utf-8") as handle:
        trade_rows = list(csv.DictReader(handle))
    with open(outputs["dividends"], newline="", encoding="utf-8") as handle:
        dividend_rows = list(csv.DictReader(handle))
    with open(outputs["interest"], newline="", encoding="utf-8") as handle:
        interest_rows = list(csv.DictReader(handle))

    assert [row["broker_timestamp_text"] for row in trade_rows] == ["2025-04-01, 09:45:00"]
    assert [row["event_date"] for row in dividend_rows] == ["2025-04-20"]
    assert [row["event_date"] for row in interest_rows] == ["2025-04-30"]


def test_symbol_report_groups_symbols_in_range(engine, fixture_dir: Path, tmp_path: Path) -> None:
    import_ibkr_activity(engine, str(fixture_dir / "ib_activity_part2_ytd.csv"))
    output_dir = tmp_path / "reports"
    output = write_symbol_report(engine, start=date(2025, 1, 1), end=date(2025, 3, 31), output_dir=output_dir)

    with open(output, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert rows == [
        {"asset_category": "Equity and Index Options", "symbol": "ABC 20JUN25 10 C", "trade_count": "3"},
        {"asset_category": "Stocks", "symbol": "ABC", "trade_count": "3"},
    ]


def test_symbol_report_respects_narrower_window(engine, fixture_dir: Path, tmp_path: Path) -> None:
    import_ibkr_activity(engine, str(fixture_dir / "ib_activity_part2_ytd.csv"))
    output_dir = tmp_path / "reports"
    output = write_symbol_report(engine, start=date(2025, 4, 1), end=date(2025, 4, 30), output_dir=output_dir)

    with open(output, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert rows == [
        {"asset_category": "Equity and Index Options", "symbol": "ABC 20JUN25 10 C", "trade_count": "1"},
    ]


def test_ledger_report_includes_all_trades_through_end_with_running_totals(engine, fixture_dir: Path, tmp_path: Path) -> None:
    import_ibkr_activity(engine, str(fixture_dir / "ib_activity_part2_ytd.csv"))
    output_dir = tmp_path / "reports"
    output = write_ledger_report(engine, symbol="ABC", end=date(2025, 3, 31), output_dir=output_dir)

    assert Path(output).name == "ledger_ABC_2025-03-31.csv"

    with open(output, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert [row["broker_timestamp_text"] for row in rows] == [
        "2025-01-10, 09:30:00",
        "2025-02-10, 09:30:00",
        "2025-03-15, 09:30:00",
    ]
    assert [row["direction"] for row in rows] == ["BUY", "BUY", "SELL"]
    assert [row["quantity_text"] for row in rows] == ["100", "50", "-120"]
    assert [row["running_quantity_text"] for row in rows] == ["100", "150", "30"]


def test_ledger_report_rejects_blank_symbol(engine, fixture_dir: Path, tmp_path: Path) -> None:
    import_ibkr_activity(engine, str(fixture_dir / "ib_activity_part2_ytd.csv"))

    with pytest.raises(ValueError, match="Symbol must not be empty or whitespace."):
        write_ledger_report(engine, symbol="   ", end=date(2025, 3, 31), output_dir=tmp_path / "reports")


def test_ledger_report_writes_header_only_for_unknown_symbol(engine, fixture_dir: Path, tmp_path: Path) -> None:
    import_ibkr_activity(engine, str(fixture_dir / "ib_activity_part2_ytd.csv"))
    output = write_ledger_report(engine, symbol="MISSING", end=date(2025, 3, 31), output_dir=tmp_path / "reports")

    assert Path(output).name == "ledger_MISSING_2025-03-31.csv"

    with open(output, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert rows == []


def test_ledger_report_rejects_ambiguous_symbol_across_multiple_instruments(engine, fixture_dir: Path, tmp_path: Path) -> None:
    import_ibkr_activity(engine, str(fixture_dir / "ib_activity_part2_ytd.csv"))

    with engine.begin() as conn:
        source_file_id = conn.execute(select(trade_events.c.source_file_id).limit(1)).scalar_one()
        instrument_id = conn.execute(
            instruments.insert().values(
                instrument_key="ambiguous:ABC:option",
                asset_category="Equity and Index Options",
                symbol="ABC",
                description="Synthetic ambiguous ABC option",
                underlying_symbol="ABC",
                instrument_type="CALL",
                expiry_date=date(2025, 12, 19),
                option_right="C",
                strike_text="10",
                created_at=datetime(2025, 3, 20, 10, 0, 0),
                updated_at=datetime(2025, 3, 20, 10, 0, 0),
            )
        ).inserted_primary_key[0]
        conn.execute(
            trade_events.insert().values(
                event_fingerprint="ambiguous-abc-trade",
                source_file_id=source_file_id,
                source_row_index=9999,
                instrument_id=instrument_id,
                data_discriminator="Order",
                asset_category="Equity and Index Options",
                currency="USD",
                symbol="ABC",
                broker_timestamp_text="2025-03-20, 10:00:00",
                broker_timestamp=datetime(2025, 3, 20, 10, 0, 0),
                event_date=date(2025, 3, 20),
                quantity_text="1",
                trade_price_text="1",
                proceeds_text="-100",
                comm_fee_text="-1",
                basis_text="101",
                realized_pl_text="0",
                raw_payload_json="{}",
                created_at=datetime(2025, 3, 20, 10, 0, 0),
            )
        )

    with pytest.raises(ValueError, match="matched multiple instruments"):
        write_ledger_report(engine, symbol="ABC", end=date(2025, 3, 31), output_dir=tmp_path / "reports")


def test_report_ledger_cli_uses_exact_symbol_and_stable_filename(fixture_dir: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "ibkr.sqlite"
    output_dir = tmp_path / "reports"

    import_result = runner.invoke(
        app,
        [
            "import",
            "ibkr",
            "--path",
            str(fixture_dir / "ib_activity_part2_ytd.csv"),
            "--db",
            str(db_path),
        ],
    )
    assert import_result.exit_code == 0

    result = runner.invoke(
        app,
        [
            "report",
            "ledger",
            "--symbol",
            "ABC 20JUN25 10 C",
            "--end",
            "2025-04-30",
            "--db",
            str(db_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    output = output_dir / "ledger_ABC_20JUN25_10_C_2025-04-30.csv"
    assert f"ledger: {output}" in result.stdout

    with output.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert [row["symbol"] for row in rows] == ["ABC 20JUN25 10 C"] * 4
    assert [row["quantity_text"] for row in rows] == ["-1", "-1", "1", "1"]
    assert [row["running_quantity_text"] for row in rows] == ["-1", "-2", "-1", "0"]
    assert rows[-1]["code_text"] == "C;Ep"


def test_report_year_cli_does_not_accept_symbol_option(tmp_path: Path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "ibkr.sqlite"

    result = runner.invoke(
        app,
        [
            "report",
            "year",
            "--start",
            "2025-01-01",
            "--end",
            "2025-12-31",
            "--db",
            str(db_path),
            "--symbol",
            "ABC",
        ],
    )

    assert result.exit_code != 0
    assert "No such option: --symbol" in result.output


def test_safe_report_token_defaults_for_empty_value() -> None:
    assert _safe_report_token("") == "report"


def test_fx_import_is_idempotent(engine, fixture_dir: Path) -> None:
    fx_file = fixture_dir / "fx_daily.csv"
    import_fx_rates(engine, str(fx_file))
    import_fx_rates(engine, str(fx_file))
    assert _row_count(engine, fx_rates) == 3
