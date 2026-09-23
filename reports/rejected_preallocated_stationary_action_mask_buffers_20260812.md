# Rejected: preallocated stationary action-mask aggregation buffers

Date: 2026-08-12  
Machine: Apple Silicon macOS host; single process; Torch and BLAS limited to one CPU thread; `nice -n 15`.  
Candidate: replace per-step mask lists plus `np.stack` in the stationary-opponent collector with reusable contiguous `(num_envs, num_actions)` boolean buffers.

## Production-shaped random-opponent rollout

Command:

```sh
env PYTHONPATH=src:.:scripts/perf OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 nice -n15 \
  uv run python scripts/perf/benchmark_inline_position_quantization_rollout.py \
  --comparison preallocated-action-mask-buffers --workload random --seed 9021 \
  --num-envs 4 --rollout-steps 32 --repetitions 15 --warmup-steps 24 \
  --torch-threads 1 --engine-fast-path on --reward-profile defense-v2
```

Fixed configuration: 4 environments, 32 learner decisions per repetition, 15 interleaved pairs, seed 9021.

- Existing list plus `np.stack`: 202.874 decisions/s median, 0.630932 s median.
- Reusable buffers: 202.533 decisions/s median, 0.631997 s median.
- Paired median: **-0.162%**; mean -0.474%; 3/15 pairs positive; paired bootstrap mean 95% CI -1.305% to +0.154%.
- Both modes produced the exact same rollout/final-state hash: `74a69488667e9fa9ceebdf83d0c18759ea81da6a071b0995d0b49a63f0c45903`.

## Decision

Rejected and removed. The saved allocations are too small to offset assigning each complete boolean mask into the reusable row. No second workload or commit was justified after the primary target workload was negative. This report is intentionally not part of a source commit.
