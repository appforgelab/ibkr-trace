from __future__ import annotations

from datetime import date
from pathlib import Path

import typer

from ibkr_trace.config import DEFAULT_DB_PATH
from ibkr_trace.db import get_engine
from ibkr_trace.import_fx import import_fx_rates
from ibkr_trace.import_ibkr import import_ibkr_activity
from ibkr_trace.reporting import write_year_reports
from ibkr_trace.tracing import write_trace_report


app = typer.Typer(help="Idempotent IBKR import, reporting, and FIFO trace CLI.")
import_app = typer.Typer(help="Import broker or FX source files.")
report_app = typer.Typer(help="Write review-friendly CSV reports.")
app.add_typer(import_app, name="import")
app.add_typer(report_app, name="report")


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


@app.callback()
def main() -> None:
    pass


@import_app.command("ibkr")
def import_ibkr(path: str = typer.Option(..., help="Path to an IBKR Activity CSV or a directory of CSV files."), db: str = typer.Option(str(DEFAULT_DB_PATH), help="SQLite database path.")) -> None:
    engine = get_engine(db)
    summary = import_ibkr_activity(engine, path)
    typer.echo(f"IBKR import completed: run_id={summary['run_id']} files_seen={summary['files_seen']} files_new={summary['files_new']} trade_events={summary['trade_events']} cash_income_events={summary['cash_income_events']}")


@import_app.command("fx")
def import_fx(path: str = typer.Option(..., help="Path to a daily FX CSV file."), db: str = typer.Option(str(DEFAULT_DB_PATH), help="SQLite database path.")) -> None:
    engine = get_engine(db)
    summary = import_fx_rates(engine, path)
    typer.echo(f"FX import completed: run_id={summary['run_id']} files_seen={summary['files_seen']} files_new={summary['files_new']} fx_rates={summary['fx_rates']}")


@report_app.command("year")
def report_year(
    start: str = typer.Option(..., help="Inclusive start date in YYYY-MM-DD format."),
    end: str = typer.Option(..., help="Inclusive end date in YYYY-MM-DD format."),
    symbol: str | None = typer.Option(None, help="Optional symbol filter."),
    db: str = typer.Option(str(DEFAULT_DB_PATH), help="SQLite database path."),
    output_dir: str | None = typer.Option(None, help="Optional output directory override."),
) -> None:
    engine = get_engine(db)
    outputs = write_year_reports(
        engine,
        _parse_date(start),
        _parse_date(end),
        symbol=symbol,
        output_dir=Path(output_dir) if output_dir else None,
    )
    for label, path in outputs.items():
        typer.echo(f"{label}: {path}")


@app.command("trace")
def trace(
    start: str = typer.Option(..., help="Inclusive start date in YYYY-MM-DD format."),
    end: str = typer.Option(..., help="Inclusive end date in YYYY-MM-DD format."),
    symbol: str | None = typer.Option(None, help="Optional symbol filter."),
    db: str = typer.Option(str(DEFAULT_DB_PATH), help="SQLite database path."),
    output_dir: str | None = typer.Option(None, help="Optional output directory override."),
) -> None:
    engine = get_engine(db)
    summary = write_trace_report(
        engine,
        _parse_date(start),
        _parse_date(end),
        symbol=symbol,
        output_dir=Path(output_dir) if output_dir else None,
    )
    typer.echo(
        "Trace completed: "
        f"trace_run_id={summary['trace_run_id']} "
        f"trace_edges={summary['trace_edges']} "
        f"unmatched_reductions={summary['unmatched_reductions']} "
        f"output={summary['output_path']}"
    )
