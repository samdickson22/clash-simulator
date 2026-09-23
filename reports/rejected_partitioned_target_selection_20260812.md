# Rejected: partitioned scalar target selection (2026-08-12)

The candidate selected directly across the scalar selector's existing
troop/building candidate partitions instead of allocating
`troop_targets + building_targets`. It preserved strict-distance replacement,
troop-first encounter priority on exact ties, and owner-relative building tie
resolution. Exhaustive small distance/tie combinations and 31 focused
selector/targeting/target-switching tests passed.

A fixed stationary-random screen used seed 9079, 4 environments x 32 steps,
15 alternating pairs after 24 warmup decisions, defense-v2, optimized/on
engine, one process/thread, and `nice -n 15` on Apple M4 Pro.

| variant | seconds | decisions/s |
| --- | ---: | ---: |
| concatenated | 0.658020 | 194.523 |
| partitioned | 0.660464 | 193.803 |

The candidate regressed -0.370% by ratio of medians and -0.336% paired median.
Only 3/15 pairs improved; the bootstrap mean 95% confidence interval was
-0.895% to -0.057%. Both variants produced exact full-rollout digest
`f04e28977a207cd0e2c12bcde399017952c9de7d806b9508ca37a4311daa4265`.

The two independent minimum searches cost more than concatenating these small
lists and retaining the established singleton/general selector. Candidate
source, test, and benchmark hunks were removed; no commit was created.
