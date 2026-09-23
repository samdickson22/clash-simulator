# Rejected changed-only combat target synchronization

The candidate skipped full fast-target publication after combat when cached
membership, position, target plane, and capability-selected targetability were
unchanged. Movement synchronization remained unconditional. It was removed
because the extra Python predicates cost more than the small array writes they
avoided.

All timings were single-process CPU-only at `nice -n 15`, with OpenBLAS,
OpenMP, VecLib, and Torch limited to one thread. Each comparison used 11
alternating paired repetitions after warmup on Apple M4 Pro, macOS 26.5.2,
Python 3.12.13.

| Workload | Reference | Candidate | Paired median | Positive pairs | Mean 95% bootstrap CI |
| --- | ---: | ---: | ---: | ---: | ---: |
| exact oracle, labels/s | 2.946660 | 2.880260 | -2.277% | 0/11 | -2.424% to -2.034% |
| balanced strategy, decisions/s | 186.115 | 182.827 | -1.269% | 3/11 | -3.115% to +0.038% |
| random, decisions/s | 187.721 | 185.338 | -1.355% | 1/11 | -2.023% to +0.261% |

Exact hashes nevertheless matched in every row:

- oracle: `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`
- strategy: `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d`
- random: `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a`

Raw outputs remain in `/tmp/combat_target_sync_{oracle,strategy,random}.json`
for this host session. No source, benchmark-driver, or test hunk from the
candidate remains.
