# Rejected cached base-deployment masks

Date: 2026-08-11

## Candidate

Cache the three exact static intersections used by every fast action mask:
deploy-zone with non-blocked tiles, that result without live tower tiles, and
non-blocked tiles without live tower tiles. The cache key contained player,
the complete zone state, and all six tower-alive flags.

The arrays were read-only in the mask builder, the logic was card general, and
nine focused cases proved exact masks for both players and changed enemy tower
states.

## Bounded attribution and rejection

The single-process probe used seed 2301, a fixed mixed troop hand with live
building occupancy, 128 two-player mask decisions per row, 11 alternating
matched pairs, and `nice -n 15`. Clasher training and one RoadForge CPU process
shared the host.

| variant | median seconds | median decision pairs/s | mask digest |
| --- | ---: | ---: | --- |
| fresh NumPy intersections | 0.101623 | 1,259.559 | `87dce9035addfb75cdfac39781f1d89aa7a1854e07b9af1487364aababe1f29f` |
| cached intersections | 0.102316 | 1,251.027 | `87dce9035addfb75cdfac39781f1d89aa7a1854e07b9af1487364aababe1f29f` |

The cached path regressed median rate by **0.68%**. Its paired median was
`-0.18%`, only 5/11 pairs were positive, and the positive paired mean was
driven by one host-contention outlier. Cache-key construction and lookup cost
more than the three small NumPy Boolean operations.

The candidate was rejected before rollout/oracle timing. All source, tests,
and benchmark drivers were removed; no optimization commit was created.
