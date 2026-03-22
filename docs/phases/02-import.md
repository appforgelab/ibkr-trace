# Phase 02: Import

## Intent

Import IBKR Activity CSV files idempotently into raw staging and normalized tables.

## Implementation Decisions

- use file `sha256` to deduplicate source files
- use stable event fingerprints to deduplicate normalized events
- stage every non-empty CSV row with section name, row kind, header signature, row index, and payload
- normalize only `Trades`, `Financial Instrument Information`, `Codes`, `Dividends`, and `Interest`

## Interfaces Touched

- `uv run ibkr-trace import ibkr --path <file-or-dir>`

## Acceptance Tests

- same file imported twice does not duplicate normalized rows
- later YTD file adds only new normalized rows
- repeated section headers are preserved in raw staging

## PR Checklist

- importer implemented
- raw staging implemented
- normalized inserts implemented
- import summary output implemented
- integration tests added
