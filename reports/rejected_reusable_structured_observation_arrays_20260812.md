# Rejected: reusable structured-observation arrays (2026-08-12)

The candidate reused each learner seat's six large actor/critic entity arrays
across synchronous CPU decisions. The builder cleared and refilled those arrays
in place; the established contiguous policy step buffer and final rollout copy
were retained, avoiding the strided-policy-input parity failure documented in
`rejected_direct_rollout_observation_views_20260812.md`.

A fixed 4-environment x 32-step stationary-random screen used seed 9073,
defense-v2, optimized/on engine, one Torch/BLAS/OpenMP/Accelerate thread, 24
warmup decisions, and 15 alternating pairs on the Apple M4 Pro host.

| variant | seconds | decisions/s |
| --- | ---: | ---: |
| fresh arrays | 0.643966 | 198.768 |
| reused arrays | 0.644995 | 198.451 |

The reused path was -0.160% by ratio of medians. Paired median was -0.015%,
only 7/15 pairs were positive, and the bootstrap mean 95% confidence interval
crossed zero (-0.126% to +0.249%). Both variants produced exact full-rollout
digest
`929a880b27dabf2b0fdb7a8d6ec628a93a4b6b1b5be3ca3d6558e50acba46cd4`.
Seventeen builder-buffer/full-rollout/structured-policy/opponent-league tests
passed before timing.

Fresh `numpy.zeros` allocation is already efficient; explicit `fill()` plus
the still-required contiguous stack copy erased the intended saving. All
candidate source, tests, and benchmark toggles were removed, and no commit was
created.
