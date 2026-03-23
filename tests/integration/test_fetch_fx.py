from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ibkr_trace.cli import app
from ibkr_trace.fetch_fx import (
    _parse_boe_date,
    fetch_boe_rates,
    write_fx_csv,
)

# Sample BoE CSV response (UTF-8 BOM prefix stripped by decode("utf-8-sig")).
SAMPLE_BOE_CSV = (
    "DATE, XUDLUSS\n"
    "02 Jan 2025, 1.2530\n"
    "03 Jan 2025, 1.2410\n"
    "06 Jan 2025, 1.2450\n"
)


class _FakeResponse:
    """Minimal file-like object returned by urlopen mock."""

    def __init__(self, data: str) -> None:
        self._data = data.encode("utf-8-sig")

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# --- unit-level helpers ---


def test_parse_boe_date_valid() -> None:
    assert _parse_boe_date("02 Jan 2025") == date(2025, 1, 2)


def test_parse_boe_date_empty() -> None:
    assert _parse_boe_date("") is None
    assert _parse_boe_date("   ") is None


def test_parse_boe_date_invalid() -> None:
    assert _parse_boe_date("not-a-date") is None


# --- fetch_boe_rates with mocked HTTP ---


def test_fetch_boe_rates_parses_csv() -> None:
    with patch("ibkr_trace.fetch_fx.urllib.request.urlopen", return_value=_FakeResponse(SAMPLE_BOE_CSV)):
        rows = fetch_boe_rates(date(2025, 1, 1), date(2025, 1, 6))

    assert len(rows) == 3
    assert rows[0] == {
        "date": "2025-01-02",
        "base_currency": "GBP",
        "quote_currency": "USD",
        "rate": "1.2530",
        "source_name": "bank_of_england",
    }


def test_fetch_boe_rates_rejects_bad_range() -> None:
    with pytest.raises(ValueError, match="from_date.*must be <= to_date"):
        fetch_boe_rates(date(2025, 3, 1), date(2025, 1, 1))


def test_fetch_boe_rates_skips_blank_rows() -> None:
    csv_with_blanks = "DATE, XUDLUSS\n02 Jan 2025, 1.25\n, \n03 Jan 2025, 1.24\n"
    with patch("ibkr_trace.fetch_fx.urllib.request.urlopen", return_value=_FakeResponse(csv_with_blanks)):
        rows = fetch_boe_rates(date(2025, 1, 1), date(2025, 1, 6))
    assert len(rows) == 2


# --- write_fx_csv ---


def test_write_fx_csv_creates_file(tmp_path: Path) -> None:
    rows = [
        {"date": "2025-01-02", "base_currency": "GBP", "quote_currency": "USD", "rate": "1.25", "source_name": "test"},
        {"date": "2025-01-03", "base_currency": "GBP", "quote_currency": "USD", "rate": "1.24", "source_name": "test"},
    ]
    out = tmp_path / "fx" / "out.csv"
    result = write_fx_csv(rows, out)
    assert result.exists()

    with out.open(newline="", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    assert len(reader) == 2
    assert reader[0]["rate"] == "1.25"


def test_write_fx_csv_merges_with_existing(tmp_path: Path) -> None:
    out = tmp_path / "fx.csv"
    # Write initial data.
    existing = [
        {"date": "2025-01-02", "base_currency": "GBP", "quote_currency": "USD", "rate": "1.25", "source_name": "old"},
        {"date": "2025-01-04", "base_currency": "GBP", "quote_currency": "USD", "rate": "1.30", "source_name": "old"},
    ]
    write_fx_csv(existing, out)

    # Merge: overlapping date gets updated, new date added, existing-only preserved.
    new = [
        {"date": "2025-01-02", "base_currency": "GBP", "quote_currency": "USD", "rate": "1.26", "source_name": "new"},
        {"date": "2025-01-03", "base_currency": "GBP", "quote_currency": "USD", "rate": "1.27", "source_name": "new"},
    ]
    write_fx_csv(new, out)

    with out.open(newline="", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    assert len(reader) == 3
    by_date = {r["date"]: r for r in reader}
    assert by_date["2025-01-02"]["rate"] == "1.26"  # updated
    assert by_date["2025-01-02"]["source_name"] == "new"
    assert by_date["2025-01-03"]["rate"] == "1.27"  # added
    assert by_date["2025-01-04"]["rate"] == "1.30"  # preserved


# --- CLI integration ---

runner = CliRunner()


def test_cli_fetch_fx(tmp_path: Path) -> None:
    out = tmp_path / "fx_out.csv"
    with patch("ibkr_trace.fetch_fx.urllib.request.urlopen", return_value=_FakeResponse(SAMPLE_BOE_CSV)):
        result = runner.invoke(
            app,
            ["fetch", "fx", "--start", "2025-01-01", "--end", "2025-01-06", "--output", str(out)],
        )
    assert result.exit_code == 0, result.output
    assert "rates_fetched=3" in result.output
    assert out.exists()
