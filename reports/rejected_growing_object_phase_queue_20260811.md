# Rejected growing object-phase queue

The candidate replaced `_run_object_phase`'s repeated dictionary rescan/sort
with one ID-sorted queue extended by monotonically allocated same-frame object
IDs. It preserved command-created-object exclusion, dynamic spawn order,
same-frame projectile state, battle RNG, and fixed rollout hashes, but its
production rollout gain was not established.

All timings were single-process CPU-only at `nice -n 15`, with OpenBLAS,
OpenMP, VecLib, and Torch limited to one thread. Each comparison used 11
alternating paired repetitions after warmup on Apple M4 Pro, macOS 26.5.2,
Python 3.12.13.

| Workload | Rescan | Queue | Paired median | Positive | Mean 95% bootstrap CI |
| --- | ---: | ---: | ---: | ---: | ---: |
| exact oracle, labels/s | 3.018332 | 3.029133 | +0.409% | 9/11 | +0.117% to +0.509% |
| balanced strategy, decisions/s | 196.019 | 196.195 | +0.092% | 9/11 | -0.101% to +0.815% |
| random, decisions/s | 189.121 | 189.092 | +0.041% | 6/11 | -0.160% to +0.891% |

Every row retained its exact fixed hash:

- oracle: `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`
- strategy: `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d`
- random: `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a`

Raw outputs remain in `/tmp/object_phase_queue_{oracle,strategy,random}.json`
for this host session. All source, test, and benchmark-driver hunks were
removed.
