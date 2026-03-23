# ibkr-trace

`ibkr-trace` is a local CLI project for importing Interactive Brokers Activity CSVs into SQLite and producing repeatable, review-friendly symbol activity reports and year-window exports.

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
- daily FX import support for later GBP-enriched reports

Planned next:

- per-symbol trade ledgers with running position totals

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
- `data/`: local inputs, runtime SQLite database, and generated reports, ignored by git

## Workflow

Create the local environment:

```bash
uv sync
```

Activate the local virtual environment:

```bash
source .venv/bin/activate
```

Import IBKR Activity CSV files:

```bash
ibkr-trace import ibkr --path data/ibkr/activity
```

Fetch daily GBP/USD rates from the Bank of England:

```bash
ibkr-trace fetch fx --start 2025-04-06 --end 2026-04-05
```

Import the fetched FX rates into the database:

```bash
ibkr-trace import fx --path data/fx/gbp_usd_daily.csv
```

Write year-window reports:

```bash
ibkr-trace report year --start 2025-04-06 --end 2026-04-05
```

Write the symbol activity report for a period:

```bash
ibkr-trace report symbols --start 2025-04-06 --end 2026-04-05
```

Current trace support:

```bash
ibkr-trace trace --start 2025-04-06 --end 2026-04-05
```

If you prefer not to activate `.venv`, you can still run the CLI with `uv run ibkr-trace ...`, but the activated-shell workflow is the default documented path.

The preferred manual-review workflow for UK tax prep is:

1. identify which symbols were traded in the period
2. inspect a single symbol ledger in time order with a running open position

That is intentionally simpler and less misleading than pretending to apply HMRC matching rules before they are implemented.

## Data Conventions

- raw broker files are stored locally under `data/` and are not tracked in git
- the primary SQLite database is `data/db/ibkr.sqlite`
- generated CSV outputs are written under `data/reports/`
- all broker numeric values are stored as canonical decimal-safe text
- current trace output is an economic FIFO trace, not an HMRC tax trace
- the preferred review model is a symbol ledger with running totals rather than inferred tax matching
