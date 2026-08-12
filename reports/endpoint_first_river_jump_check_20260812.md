# Endpoint-first river-jump walkability check

Date: 2026-08-12

Baseline: `f13706d`

## Change and exactness argument

Ordinary ground movement previously tested the current position's
walkability, then the proposed endpoint's walkability, before considering a
river jump. The predicate is:

```text
current is walkable and endpoint is not walkable
```

The candidate evaluates the pure endpoint query first. Boolean semantics are
unchanged, but the common walkable-endpoint case now short-circuits after one
query instead of evaluating both terrain/building predicates. The same
`_try_start_river_jump` call remains behind the same conjunction. This is
shared movement logic with no card, deck, route, or enabled-card special case.

A focused test proves one query instead of two for a walkable move and the
same two queries, position, and jump decision at an unwalkable boundary.

## Machine and resource conditions

- Apple M4 Pro, 12 logical CPUs, 24 GiB RAM
- Darwin 25.5.0 arm64
- CPython 3.12.13
- one CPU process, one Torch thread, `nice -n 10`, no MPS/GPU
- no Clasher training/evaluation child or RoadForge solver was active; the
  old zero-CPU Clasher tmux server remained

## Exact oracle

Command:

```bash
nice -n 10 .venv/bin/python \
  scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison endpoint-first-river-jump-check \
  --seed 9127 --planner-seed 2127 --states 2 --state-stride 4 \
  --repetitions 11 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

Eleven alternating matched pairs ran after one warmup label per mode.

| mode | median seconds / 2 labels | median labels/s |
| --- | ---: | ---: |
| origin-first | 0.417424 | 4.791289 |
| endpoint-first | 0.406562 | 4.919301 |

- ratio-of-medians gain: **+2.672%**
- paired gain: **+2.405% median**, +2.794% mean
- positive pairs: **11/11**
- bootstrap paired-mean 95% CI: **+2.117% to +3.528%**
- exact action/state/planner digest in every row:
  `8d3d9dcf461ce641fc8166a50fdaa1a052985550268f01d63a835b3615551dd3`

## Stationary rollouts

Commands:

```bash
nice -n 10 .venv/bin/python \
  scripts/perf/benchmark_conditional_combat_quantization_rollout.py \
  --comparison endpoint-first-river-jump-check --workload random \
  --seed 9127 --num-envs 4 --rollout-steps 24 --warmup-steps 4 \
  --repetitions 15 --max-ticks 2048

nice -n 10 .venv/bin/python \
  scripts/perf/benchmark_conditional_combat_quantization_rollout.py \
  --comparison endpoint-first-river-jump-check --workload strategy \
  --strategy balanced --seed 9127 --num-envs 4 --rollout-steps 24 \
  --warmup-steps 4 --repetitions 15 --max-ticks 2048
```

Each workload used 15 alternating matched pairs, defense-v2, optimized/on,
preallocated observation buffers, stationary-opponent mask reuse, and one
Torch thread.

| workload | reference decisions/s | candidate decisions/s | ratio gain | paired median | positive pairs | paired mean 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| random | 210.2886 | 213.0067 | **+1.293%** | **+1.079%** | 12/15 | +0.086% to +1.794% |
| balanced strategy | 200.5619 | 202.1582 | **+0.796%** | **+0.842%** | 13/15 | +0.149% to +1.783% |

Random digest in every row:
`88ed3bf1903c32054d970fae32e9497cd1b45f5d7052541788aecdae11fcb598`.
Strategy digest in every row:
`f2e1ecd089aef9dc5ed792c9a054f2f3097c6673b8224214edc699099b653ee6`.

## Parity and focused gates

The fixed seed-2301, 64-decision, 8-tick, max-ticks-2048 defense-v2 rollout
was run twice for each origin-first/endpoint-first pair in scalar/off, shadow,
and optimized/on modes. All 12 runs produced:

`9f190f2efd15954d8105db43b2352e8b50c1bafd3fea9f2921964c6123389349`

Shadow performed one action-mask comparison per trial with zero mismatches.
Seven hundred one focused tests passed across the new query-order test,
enabled troop interactions, river/bridge/pathing, hover traits, targeting,
collision, action masks, and exact oracle traces. Ruff passes for all owned
test and benchmark files; shared legacy modules retain only their pre-existing
lint/type backlog.
