# Phase 04: Trace

## Intent

Trace reducing trades back to originating opens using FIFO economic matching.

## Implementation Decisions

- this is an economic trace, not HMRC tax matching
- FIFO is fixed in v1
- openings and closings are inferred from IBKR `Code` flags and quantity sign
- only reducing trades inside the requested date window are emitted

## Interfaces Touched

- `uv run ibkr-trace trace --start YYYY-MM-DD --end YYYY-MM-DD [--symbol SYMBOL]`

## Acceptance Tests

- stock sell consumes older buy lots in FIFO order
- short option close consumes older sold-to-open lots in FIFO order
- trace output remains stable across reruns

## PR Checklist

- trace engine implemented
- trace run persistence implemented
- CSV output implemented
- integration tests added
