# Rejected specialized `BattleState` deepcopy

Date: 2026-08-12. A memo-aware `BattleState.__deepcopy__` copied exact atomic
built-ins directly and recursively copied every mutable/non-atomic attribute.
Tests proved generic/specialized state, action-mask, RNG, cache, circular entity
back-reference, and mutation-isolation parity.

The three-snapshot direct clone workload used seed 2301, 15 alternating pairs,
and 500 clones per row. Median throughput improved from 2950.85 to 3041.81
clones/s; paired median was +2.9142%, all 15 pairs improved, and the bootstrap
mean 95% CI was +2.5890% to +5.3691%.

The production Oracle used depth 6, 32 simulations, 64 action samples, three
labels per row, and 21 alternating pairs. Generic and specialized modes shared
the exact digest
`72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`,
but paired median throughput changed only +0.0145%, 11/21 pairs improved, and
the bootstrap mean 95% CI crossed zero (-0.0183% to +0.5411%). The
ratio-of-medians was -0.1047% (3.60873 versus 3.60495 labels/s).

The candidate was removed because the clone microbenchmark gain did not
survive the required production workload gate. Raw Oracle output:
`/tmp/battle_state_deepcopy_oracle.json`.
