# Exact scalar targeting for small fast-path sets

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

## Change

The NumPy nearest-target path has fixed ufunc and temporary-array costs. Exact
oracle states in the measured production shape contained only 6--16 cached
targets, where the existing scalar spatial-bucket selector was faster. The
fast path now uses that already-supported scalar selector below 21 cached
targets and retains vector targeting at 21 or more.

The threshold depends only on the current shared target-cache size. It has no
card-name, deck, player, policy, or mechanic branch. Both selectors use the
same canonical mechanics and ordering; this changes neither observations nor
legal actions and consumes no RNG.

## Crossover measurement

Machine: Apple M4 Pro, 24 GiB RAM, macOS 26.5.2 arm64, Python 3.12.13. All
measurements were single-process CPU runs with no MPS work. A full-command-line
process guard rejected live training, evaluation, DAgger, and multiprocessing
workers immediately before each run. Reference/candidate ordering alternated.

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_target_threshold_sweep.py \
  --seed 2301 --card Knight --per-side 1,2,4,6,7,8,10,12 \
  --ticks 32 --repetitions 5
```

| cached targets | vector median seconds | scalar median seconds | scalar gain |
| ---: | ---: | ---: | ---: |
| 8 | 0.010284 | 0.008116 | +26.71% |
| 10 | 0.016100 | 0.013615 | +18.26% |
| 14 | 0.029424 | 0.026768 | +9.92% |
| 18 | 0.043200 | 0.042050 | +2.73% |
| 20 | 0.048662 | 0.048572 | +0.19% |
| 22 | 0.056007 | 0.057299 | -2.26% |
| 26 | 0.070770 | 0.076947 | -8.03% |
| 30 | 0.087341 | 0.098833 | -11.63% |

Every scalar/vector row at every target count produced an identical final
battle hash. A separate nine-repetition 21-target boundary probe favored the
vector selector by 2.30%, so 21 is the first vectorized count. Instrumenting a
fixed production-shape oracle label observed 11,200 target queries, all with
6--16 cached targets.

## Production-shape oracle

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_oracle_target_threshold.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 5 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --candidate-threshold 21 --engine-fast-path on
```

The three fixed snapshots include the initial state and deterministic
random-action successors. The digest includes before/after planner state keys,
joint action labels, complete input-battle RNG before/after every label, and
the complete final planner RNG.

| mode | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| vector at every size | 1.942582 | 1.942045 | 0.004394 | 1.544336 |
| scalar below 21 | 1.618408 | 1.617595 | 0.002236 | 1.853673 |

The hybrid improves exact oracle label throughput by **20.03%** and reduces
wall time by 16.69%. All ten rows produced digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.

## Production-shaped stationary rollouts

The wrapper below selects the threshold and delegates to the existing rollout
driver. Runs used seed 2301, one environment, 64 decisions, eleven repetitions,
eight warmup decisions, two Torch threads, and the exact fast path.

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_target_threshold.py \
  --target-vector-min-size {0,21} --workload random --seed 2301 \
  --num-envs 1 --rollout-steps 64 --repetitions 11 --warmup-steps 8 \
  --torch-threads 2 --engine-fast-path on

PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_target_threshold.py \
  --target-vector-min-size {0,21} --workload strategy --strategy balanced \
  --seed 2301 --num-envs 1 --rollout-steps 64 --repetitions 11 \
  --warmup-steps 8 --torch-threads 2 --engine-fast-path on
```

| workload | vector seconds | hybrid seconds | vector decisions/s | hybrid decisions/s | gain |
| --- | ---: | ---: | ---: | ---: | ---: |
| stationary random | 0.505246 | 0.467678 | 126.670916 | 136.846255 | +8.03% |
| balanced strategy | 0.549609 | 0.520313 | 116.446508 | 123.002786 | +5.63% |

Random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Exactness gates

The dedicated regression forces both threshold choices in scalar/off, shadow,
and optimized/on modes for the same 32-decision fixed-seed rollout.

```text
3 dedicated scalar/off, shadow, and optimized/on cases passed
52 target/collision/action-mask/pathfinding exactness tests passed
pinned rollout digests unchanged
shadow checks > 0; shadow mismatches = 0
Ruff and py_compile clean for owned code, tests, and benchmark drivers
git diff --check clean
```

Integration is an isolated cherry-pick affecting only the shared target-path
threshold, its direct parity test, three bounded benchmark drivers, and this
report.
