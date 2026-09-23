# Rejected: entity-owned fast target-cache index

Date: 2026-08-11

The candidate published each entity's derived target-cache index during
structural rebuilds, then used an identity-validated direct slot in
`_sync_fast_target_entity` instead of a dictionary lookup and repeated
eligibility check. Stale indices fell back to the exact dictionary path. It
was card-general and preserved all fixed hashes, but did not improve both
production rollout workloads.

All measurements were one process, one Torch/BLAS/OpenMP/VecLib thread,
`nice -n 15`, seed 2301, with RoadForge occupying one CPU core.

| Workload | Paired median | Positive | Mean 95% bootstrap CI | Median-rate change | Hash |
| --- | ---: | ---: | ---: | ---: | --- |
| oracle, 3 states, depth 6, 32 simulations | +0.654% | 8/11 | +0.266% to +1.163% | +0.447% | `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9` |
| strategy, 8 env x 32 decisions | +0.273% | 8/11 | +0.109% to +1.224% | +0.343% | `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d` |
| random, 8 env x 32 decisions | +0.065% | 6/11 | -0.305% to +0.848% | **-0.087%** | `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a` |

Raw outputs:

- `/tmp/entity_target_index_oracle.json`
- `/tmp/entity_target_index_strategy_8x32.json`
- `/tmp/entity_target_index_random_8x32.json`

All source, test, and benchmark-driver changes were removed. This rejection
report remains untracked and must not be included with an unrelated commit.
