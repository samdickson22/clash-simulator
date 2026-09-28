# Simple Gym MPS versus CUDA benchmark

## Decision

Use Apple MPS for local development, correctness smoke tests, and bounded experiments. Use CUDA Graph execution for production-scale Simple Gym collection and training.

This is a matched backend benchmark of commit `b8f299f87cbe7e4f8b4823549b85188c146a843b`, a descendant of the verified MPS integration `41d13fed`. It does not claim bit-identical arithmetic between Metal and CUDA. It does establish deterministic replay within each backend, native execution, committed rows, and zero fallback for the measured workload.

## Matched workload

- SimpleGymRuntime
- first-legal policy
- batch size 128
- 10 warm-up ticks
- 100 measured ticks
- 3 repetitions
- seed 202608264
- 33 supported decks, 0 rejected
- no terminal rows in the measured window

## Results

| Backend | Execution | Median row-ticks/s | Median actor transitions/s | Median wall time | Relative to MPS |
|---|---:|---:|---:|---:|---:|
| Apple MPS | eager | 84.1818 | 168.3635 | 152.0519 s | 1.00x |
| RTX A6000 CUDA | eager | 344.2121 | 688.4242 | 37.1864 s | 4.09x |
| RTX A6000 CUDA | CUDA Graph | 416.7948 | 833.5895 | 30.7106 s | 4.95x |

CUDA Graph improved over eager CUDA by 1.211x. The graph profile recorded 10 kernel launches and zero explicit host synchronizations. CUDA eager and CUDA Graph produced the same semantic digest, `7dced673c3a63ba626113811631352bc3dc7692958b5c14bba427341b2e6d70f`.

MPS produced a stable within-backend digest, `963a16330c8159d7942d7d919ce1c5dedb783f4b8ff8ee5279b0bbceb7fe1fa5`. The different MPS and CUDA digests are not treated as a parity failure here because this throughput driver does not implement a cross-device tolerance/state comparison. Separate integration tests cover exact CPU/MPS deployment traces and the public-mask/reward/admission route.

The reported CUDA Graph peak-memory field is allocator/profile-scope dependent and must not be compared directly with eager CUDA peak memory.

## Evidence

- `reports/simple_gym_mps_batch128_profile_20260827.json`
- `reports/simple_gym_cuda_eager_batch128_b8f299f8.json`
- `reports/simple_gym_cuda_graph_batch128_b8f299f8.json`
- `reports/simple_gym_mps_smoke_20260827.json`
- `reports/simple_gym_cuda_smoke_b8f299f8.json`

The Prime A6000 pod was terminated after evidence was copied and hash-checked; no paid pod remained active at handoff.
