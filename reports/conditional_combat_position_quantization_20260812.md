# Conditional combat position quantization

Date: 2026-08-12

Commit baseline: `53f988f`

## Change

The native component loop formerly rounded every live troop and building back
to the logic-unit grid after its combat component, including the common case
where combat did not change either coordinate. The candidate snapshots the two
coordinates and performs the same publication only when a combat hook moved
the entity. This is shared engine behavior: it is independent of card name,
deck, collision plane, or enabled-card membership.

A focused test covers both contracts. Stationary combat skips the redundant
calls, while a synthetic combat hook that changes a coordinate executes the
same quantization and produces the same positions as the reference path.

## Machine and resource conditions

- Apple M4 Pro, 12 logical CPUs, 24 GiB RAM
- Darwin 25.5.0 arm64
- CPython 3.12.13
- one process, one Torch thread, CPU only, `nice -n 10`
- no Clasher training/evaluation child, RoadForge solver, or MPS workload was
  active during the matched screens; an old zero-CPU tmux server remained

## Oracle benchmark

Command:

```bash
nice -n 10 .venv/bin/python \
  scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison conditional-combat-quantization \
  --seed 9037 --planner-seed 2037 --states 2 --state-stride 4 \
  --repetitions 11 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

This used 11 alternating matched pairs after one warmup label per mode.

| mode | median seconds / 2 labels | median labels/s |
| --- | ---: | ---: |
| per-entity publication | 1.188075 | 1.683396 |
| conditional publication | 1.182127 | 1.691866 |

- ratio-of-medians gain: **+0.503%**
- paired gain: **+0.701% median**, +0.599% mean
- positive pairs: 10/11
- bootstrap 95% CI for paired mean: +0.294% to +0.928%
- exact action/state/planner digest in every row:
  `c4946197e9b5e0114d290433e64c2f56bd21e090b672034898c8851825052bd8`

## Stationary rollout benchmarks

Commands:

```bash
nice -n 10 .venv/bin/python \
  scripts/perf/benchmark_conditional_combat_quantization_rollout.py \
  --workload random --seed 9079 --num-envs 4 --rollout-steps 24 \
  --warmup-steps 4 --repetitions 15 --max-ticks 2048

nice -n 10 .venv/bin/python \
  scripts/perf/benchmark_conditional_combat_quantization_rollout.py \
  --workload strategy --strategy balanced --seed 9079 --num-envs 4 \
  --rollout-steps 24 --warmup-steps 4 --repetitions 15 \
  --max-ticks 2048
```

Each workload used 15 alternating matched pairs, defense-v2, optimized/on,
preallocated observation buffers, stationary-opponent mask reuse, and one
Torch thread.

| workload | reference median decisions/s | candidate median decisions/s | ratio gain | paired median | positive pairs | paired mean 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| random | 192.1647 | 192.8948 | +0.380% | +0.106% | 9/15 | -0.657% to +0.832% |
| balanced strategy | 185.1866 | 185.8799 | +0.374% | +0.395% | 12/15 | +0.013% to +0.513% |

Random digest in every row:
`fa65e723d3adff600957bd4ea9692c917348470267241eb1c7bb61fca2bdca4c`.
Strategy digest in every row:
`8c61ececcf2a9d28d7c447d3efc3339f16d9c8ba7b37e653f2414c84ade3a040`.
The random result is recorded as exact but noisy; the oracle and balanced
strategy screens provide the attributable evidence.

## Exactness and focused gates

The fixed seed-2301, 64-decision, 8-tick, max-ticks-2048 defense-v2 rollout was
run twice for each reference/candidate pair in scalar/off, shadow, and
optimized/on modes. All 12 runs produced:

`9f190f2efd15954d8105db43b2352e8b50c1bafd3fea9f2921964c6123389349`

Shadow recorded one action-mask comparison per trial and zero mismatches.

Focused gates: 104 tests passed across the new branch test, target switching,
spatial targeting, sight/reach, exact oracle traces, collision broadphase,
fast target selection, action masks, pathing, and hover traits. Ruff passes for
the owned test and benchmark files. `battle.py` retains its pre-existing Ruff
and mypy backlog; the candidate introduced no new reported line.
