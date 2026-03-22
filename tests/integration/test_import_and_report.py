from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from sqlalchemy import func, select

from ibkr_trace.import_fx import import_fx_rates
from ibkr_trace.import_ibkr import import_ibkr_activity
from ibkr_trace.reporting import write_symbol_report, write_year_reports
from ibkr_trace.schema import cash_income_events, fx_rates, raw_section_headers, trade_event_codes, trade_events


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


def test_fx_import_is_idempotent(engine, fixture_dir: Path) -> None:
    fx_file = fixture_dir / "fx_daily.csv"
    import_fx_rates(engine, str(fx_file))
    import_fx_rates(engine, str(fx_file))
    assert _row_count(engine, fx_rates) == 3
