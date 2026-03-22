# ibkr-trace Plan

## Summary

- repo root: project-local `ibkr/` directory
- repo/project/CLI name: `ibkr-trace`
- Python package: `ibkr_trace`
- database path: `data/db/ibkr.sqlite`
- primary goal: local, idempotent ledger reconstruction for IBKR Activity CSV data, with review-friendly symbol discovery and per-symbol ledgers

## Scope

Included in v1:

- git repo bootstrap inside `ibkr/`
- local Python project managed with `uv`
- raw staging plus normalized SQLite schema
- idempotent import for IBKR Activity CSVs
- idempotent import for daily FX CSVs
- absolute date-window reporting for trades, dividends, and interest
- period-level symbol discovery
- per-symbol ledgers with running open position totals
- optional economic trace output for debugging and internal analysis

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
- `source .venv/bin/activate`
- `ibkr-trace import ibkr --path <file-or-dir>`
- `ibkr-trace import fx --path <file>`
- `ibkr-trace report year --start YYYY-MM-DD --end YYYY-MM-DD`
- `ibkr-trace report symbols --start YYYY-MM-DD --end YYYY-MM-DD`
- `ibkr-trace report ledger --symbol SYMBOL --end YYYY-MM-DD`
- `ibkr-trace trace --start YYYY-MM-DD --end YYYY-MM-DD [--symbol SYMBOL]`

Ledger reporting conventions:

- the ledger is for the exact `symbol` stored in `trade_events`
- include all trades for that symbol from inception through the requested end date
- running total is the cumulative signed quantity through each row
- ledger output is a review aid only and does not apply FIFO, HMRC matching, or tax logic

## PR Map

- PR 1: bootstrap repo, docs, schema, Alembic wiring, empty CLI shell
- PR 2: idempotent IBKR import and normalization
- PR 3: year-window reporting, period symbol discovery, and per-symbol ledger views
- PR 4: optional economic tracing and internal analysis helpers
- PR 5: FX import and GBP-enriched reporting surface

## Acceptance Criteria

- re-importing the same Activity CSV does not duplicate normalized events
- importing later year-to-date statements adds only new normalized events
- repeated section headers in one CSV are preserved in raw staging
- assignment, exercise, and expired-position codes survive normalization
- year-window reports include only rows in range
- symbol discovery lists the symbols traded in a specified period
- per-symbol ledgers show all trades in time order with a running open position
- ledger views can be used to inspect positions beyond the period start when earlier trades are needed for context
- if economic tracing is used, stock sells trace back to older buy opens with FIFO
- if economic tracing is used, short option close events trace back to older sold-to-open lots of the same series
- FX imports are idempotent on date and currency pair
