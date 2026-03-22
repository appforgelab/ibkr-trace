from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from ibkr_trace.import_ibkr import import_ibkr_activity
from ibkr_trace.tracing import write_trace_report


def test_fifo_trace_for_stock_and_short_option(engine, fixture_dir: Path, tmp_path: Path) -> None:
    import_ibkr_activity(engine, str(fixture_dir / "ib_activity_part2_ytd.csv"))
    output_dir = tmp_path / "reports"
    summary = write_trace_report(engine, start=date(2025, 3, 1), end=date(2025, 4, 30), output_dir=output_dir)

    assert summary["trace_edges"] == 4
    with open(summary["output_path"], newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    stock_rows = [row for row in rows if row["reducing_symbol"] == "ABC"]
    option_rows = [row for row in rows if row["reducing_symbol"] == "ABC 20JUN25 10 C"]

    assert [row["matched_quantity_text"] for row in stock_rows] == ["100", "20"]
    assert [row["opening_timestamp"] for row in stock_rows] == ["2025-01-10, 09:30:00", "2025-02-10, 09:30:00"]
    assert [row["opening_timestamp"] for row in option_rows] == ["2025-01-05, 09:45:00", "2025-01-10, 09:45:00"]
