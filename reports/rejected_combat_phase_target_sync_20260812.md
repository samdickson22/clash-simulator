# Rejected: combat-phase target-plane refresh split (2026-08-12)

The candidate used a combat-specific exact fast-target publisher that retained
membership, position, mechanic targetability, and stealth updates while
leaving target-plane publication to the movement component where river jumps
change it. Movement retained the complete publisher because movement-owned
mechanics can change targetability. It was general, contained no card-name
branches, and preserved exact hashes, but the production gain was too small
and noisy to justify duplicating cache-publication logic.

All measurements used Apple M4 Pro, Python 3.12.13, one CPU process/thread,
`nice -n 10`, fixed alternating reference/candidate order, and no MPS/GPU.
Another low-CPU Clasher process remained resident, so only paired comparisons
were considered.

| workload | reference seconds | candidate seconds | median-rate gain | paired median | positive pairs | bootstrap mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| exact stable-root oracle, 2 states, 11 pairs | 0.615031 | 0.611918 | +0.509% | +0.749% | 10/11 | +0.493% to +1.264% | `19429f5aebd23b809c82300e2efd7c74e5ddabc6b2f715e13b6ca10d37ee65a7` |
| random, 4 env x 32, 15 pairs | 0.632497 | 0.630466 | +0.322% | +0.255% | 10/15 | -0.125% to +0.393% | `5e2a582fd524cdd04858771834f37c789d951255305d29de883d497ce9475310` |
| balanced strategy, 4 env x 32, 15 pairs | 0.692319 | 0.689840 | +0.359% | +0.234% | 12/15 | -0.361% to +0.549% | `a861fed6bb9a051cce65bf99015cf6ca7ef32242dbbb188271930557040bec25` |

The production runs used 24 warmup decisions. A shorter 4-warmup screen was
also exact and similarly small: random +0.078% and strategy +0.220% by ratios
of medians. Thirty-nine focused targeting and determinism tests passed while
the candidate was present. All candidate source and benchmark-driver hunks
were removed; no commit was created.
