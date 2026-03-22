# Phase 03: Reporting

## Intent

Export year-window CSV reports for trades, dividends, and interest.

## Implementation Decisions

- use absolute date windows rather than tax-year shortcuts
- write outputs under `data/derived/reports/`
- keep reports flat and review-friendly

## Interfaces Touched

- `uv run ibkr-trace report year --start YYYY-MM-DD --end YYYY-MM-DD`

## Acceptance Tests

- trades report contains only trade rows in range
- dividends report contains only dividend rows in range
- interest report contains only interest rows in range

## PR Checklist

- reporting queries implemented
- CSV output implemented
- range filtering tested
