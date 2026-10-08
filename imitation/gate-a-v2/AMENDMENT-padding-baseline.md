# Pretraining compatibility amendment: masked padding in frequency baseline

2026-10-08 12:27 UTC. No v2 training, calibration or held-out scoring has
occurred. The store is complete and unchanged. The first dev baseline exited
with T5's `duplicate hand token would break baseline/spec alignment` guard.
The fitted frequency counts are complete, preserved and reused unchanged.

An exhaustive **dev-only** audit found exactly two supervised play rows with
duplicate hand tokens: packed dev rows8,762,043 and11,393,318. Both have two
token0 padding slots, both always illegal. There are zero duplicate nonzero
tokens, duplicate legal choices or duplicated labeled cards. Source identities:
episode1003502466/unit6534/source row12451 and
episode1004901990/unit8467/source row11735. Neither is a data/extractor defect.

The T11 compatibility wrapper imports the unchanged T5 frequency scorer. Only
when a play row has duplicate padding tokens, it passes a private baseline
view with unique temporary token IDs for the extra **illegal zero-mass padding
slots**. It verifies these slots are masked out and never labeled. Counts times
the same zero legality masks remain exactly zero; every gate, card, tile and
joint probability is unchanged. Model feature construction receives original
hand IDs. Stored arrays, masks, roles, counts, T4/T5 files and all metrics/bars
are unchanged. Non-padding or legally selectable duplicates still fail closed.

Verify the adapter against the already-used T3 float64 formulas on both
affected rows and ordinary dev rows, assert source bytes unchanged, and retain
the failed logs. Require a hashed PASS receipt before freezing or fitting.
This resolves an over-broad diagnostic assertion, not a changed baseline.
