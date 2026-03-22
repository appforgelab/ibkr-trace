# Investigation: HMRC Tax Trace

This project deliberately stops short of UK capital-gains computation.

The intended manual-review path before any HMRC engine exists is:

- identify symbols traded in the relevant period
- inspect a per-symbol ledger with running open position totals
- use that ledger to locate earlier acquisitions and later disposals that matter for tax work

Future work for a tax-specific trace should cover:

- same-day matching
- 30-day matching
- Section 104 pooling
- GBP conversion at acquisition and disposal dates
- option-specific exercise and assignment treatment
- audit outputs that explain why a disposal matched to a pool rather than named lots

This should be treated as a separate design and implementation track, not folded into the simpler symbol-ledger review workflow or the optional FIFO economic trace.
