# Rejected: direct tight bucket-bound clamps

Date: 2026-08-12. Current verified stack: `16a1125`.

The hot stationary-random profile attributed 32 ms self time across 11,910
`BattleState.iter_entities_in_radius` calls. A candidate replaced the six
scalar `min`/`max` dispatches used by exact tight-bound production queries with
equivalent direct comparisons. Unit coverage compared exact ordered candidate
IDs at arena boundaries, outside-arena centers, sub-half-tile and oversized
radii, and NaN; 35 focused bucket/collision/avoidance tests passed.

The production-shaped matched command used one CPU/BLAS/Torch thread at
`nice -n 15`, 4 stationary-random environments, 32 decisions, 24 warmup
decisions, seed 9047, exact fast path, `defense-v2`, and 15 alternating pairs.
The complete rollout hash was unchanged:
`e95b8697c74ba09d57a1ae183409b5ce58def265fcc2d2b2734c057883146df8`.

The direct candidate measured 213.707 decisions/s versus 213.118 for the
reference. Its paired median was +0.362% with 13/15 positive pairs, but the
bootstrap mean 95% CI crossed zero (-0.327% to +0.460%). An earlier partial
candidate was also inconclusive (+0.511% paired median, 9/15 positive, CI
-0.123% to +0.874%). The source, tests, and benchmark-driver changes were
therefore removed and no commit was made.
