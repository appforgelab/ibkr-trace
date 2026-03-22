# ibkr-trace Plan

## Summary

- repo root: project-local `ibkr/` directory
- repo/project/CLI name: `ibkr-trace`
- Python package: `ibkr_trace`
- database path: `data/derived/db/ibkr.sqlite`
- primary goal: local, idempotent ledger and traceability for IBKR Activity CSV data

## Scope

Included in v1:

- git repo bootstrap inside `ibkr/`
- local Python project managed with `uv`
- raw staging plus normalized SQLite schema
- idempotent import for IBKR Activity CSVs
- idempotent import for daily FX CSVs
- absolute date-window reporting for trades, dividends, and interest
- FIFO economic trace from reducing trades to originating opens

Excluded from v1:

- HMRC same-day matching
- HMRC 30-day matching
- Section 104 pooling
- average-cost or capital-gains computation
- broker API integration
- web UI

## Data Model

Raw staging tables:

- `import_runs`
- `source_files`
- `raw_section_headers`
- `raw_section_rows`

Normalized tables:

- `code_definitions`
- `instruments`
- `trade_events`
- `trade_event_codes`
- `cash_income_events`
- `trace_runs`
- `trace_edges`
- `fx_rates`

Normalization coverage in v1:

- `Trades`
- `Financial Instrument Information`
- `Codes`
- `Dividends`
- `Interest`

Sections staged but not normalized in v1:

- `Fees`
- `Deposits & Withdrawals`
- stock lending sections
- performance summaries
- other informational statement sections

## Interfaces

- `uv sync`
- `uv run ibkr-trace import ibkr --path <file-or-dir>`
- `uv run ibkr-trace import fx --path <file>`
- `uv run ibkr-trace report year --start YYYY-MM-DD --end YYYY-MM-DD`
- `uv run ibkr-trace trace --start YYYY-MM-DD --end YYYY-MM-DD [--symbol SYMBOL]`

## PR Map

- PR 1: bootstrap repo, docs, schema, Alembic wiring, empty CLI shell
- PR 2: idempotent IBKR import and normalization
- PR 3: year-window reporting
- PR 4: FIFO origin tracing
- PR 5: FX import and GBP-enriched reporting surface

## Acceptance Criteria

- re-importing the same Activity CSV does not duplicate normalized events
- importing later year-to-date statements adds only new normalized events
- repeated section headers in one CSV are preserved in raw staging
- stock sells trace back to older buy opens with FIFO
- short option close events trace back to older sold-to-open lots of the same series
- assignment, exercise, and expired-position codes survive normalization
- year-window reports include only rows in range
- FX imports are idempotent on date and currency pair
