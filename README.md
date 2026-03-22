# ibkr-trace

`ibkr-trace` is a local CLI project for importing Interactive Brokers Activity CSVs into SQLite, producing repeatable year-window reports, and tracing reducing trades back to originating opens with FIFO.

## Disclaimer

This project is an engineering tool for ledger reconstruction, reporting, and trade tracing.

- It is not tax advice.
- It is not a full capital-gains calculator.
- It does not implement HMRC same-day, 30-day, or Section 104 matching.
- Any tax filing output should be reviewed independently before use.

## Scope

V1 covers:

- idempotent IBKR Activity CSV imports
- normalized trades, instrument metadata, dividends, and interest
- absolute date-window CSV reports
- FIFO economic trace of reducing trades
- daily FX import support for later GBP-enriched reports

V1 does not cover:

- HMRC Section 104 pooling
- same-day or 30-day UK tax matching
- full UK capital gains computation

This scope boundary is intentional so the project remains audit-friendly and does not imply tax correctness beyond the implemented ledger and trace features.

## Stack

- Python 3.13
- `uv`
- SQLite
- SQLAlchemy Core
- Alembic
- Typer
- pytest

## Layout

- `src/ibkr_trace/`: application code
- `docs/`: roadmap and phase specs
- `tests/`: unit, integration, and sanitized fixtures
- `data/sources/`: local raw inputs, ignored by git
- `data/derived/`: local DB and report outputs, ignored by git

## Workflow

Create the local environment:

```bash
uv sync
```

Import IBKR Activity CSV files:

```bash
uv run ibkr-trace import ibkr --path data/sources/ibkr/activity
```

Import daily FX rates:

```bash
uv run ibkr-trace import fx --path data/sources/fx/gbp_usd_daily.csv
```

Write year-window reports:

```bash
uv run ibkr-trace report year --start 2025-04-06 --end 2026-04-05
```

Write FIFO trace edges for reducing trades:

```bash
uv run ibkr-trace trace --start 2025-04-06 --end 2026-04-05
```

## Data Conventions

- raw broker files are stored locally under `data/sources/` and are not tracked in git
- the primary SQLite database is `data/derived/db/ibkr.sqlite`
- all broker numeric values are stored as canonical decimal-safe text
- traces are economic FIFO traces, not HMRC tax traces
