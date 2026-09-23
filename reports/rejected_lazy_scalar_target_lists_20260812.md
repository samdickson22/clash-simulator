# Rejected: lazy scalar target lists (2026-08-12)

`Entity.get_nearest_target` previously allocated its scalar building/troop
candidate lists before attempting the crowded vector selector. The candidate
moved those two empty-list allocations after the vector return, guarded by an
exact reference switch. Target order, eligibility, distance, fallback, RNG,
and battle state were unchanged.

The fixed oracle screen used seed 9037, planner seed 2037, two snapshots,
depth 6, 32 simulations, 64 action samples, 8-tick steps, 11 alternating
pairs, one process/thread, and `nice -n 15` on the Apple M4 Pro host.

| variant | seconds | labels/s |
| --- | ---: | ---: |
| eager lists | 1.191552 | 1.678483 |
| lazy lists | 1.190151 | 1.680459 |

The ratio of medians was +0.118%, but paired median was -0.039%, only 4/11
pairs were positive, and the bootstrap mean 95% confidence interval crossed
zero (-0.197% to +0.279%). Both variants produced exact action/state/planner
RNG digest
`f2189cf83eab5eb6c9b9512bd621a351c0691b8dd8ac14cb2d4c4745c7772f32`.
Thirty-two focused scalar/vector targeting, target-switching, spatial parity,
and exact planner tests passed before timing.

The candidate source, test-driver, and rollout-driver hunks were removed. No
commit was created; the allocation is real but below end-to-end attribution.
