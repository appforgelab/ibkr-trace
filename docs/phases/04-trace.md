# Phase 04: Trace

## Intent

Provide optional economic trace output for debugging and internal analysis, without presenting it as HMRC tax matching.

## Implementation Decisions

- this is an economic trace, not HMRC tax matching
- this is secondary to the symbol-ledger workflow and should not be the primary review surface
- FIFO is fixed when economic tracing is used
- openings and closings are inferred from IBKR `Code` flags and quantity sign
- only reducing trades inside the requested date window are emitted

## Interfaces Touched

- `uv run ibkr-trace trace --start YYYY-MM-DD --end YYYY-MM-DD [--symbol SYMBOL]`

## Acceptance Tests

- stock sell consumes older buy lots in FIFO order
- short option close consumes older sold-to-open lots in FIFO order
- trace output remains stable across reruns
- trace output remains clearly labeled as economic rather than tax matching

## PR Checklist

- trace engine kept optional and clearly labeled
- trace run persistence implemented
- CSV output implemented
- integration tests added
