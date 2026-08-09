# Exact exhaustive fast-target miss

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

## Change

The vectorized nearest-target selector applies the scalar scan's broad target
eligibility, attack plane, pending-projectile reservation, target category,
sight geometry, and optional Crown fallback filters. Attacker mechanics are
the only remaining validation and can only reject a broad candidate. When the
vector selector returns `None`, the later scalar scan therefore cannot find a
legal target and is skipped. A non-null vector candidate still passes through
the existing scalar mechanics validation and falls back to the scalar scan if
rejected, preserving alternative-target selection.

The change is shared and data-driven. It has no card-name or enabled-deck
branch and does not change target ordering, actions, observations, rewards, or
RNG use.

## Clean bounded benchmarks

Machine: Apple M4 Pro, 24 GiB RAM, macOS 26.5.2 arm64, Python 3.12.13. The
seed-63 population and its seven evaluation workers had exited. A ten-second
quiet interval and a full-argument process guard immediately before every run
verified that no Clasher training, evaluation, DAgger, or multiprocessing
worker was live. All measurements were single-process CPU runs with no MPS
work.

Crowded-engine command:

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_fast_target_exhaustive_none.py \
  --seed 2301 --card Knight --per-side 12 --ticks 64 --repetitions 11
```

The driver warms the exact dense route cache and alternates baseline/candidate
ordering on every repetition.

| mode | median seconds | mean seconds | stdev | median ticks/s |
| --- | ---: | ---: | ---: | ---: |
| scalar fallback after miss | 0.181929 | 0.181938 | 0.000500 | 351.786393 |
| exhaustive early return | 0.163407 | 0.163251 | 0.000789 | 391.660488 |

This is **+11.33%** crowded-engine throughput and a 10.18% wall-time reduction.
Candidate was faster in all eleven matched pairs; the paired gain median was
11.38%, with 0.66 percentage-point sample stdev. All 22 measured rows
produced exact battle hash
`d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`.

Production-shaped stationary rollouts used the existing benchmark driver with
seed 2301, one environment, 64 decisions, seven repetitions, eight warmup
decisions, two Torch threads, and the exact fast path. The benchmark selected
the baseline or candidate through `_FAST_TARGET_NONE_IS_EXHAUSTIVE` before
collecting each matched run.

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_stationary_rollout.py \
  --workload random --seed 2301 --num-envs 1 --rollout-steps 64 \
  --repetitions 7 --warmup-steps 8 --torch-threads 2 \
  --engine-fast-path on

PYTHONPATH=src:. uv run python scripts/perf/benchmark_stationary_rollout.py \
  --workload strategy --strategy balanced --seed 2301 --num-envs 1 \
  --rollout-steps 64 --repetitions 7 --warmup-steps 8 --torch-threads 2 \
  --engine-fast-path on
```

| workload | baseline seconds | candidate seconds | baseline decisions/s | candidate decisions/s | gain |
| --- | ---: | ---: | ---: | ---: | ---: |
| stationary random | 0.532768 | 0.517851 | 120.127429 | 123.587772 | +2.88% |
| balanced strategy | 0.570187 | 0.563342 | 112.243779 | 113.607669 | +1.22% |

Both random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`.
Both strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Exactness gates

The dedicated regression covers both Crown-fallback modes and proves that a
non-null vector candidate rejected by attacker mechanics still yields a
farther legal scalar alternative. Additional gates:

```text
48 exhaustive-miss/spatial-target/target-switch/action-mask/scalar-shadow tests passed
26 enabled-deck target geometry, sight, ordering, tie, and cache tests passed
pinned scalar/off, shadow, and optimized/on rollout digest unchanged
shadow checks > 0; shadow mismatches = 0
Ruff clean for owned test/benchmark and changed code excluding inherited findings
py_compile and git diff --check clean
```

Integration is an isolated cherry-pick affecting only the shared target
selection path, its direct test, the bounded benchmark, and this report.
