# Rejected: inlined target dynamic refresh

Date: 2026-08-11

The candidate inlined `_refresh_fast_target_dynamic_values` into the exact
target membership scan to remove one Python call per cached entity. It kept a
private called-helper reference path and produced identical oracle and rollout
hashes, but the end-to-end gain was too small to justify duplicating exact
cache publication logic.

All measurements were one process, one Torch/BLAS/OpenMP/VecLib thread,
`nice -n 15`, seed 2301, with RoadForge occupying one CPU core.

| Workload | Paired median | Positive | Mean 95% bootstrap CI | Hash |
| --- | ---: | ---: | ---: | --- |
| oracle, 3 states, depth 6, 32 simulations | +0.228% | 8/11 | -0.055% to +0.398% | `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9` |
| strategy, 8 env x 32 decisions | +0.249% | 10/11 | +0.156% to +1.314% | `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d` |
| random, 8 env x 32 decisions | +0.098% | 7/11 | -0.025% to +1.205% | `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a` |

Raw outputs:

- `/tmp/inlined_target_refresh_oracle.json`
- `/tmp/inlined_target_refresh_strategy_8x32.json`
- `/tmp/inlined_target_refresh_random_8x32.json`

All source, test, and benchmark-driver changes were removed. This rejection
report remains untracked and must not be included with an unrelated commit.
