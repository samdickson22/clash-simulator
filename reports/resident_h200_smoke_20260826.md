# Resident H200 smoke — 2026-08-26

This is bounded absolute-throughput evidence for the resident PyTorch Gym. It
is not a Python comparison, a speedup claim, or a full-episode acceptance run.

## Environment

- Accelerator: NVIDIA H200 141 GB
- PyTorch: 2.10.0 with CUDA 12.8 runtime packages
- Validation profile: `projected_gym_transition_v1`
- Policy: deterministic no-op
- Repetitions: 2
- Measured decisions per repetition: 1
- Decision interval: 1 tick

Every recorded run had deterministic repeated digests, zero fallback, and all
requested ticks executed natively.

## Results

| Execution profile | Batch | Entity/object capacity | Median native row-ticks/s | Median seconds/decision |
| --- | ---: | ---: | ---: | ---: |
| `exact_debug` | 1 | 16/16 | 0.3862 | 2.5901 |
| `exact_debug` | 1 | 128/128 | 0.07305 | 13.6926 |
| `gym_fast` | 1 | 16/16 | 0.4783 | 2.0933 |
| `gym_fast` | 1 | 128/128 | 0.08386 | 11.9257 |
| `gym_fast` | 16 | 16/16 | 7.2608 | 2.2053 |

The fast profile removes diagnostic event bookkeeping and checked pool
validation, but the retained owner topology remains unsuitable for training.

## Profile diagnosis

A single batch-1, capacity-16 `gym_fast` tick under `torch.profiler` recorded:

- 275,608 `cudaLaunchKernel` calls;
- 19,231 `cudaStreamSynchronize` calls;
- 1,572,470 profiler events;
- 438.8 ms aggregate CUDA kernel time;
- 3.225 s aggregate CPU profiler time.

The profiler itself adds overhead, so those times are diagnostic rather than
benchmark measurements. The operation counts establish the architectural
problem: fixed-capacity retained owners and Python-controlled eager kernels
dominate a tick even when almost every mechanic is inactive.

## Decision

Keep `TensorResidentEngine` as the exact-debug and mechanic verification path.
Do not use it as the production RL executor. Build a unified, approximate Gym
kernel with one dense entity state and a small number of vectorized phase
passes, while retaining projected policy-state, mask, reward, and outcome
validation against available real-game data.
