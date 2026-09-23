# Rejected: cached scalar targetability reuse (2026-08-12)

The candidate reused target-owned eligibility already published in the live
fast target cache during small-set scalar selection, while retaining
attacker-owned pending-projectile and mechanic filters. Identity, ownership,
liveness, and the separately cached stealth clock were validated explicitly;
scalar/off and caller-supplied entity collections retained the full runtime
predicate. It was card-general and exact after the complete guards were added.

Two parity failures during development were caught before acceptance and are
part of the audit trail. The targetability boolean intentionally excludes the
separately vectorized stealth timestamp, and same-frame damage can make cached
membership temporarily stale until the victim component runs. Adding exact
stealth-time and direct liveness checks restored the previously failing
stationary-rollout hash and three independent 64-decision traces.

Final corrected measurements used Apple M4 Pro, Python 3.12.13, one CPU
process/thread, `nice -n 10`, fixed alternating order, and no MPS/GPU. Another
low-CPU Clasher process remained resident, so only paired comparisons were
considered.

| workload | reference seconds | candidate seconds | ratio of medians | paired median | positive pairs | bootstrap mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| exact stable-root oracle, 2 states, 11 pairs | 0.682437 | 0.676797 | **+0.833%** | +0.900% | 10/11 | +0.555% to +0.991% | `c2ff6d942f5632d2ebf99c8f8b6fb323c2c2bc710b8ab448bf82a44e1f8053a8` |
| stationary random, 4 env x 32, 15 pairs after 24 warmup | 0.617911 | 0.618374 | **-0.075%** | +0.384% | 10/15 | -0.319% to +1.545% | `a29f7fd1c8d34ae77a218e80723d3183b0d1fde8a3458ab6a142a3b97ea12d7b` |

The oracle-only gain did not translate into end-to-end random rollout
throughput. Given the additional cache-validity surface and a negative ratio
of production medians, the candidate was rejected. All source and benchmark-
driver hunks were removed; no commit was created.
