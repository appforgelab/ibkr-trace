# Phase 03: Reporting

## Intent

Export review-friendly reports for a period and make it easy to inspect one symbol's full trading history.

## Implementation Decisions

- use absolute date windows rather than tax-year shortcuts
- write outputs under `data/reports/`
- keep reports flat and review-friendly
- add a period-level symbol list so the user can see which instruments were active in the chosen window
- add a per-symbol ledger view that shows every trade in time order with a running open quantity
- make the ledger use the exact `symbol` stored in `trade_events`
- include all trades for that symbol from inception through the requested end date
- define the running total as the cumulative signed quantity through each row
- keep the ledger as a review aid only, with no FIFO or HMRC matching logic

## Interfaces Touched

- `ibkr-trace report year --start YYYY-MM-DD --end YYYY-MM-DD`
- `ibkr-trace report symbols --start YYYY-MM-DD --end YYYY-MM-DD`
- `ibkr-trace report ledger --symbol SYMBOL --end YYYY-MM-DD`

## Acceptance Tests

- trades report contains only trade rows in range
- dividends report contains only dividend rows in range
- interest report contains only interest rows in range
- symbol report lists only symbols with trades in the requested period
- ledger report shows a symbol's trades in order with row quantity and running position total
- ledger report filename is stable, such as `ledger_<symbol>_<end>.csv`

## PR Checklist

- reporting queries implemented
- CSV output implemented
- range filtering tested
- symbol discovery implemented
- per-symbol ledger implemented
