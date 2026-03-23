"""Fetch GBP/USD daily FX rates from the Bank of England."""

from __future__ import annotations

import csv
import io
import urllib.request
from datetime import date, datetime
from pathlib import Path

from ibkr_trace.config import FX_DIR

BOE_SERIES_CODE = "XUDLUSS"
BOE_URL_TEMPLATE = (
    "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"
    "?csv.x=yes&SeriesCodes={series}&UsingCodes=Y&CSVF=TN"
    "&Datefrom={from_date}&Dateto={to_date}"
)
DEFAULT_OUTPUT_PATH = FX_DIR / "gbp_usd_daily.csv"
SOURCE_NAME = "bank_of_england"


def _boe_url(from_date: date, to_date: date) -> str:
    """Build the BoE CSV download URL for the given date range."""
    return BOE_URL_TEMPLATE.format(
        series=BOE_SERIES_CODE,
        from_date=from_date.strftime("%d/%b/%Y"),
        to_date=to_date.strftime("%d/%b/%Y"),
    )


def _parse_boe_date(value: str) -> date | None:
    """Parse a BoE date like '02 Jan 2025'."""
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return datetime.strptime(stripped, "%d %b %Y").date()
    except ValueError:
        return None


def fetch_boe_rates(from_date: date, to_date: date) -> list[dict[str, str]]:
    """Fetch GBP/USD daily rates from the Bank of England.

    Returns a list of dicts with keys: date, base_currency, quote_currency,
    rate, source_name — ready to write as CSV rows.
    """
    if from_date > to_date:
        raise ValueError(f"from_date ({from_date}) must be <= to_date ({to_date})")

    url = _boe_url(from_date, to_date)
    req = urllib.request.Request(url, headers={"User-Agent": "ibkr-trace/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8-sig")

    rows: list[dict[str, str]] = []
    reader = csv.reader(io.StringIO(raw))
    header = next(reader, None)
    if header is None:
        raise ValueError("BoE response contained no data")

    # The BoE CSV has two columns: DATE, <series_code>
    # Validate we got the expected shape.
    if len(header) < 2:
        raise ValueError(f"Unexpected BoE CSV header: {header}")

    for raw_row in reader:
        if len(raw_row) < 2:
            continue
        rate_date = _parse_boe_date(raw_row[0])
        rate_value = raw_row[1].strip()
        if rate_date is None or not rate_value:
            continue
        rows.append(
            {
                "date": rate_date.isoformat(),
                "base_currency": "GBP",
                "quote_currency": "USD",
                "rate": rate_value,
                "source_name": SOURCE_NAME,
            }
        )

    return rows


def write_fx_csv(rows: list[dict[str, str]], output: Path) -> Path:
    """Write transformed FX rows to a CSV file.

    If the file already exists, merges new rows with existing ones
    (keyed by date), preserving any dates not in the new fetch.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["date", "base_currency", "quote_currency", "rate", "source_name"]

    # Load existing rows keyed by date so we can merge.
    existing: dict[str, dict[str, str]] = {}
    if output.exists():
        with output.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                key = row.get("date", "")
                if key:
                    existing[key] = row

    # New rows overwrite existing for the same date.
    for row in rows:
        existing[row["date"]] = row

    # Write sorted by date.
    sorted_rows = sorted(existing.values(), key=lambda r: r["date"])

    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted_rows)

    return output.resolve()


def fetch_and_save(
    from_date: date,
    to_date: date,
    output: Path = DEFAULT_OUTPUT_PATH,
) -> dict[str, object]:
    """Fetch BoE rates and write to CSV. Returns a summary dict."""
    rows = fetch_boe_rates(from_date, to_date)
    path = write_fx_csv(rows, output)
    return {
        "rates_fetched": len(rows),
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "output_path": str(path),
    }
