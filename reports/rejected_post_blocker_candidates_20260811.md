# Rejected post-blocker candidates

Date: 2026-08-11

These candidates were screened after the exact deployment-blocker snapshot.
None remains in source and no optimization claim is made from them.

## Direct native-route backwards scan

The candidate classified newly built routes directly from immutable half-tile
cells instead of allocating a tuple of intermediary `Position` objects. A
fixed route-miss-heavy crowded battle used seed 2301, 12 Knights per side, 64
ticks, seven alternating pairs, the exact fast path, and `nice -n 15`.

- reference median: 0.112637 seconds
- direct median: 0.112490 seconds
- paired gain median/mean: +0.25% / +0.30%
- positive pairs: 5/7
- every hash: `d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`

Two pairs regressed and the deliberately amplified workload gained less than
0.3%, so the source hunk was removed without running normal rollouts.

## PyTorch inference-mode collector wrapper

This preliminary screen is retained only as provenance. It was superseded by
the longer matched random and strategy evidence, recurrent-state lifecycle
coverage, scalar/shadow/on digest parity, and accepted implementation in
commit `ea29277`; see `reports/rollout_inference_mode_20260811.md`.

A source-free wrapper compared the existing `no_grad` stationary-random
collector with an outer `torch.inference_mode()` context at seed 3401, eight
environments, 32 steps, two Torch threads, and seven alternating pairs.

- no-grad median: 1.490065 seconds
- inference-mode median: 1.460669 seconds
- paired gain median/mean: +1.58% / +2.80%
- positive pairs: 5/7
- every hash: `3a678a65cc9f63b40880107aa0463501c60c50f8b3bc2db528ef168818b3ca1b`

The first pair was a large shared-load outlier and two pairs regressed. A
longer repeat was invalidated when the main worktree started an MPS
architecture fit using about 72-74% CPU and 24% RAM; RoadForge then started a
single-core reconstruction as well. No source change was made. Revisit only
with uncontaminated matched rollout evidence and recurrent-state lifecycle
tests.

## Single-pass stationary-random mask sampling

The candidate removed `np.any(mask)` immediately before
`np.flatnonzero(mask)`. A 2,306-entry fixed mask, 10,000 samples per row, and 11
alternating pairs showed a +24.34% paired median sampler-kernel gain with
identical actions and complete RNG continuation. The absolute saving was only
about 0.92 microseconds per opponent decision. At the representative 8 x 32
rollout shape that attributes about 0.24 milliseconds, roughly 0.02% of the
measured rollout wall time. The hunk and its three unit tests were removed as
immaterial without spending a loaded-host production timing loop.
