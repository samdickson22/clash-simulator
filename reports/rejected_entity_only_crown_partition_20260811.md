# Rejected: entity-only Crown fallback partition

Date: 2026-08-11

The candidate retained only Crown entities during the semantic-slot fallback
partition and recomputed the two cheap horizontal distances during selection,
instead of allocating `(entity, distance)` pairs. It preserved candidate
order, epsilon ties, dynamic validity, complete hashes, and card-general
behavior, but the repeated distance work cost more than the removed tuples.

All measurements were one process, one Torch/BLAS/OpenMP/VecLib thread,
`nice -n 15`, seed 2301, with RoadForge occupying one CPU core.

| Workload | Paired median | Positive | Mean 95% bootstrap CI | Median-rate change | Hash |
| --- | ---: | ---: | ---: | ---: | --- |
| oracle, 3 states, depth 6, 32 simulations | **-0.033%** | 5/11 | -0.459% to +0.676% | -0.059% | `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9` |
| strategy, 8 env x 32 decisions | **-0.055%** | 3/11 | -0.293% to +0.898% | -0.170% | `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d` |
| random, 8 env x 32 decisions | +0.126% | 7/11 | -0.126% to +0.852% | +0.007% | `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a` |

Raw outputs:

- `/tmp/entity_only_crown_partition_oracle.json`
- `/tmp/entity_only_crown_partition_strategy_8x32.json`
- `/tmp/entity_only_crown_partition_random_8x32.json`

All source, test, and benchmark-driver changes were removed. This rejection
report remains untracked and must not be included with an unrelated commit.
