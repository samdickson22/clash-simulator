# Preferred-first exact Crown fallback distance

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

Depends on: `ccab160`, `e1ee425`

## Change

The Crown fallback path validated exact candidates, computed adjusted native
distance for every surviving Princess/King tower, and only then applied the
existing data-driven Crown preference. With the current globals, the preference
usually retains one lane's Princess Tower and excludes the opposite Princess
and King before distance can affect selection.

The fallback now applies the unchanged preference first and computes adjusted
distance only for retained objectives. The reference path remains selectable in
the benchmark driver. Candidate validation, preference inputs/order, native
distance, final tie selection, actions, battle state, and RNG are unchanged.
There are no card-name, deck, policy, reward, or enabled-interaction branches.

## Machine and controls

- Apple M4 Pro, 24 GiB RAM
- macOS 26.5.2 arm64
- Python 3.12.13
- single-process CPU only; no MPS/GPU, training, checkpoint, or corpus write
- fixed battle seed 2301 and oracle seed 901
- executable-prefix process guard before and after accepted commands
- continuous 30-second Clasher quiescence window before the oracle A/B

## Exact oracle labels

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_oracle_preferred_crown_distance.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 5 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

The driver alternates eager/preferred-first order across five matched
repetitions. Its digest includes before/after planner state keys, both action
labels, battle RNG before/after each label, and complete final planner RNG.

| distance order | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| eager for every valid Crown | 1.183104 | 1.182510 | 0.002848 | 2.535702 |
| preferred Crowns only | 1.160115 | 1.159822 | 0.001352 | 2.585951 |

Preferred-first distance improves exact oracle throughput by **1.98%** and
reduces wall time by 1.94%. All ten rows produced digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.

## Production-shaped stationary rollouts

Each command used one environment, 64 decisions, seven repetitions after two
untimed warmup decisions, two Torch threads, exact fast mode, and all preceding
optimizations enabled.

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_stationary_rollout.py \
  --workload random --seed 2301 --num-envs 1 --rollout-steps 64 \
  --repetitions 7 --warmup-steps 2 --torch-threads 2 \
  --engine-fast-path on --target-cache-refresh reuse \
  --building-cache-refresh reuse --targetability-refresh classified \
  --crown-fallback-membership cached \
  --crown-distance-order {eager,preferred-first}

# Repeat with --workload strategy --strategy balanced.
```

| workload | eager seconds / decisions/s | preferred seconds / decisions/s | gain |
| --- | ---: | ---: | ---: |
| stationary random | 0.430365 / 148.711064 | 0.423403 / 151.156197 | **+1.64%** |
| balanced strategy | 0.501815 / 127.537147 | 0.496746 / 128.838567 | **+1.02%** |

Random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Crowded exact engine

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_crowded_engine.py \
  --seed 2301 --card Knight --per-side 12 --ticks 64 --repetitions 11 \
  --mode on --clear-route-cache-per-mode --target-cache-refresh reuse \
  --building-cache-refresh reuse --targetability-refresh classified \
  --crown-fallback-membership cached \
  --crown-distance-order {eager,preferred-first}
```

| distance order | median seconds / 64 ticks | ticks/s |
| --- | ---: | ---: |
| eager | 0.124328 | 514.768772 |
| preferred-first | 0.123837 | 516.809775 |

Crowded throughput improves by **0.40%** with unchanged state digest
`d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`.

## Exactness gates

```text
105 target/collision/action-mask/clone/batched/determinism focused tests passed
622 enabled troop-interaction tests passed
direct left/center/right fallback cases prove identical targets
direct attribution proves one distance call for a one-lane preferred result
off/shadow/on fixed-seed hashes unchanged; shadow mismatches = 0
canonical scalar/shadow/on digest remains
  6580da7847703ca63be431ab815c494c419abd39f439557dd3f9418c8e3a464e
new test and oracle driver Ruff/py_compile clean
git diff --check clean
```

## Integration

Cherry-pick after `ccab160` and `e1ee425`. The source change is limited to the
`_PREFER_CROWN_FALLBACK_BEFORE_DISTANCE` benchmark switch and the fallback
closure's distance ordering. Existing stationary/crowded drivers only gain the
`--crown-distance-order` selector. No battle cache schema changes are introduced
by this commit.
