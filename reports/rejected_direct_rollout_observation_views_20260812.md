# Rejected: direct rollout observation views (2026-08-12)

## Candidate

Stack each CPU actor observation directly into the current slice of the final
`[agent, step, ...]` rollout arrays and use that same slice as policy input.
This would remove the copy from the established reusable contiguous step
buffers into rollout storage.

## Result

Rejected and fully removed. A 4-environment, 32-step, 15-pair stationary-random
screen measured only +0.303% by ratio of medians (paired median +0.147%, 9/15
positive pairs, bootstrap mean 95% confidence interval -0.237% to +1.203%).
More importantly, exact rollout parity failed.

The reusable-buffer reference produced digest
`b6c9747fdd8d257d9729eb0a93ae440c06ed51fc61a5bee001df902ab14abb45`;
the direct-view candidate produced
`02b02d7346104e519f8ad8f918f1e3388e1fc2d7a5a4755417a9a07994cfc54d`.
One-step digests match, but the first mismatch appears by the second recurrent
decision and persists for 4, 8, 16, and 32 steps.

## Cause

With rollout storage laid out as `[agent, step, ...]`, selecting one step is a
non-contiguous/strided NumPy view whenever the rollout has multiple steps. The
existing reusable step buffers are contiguous. Passing the strided view through
`torch.as_tensor` selects different CPU policy-kernel memory behavior; at the
production model size, tiny numerical differences change sampled recurrent
actions by decision two. Making the view contiguous would restore the copy (and
per-step allocation) that the candidate attempted to eliminate.

## Controls

- Apple M4 Pro, 24 GiB RAM; macOS 26.5.2 arm64; Python 3.12.13
- fixed seed 9071, 4 environments, 32 rollout steps, 15 alternating pairs
- one Torch/BLAS/OpenMP/Accelerate thread, single process, `nice -n 15`
- exact defense-v2 reward profile and optimized/on engine
- no competing Clasher or RoadForge worker during the main screen

The candidate source, test, and benchmark-driver hunks were removed. The raw
main-screen result remains at `/tmp/direct_rollout_random.json` for the current
host session; this rejection report is the durable artifact.
