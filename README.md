# ibkr-trace

`ibkr-trace` is a local CLI project for importing Interactive Brokers Activity CSVs into SQLite and producing repeatable, review-friendly trade ledgers and year-window reports.

## Disclaimer

This project is an engineering tool for ledger reconstruction and reporting.

- It is not tax advice.
- It is not a full capital-gains calculator.
- It does not implement HMRC same-day, 30-day, or Section 104 matching.
- Any tax filing output should be reviewed independently before use.

## Scope

V1 covers:

- idempotent IBKR Activity CSV imports
- normalized trades, instrument metadata, dividends, and interest
- absolute date-window CSV reports
- symbol discovery for a specified period
- per-symbol trade ledgers with running position totals
- daily FX import support for later GBP-enriched reports

V1 does not cover:

- HMRC Section 104 pooling
- same-day or 30-day UK tax matching
- full UK capital gains computation

This scope boundary is intentional so the project remains audit-friendly and does not imply tax correctness beyond the implemented ledger and reporting features.

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

Current trace support:

```bash
uv run ibkr-trace trace --start 2025-04-06 --end 2026-04-05
```

The preferred manual-review workflow for UK tax prep is:

1. identify which symbols were traded in the period
2. inspect a single symbol ledger in time order with a running open position

That is intentionally simpler and less misleading than pretending to apply HMRC matching rules before they are implemented.

## Data Conventions

- raw broker files are stored locally under `data/sources/` and are not tracked in git
- the primary SQLite database is `data/derived/db/ibkr.sqlite`
- all broker numeric values are stored as canonical decimal-safe text
- current trace output is an economic FIFO trace, not an HMRC tax trace
- the preferred review model is a symbol ledger with running totals rather than inferred tax matching
