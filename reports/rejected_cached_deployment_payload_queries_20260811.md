# Rejected cached deployment-payload query candidate

Date: 2026-08-11

## Candidate

Within one fast action-mask build, cache the authoritative Boolean result of
`BattleState.is_deployment_payload_occupied` by canonical tile and exact
collision geometry. Troops were keyed by collision radius and buildings by
their integer footprint size; their namespaces were distinct. The cache was
request-local, used no card names, changed no floating-point predicate, and
required no invalidation.

The candidate source, tests, and dedicated benchmark driver were removed after
production attribution.

## Correctness

- 33 deployment-blocker, scalar/fast action-mask, and gather tests passed.
- Both canonical player perspectives with a live timed payload produced
  bit-identical masks while reducing authoritative occupancy calls.
- The scalar path was unchanged and bit-identical.
- Every production reference/candidate pair below produced the same digest.
- Ruff, Python compilation, and `git diff --check` passed.

## Live-payload kernel

Apple M4 Pro, macOS 26.5.2 arm64, Python 3.12.13; seed 2301; 128 two-player
mask decisions; 11 alternating pairs; niceness 15; hand
`Knight,Archers,Musketeer,Cannon`; one live payload at (9.5, 15.5).

- Reference median: 0.079930 s, 1,601.406 decision pairs/s
- Cached median: 0.056109 s, 2,281.281 decision pairs/s
- Paired median/mean: +39.643% / +40.844%; 11/11 positive
- Mean bootstrap 95% CI: +38.881% to +42.939%
- Both hashes: `499274cb6019acc02f42cc5de05531d58f10ec333cb816161e6b3812d2d0db55`

## Production-shaped attribution

Each screen used seven alternating pairs at niceness 15 while sharing the host
with an unrelated MPS imitation fit and a single-core RoadForge solver. These
paired results support rejection, not cross-run absolute-throughput claims.

| workload | reference median | cached median | paired median | mean 95% CI | positive | digest |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| random, 8 env x 32 | 184.347 decisions/s | 184.072 decisions/s | -0.438% | -1.176% to +3.038% | 3/7 | `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a` |
| balanced strategy, 8 env x 32 | 181.824 decisions/s | 188.367 decisions/s | +1.240% | +0.223% to +4.550% | 5/7 | `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d` |
| oracle, depth 6 x 32, 3 labels | 2.542 decisions/s | 2.530 decisions/s | -0.497% | -1.297% to -0.021% | 1/7 | `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9` |

## Decision

Reject. The dictionary bookkeeping is profitable only while a payload is live
and two or more hand slots share collision geometry. It is neutral/noisy for
random rollouts and significantly regresses the authoritative oracle screen.
Enabling it conditionally by known cards or deck composition would violate the
general mechanics requirement and is not justified.
