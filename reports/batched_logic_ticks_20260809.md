# Exact decision-window tick batching

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

## Change

Every native tick must refresh the fast caches at its start because the
preceding object phase can change movement and targetability. Repeated public
`BattleState.step()` calls also publish the same caches at every tick end so an
external caller can inspect the battle immediately. Inside a closed 8-tick RL
or oracle decision window, no external code runs between ticks. The candidate
therefore keeps every start refresh and explicit in-component synchronization,
but defers the redundant end publication until the final tick in the window.

Public one-tick `step()` behavior is unchanged. `step_logic_ticks()` returns the
exact number advanced and republishes all fast caches before returning, including
after early game termination. The shared self-play environment and allocation-
lean oracle use this primitive. There are no card-name or enabled-deck branches.

## Clean bounded benchmarks

Machine: Apple M4 Pro, 24 GiB RAM, macOS 26.5.2 arm64, Python 3.12.13. The
population/evaluation workers had exited, followed by a ten-second quiet
interval. A full-argument process guard before every command rejected live
training, evaluation, DAgger, or multiprocessing workers. All measurements
were single-process CPU runs with no MPS work.

### Crowded engine

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_batched_logic_ticks.py \
  --seed 2301 --card Knight --per-side 12 \
  --windows 8 --ticks-per-window 8 --repetitions 11
```

| mode | median seconds | mean seconds | stdev | median ticks/s |
| --- | ---: | ---: | ---: | ---: |
| repeated public step | 0.163974 | 0.163989 | 0.000700 | 390.304690 |
| batched decision windows | 0.161825 | 0.162192 | 0.000918 | 395.489565 |

This is +1.33% throughput and a 1.31% wall-time reduction. Ten of eleven
matched pairs favored the candidate; the paired median gain was 1.17%. All 22
rows produced exact battle hash
`d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`.

### Production-shaped stationary rollouts

The existing rollout driver used seed 2301, one environment, 64 decisions,
eleven repetitions, eight warmup decisions, two Torch threads, and the exact
fast path. Baseline installs the reference repeated-step helper; candidate uses
`BattleState.step_logic_ticks`.

| workload | baseline seconds | candidate seconds | baseline decisions/s | candidate decisions/s | gain |
| --- | ---: | ---: | ---: | ---: | ---: |
| stationary random | 0.529634 | 0.525466 | 120.838202 | 121.796614 | +0.79% |
| balanced strategy | 0.572869 | 0.569503 | 111.718483 | 112.378606 | +0.59% |

Both random variants produced
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`.
Both strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

### Production-shape oracle

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_oracle_tick_batch.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 5 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

The three fixed snapshots include the initial state and two deterministic
random-action successors. Reference/candidate ordering alternates. The digest
includes before/after planner state keys, selected joint actions, complete input
battle RNG before and after each label, and the complete final planner RNG.

| mode | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| repeated public step | 1.933757 | 1.935685 | 0.004356 | 1.551384 |
| batched decision windows | 1.886077 | 1.887850 | 0.005971 | 1.590603 |

The candidate improves exact oracle label throughput by **2.53%** and reduces
wall time by 2.47%. All ten rows produced digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.

## Exactness gates

The direct test compares repeated and batched ticks across public player/entity
state, complete Python RNG state, all eleven NumPy target-cache arrays, target
membership/order, and spatial bucket membership. It also compares baseline and
candidate rollouts in scalar/off, shadow, and optimized/on modes, and compares
fixed oracle actions plus complete planner/input-battle RNG state.

```text
5 direct batching exactness tests passed
64 batching/targeting/collision/action-mask/scalar-shadow/oracle tests passed
fixed scalar/off, shadow, and optimized/on hashes unchanged
shadow mismatches = 0
Ruff clean for owned tests and benchmark drivers
selfplay_env.py and oracle_direct_path.py mypy clean
py_compile and git diff --check clean
```

## Integration

Cherry-pick the isolated commit, resolving only the small `battle.py` and
`selfplay_env.py` hunks if the training branch has nearby inherited edits. The
authoritative planner has already folded direct-path logic into
`oracle_planner.py`; replace its eight-call `battle.step()` loop with
`battle.step_logic_ticks(self.decision_interval_ticks)`, matching the included
`oracle_direct_path.py` hunk. No CLI, corpus fingerprint, reward, action,
observation, RNG, or checkpoint-format change is required.
