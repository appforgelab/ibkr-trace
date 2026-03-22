# Investigation: HMRC Tax Trace

This project deliberately stops short of UK capital-gains computation.

Future work for a tax-specific trace should cover:

- same-day matching
- 30-day matching
- Section 104 pooling
- GBP conversion at acquisition and disposal dates
- option-specific exercise and assignment treatment
- audit outputs that explain why a disposal matched to a pool rather than named lots

This should be treated as a separate design and implementation track, not folded into the v1 FIFO economic trace.
