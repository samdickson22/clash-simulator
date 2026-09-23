# Rejected direct native target-distance allowance read

Date: 2026-08-11

The candidate read the required Entity dataclass field
`_native_target_distance_discount_sq_units` directly in ordinary and dash
distance calculations while preserving the legacy negative-value clamp.
Positive, zero, and negative unit cases matched the defensive path exactly.

The bounded stable-root oracle screen used battle seed 2301, planner seed 901,
3 states, depth 6, 32 simulations, 64 action samples, 5 alternating pairs,
and `nice -n 10` while shared RoadForge CPU and Clasher MPS work remained
active.

| variant | median seconds / 3 labels | mean | stdev | labels/s |
| --- | ---: | ---: | ---: | ---: |
| defensive | 1.310234 | 1.315444 | 0.038331 | 2.289668 |
| direct | 1.329190 | 1.315235 | 0.033256 | 2.257014 |

Direct reads regressed median rate by 1.43%. The within-pair gain median was
also negative at -0.47%; three of five pairs regressed. Every row retained
the complete action/state/battle-RNG/planner-RNG digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.

The candidate was rejected before rollout timing. All source, test, and driver
hunks were removed; this report remains uncommitted only as an audit note.
