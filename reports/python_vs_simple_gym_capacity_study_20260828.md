# Python versus resident Simple Gym capacity study

## Decision

The resident PyTorch rewrite is not intrinsically slower than the original
Python object gym. Its hidden performance failure is the fixed 128-entity dense
working set. CUDA Graph execution with a bounded 48-entity/64-effect contract is
currently the best safety/performance candidate:

- 2,666.05 raw row-ticks/s on one RTX A6000;
- 9.33x the same pod's Python exact-mask rate;
- approximately 1.65x the M4 Pro's matched Python exact-mask rate; and
- four distinct full-match seeds, replayed twice, deterministic, terminal,
  fully native, fully committed, and zero-fallback.

Capacity 48 is not yet proven sufficient for every possible 33-deck matchup or
pathological crowd. The production default therefore remains 128. Fresh
Simple-Gym training now accepts explicit `--simple-max-entities` and
`--simple-max-effects` values and persists both in checkpoint metadata, making
48/64 a fail-closed experimental contract rather than a hidden default change.

## Matched benchmark contract

Commit `a92ec01f` adds a three-arm AB/BA harness:

1. original Python structured observation plus exact fast action mask;
2. Python structured observation plus public-mask-v2; and
3. resident Simple PyTorch projected observation/mask/tick.

All arms use the same 33-deck supported pool, first-legal actions for both
actors, one native battle tick per row, and no neural policy inference.
Construction, reset, warm-up, digest replay, and report serialization are
outside the measured window. Each backend must reproduce one deterministic
digest across repetitions. The projected Simple semantics are deliberately not
claimed byte-identical to the Python debug oracle.

## M4 Pro MPS results

Batch 128, ten measured ticks, five repetitions at capacity 128:

| Backend | Median row-ticks/s | Relative to Python exact |
|---|---:|---:|
| Python exact fast mask | 1,615.77 | 1.00x |
| Python public-mask-v2 | 3,160.95 | 1.96x |
| Simple MPS, 128/128 | 84.00 | 0.052x |

Simple MPS capacity sweep, batch 128:

| Entities/effects | Median row-ticks/s | Change from 128/128 |
|---|---:|---:|
| 16/16 | 851.41 | 10.14x |
| 32/32 | 811.78 | 9.66x |
| 64/64 | 451.08 | 5.37x |
| 128/128 | 84.00 | 1.00x |

Even at 16/16, MPS remains slower than Python on the M4. MPS remains useful
for functional testing and local bounded fitting, but it is not the production
simulation backend.

## A6000 CUDA Graph results

Matched batch-128 results include Python timing on the same six-vCPU pod:

| Entities/effects | Simple row-ticks/s | Pod Python exact | Same-host speedup |
|---|---:|---:|---:|
| 32/32 | 3,974.91 | 280.18 | 14.19x |
| 64/64 | 1,816.34 | 285.86 | 6.35x |
| 128/128 | 416.18 | 300.12 | 1.39x |

The M4 is a much stronger Python host than the rented six-vCPU pod. Comparing
CUDA against the matched M4 Python median gives approximately 2.46x at 32/32,
1.12x at 64/64, and 0.26x at 128/128.

## Entity versus effect attribution

Short CUDA Graph probes isolate the two padded dimensions:

| Entities/effects | Median row-ticks/s |
|---|---:|
| 32/128 | 3,328.45 |
| 48/64 | 2,666.05 |
| 128/32 | 496.99 |
| 128/128 | 416.18 |

Shrinking effects from 128 to 32 while retaining 128 entities buys only about
19%. Shrinking entities from 128 to 32 while retaining 128 effects buys about
8.0x. Entity-wide and entity-pair dense work is the dominant target.

## Full-match capacity evidence

Capacity 32/32 passed seed 202608282 twice under first-legal CUDA Graph play,
ending at tick 3363 by regulation crown with deterministic digest, native and
committed counts equal to row ticks, and zero fallback.

Capacity 48/64 passed four seeds (202608282 through 202608285), each replayed
twice. Accepted terminal ticks were 3363, 3600, 3600, and 3600. All acceptance
fields are true. This covers eight complete executions but samples only four
deck pairs; it is not exhaustive crowd-capacity proof.

## Next engineering step

Use explicit 48/64 capacity for a fresh CUDA Graph training pilot, guarded by:

- hard capacity rejection and persisted checkpoint metadata;
- a larger deck/matchup peak-occupancy audit;
- zero fallback/native/committed counters;
- deterministic episode digests; and
- comparison against the promoted Hog champion under free-running gameplay.

Longer term, group environments into 32/48/64/128 capacity buckets selected
from deck-pair admission evidence. A single 128-wide runtime should be reserved
for genuinely crowded matchups rather than charging every row its cost.

## Training-route smoke

The explicit 48/64 contract completed one real fresh PPO update on MPS with a
494-token recurrent policy. The run used two environments, four actors, one
rollout decision, four transitions, and one optimizer epoch. Collection took
2.41 seconds and learning 2.03 seconds; the saved checkpoint SHA-256 was
`a35f486845b50ba2f0183abd2e5f2245f0ba38456f7aa56a05a2db2a0304bccf`.
Reloaded metadata asserted:

```text
model_config.max_entities=48
simulation_backend_metadata.max_entities=48
simulation_backend_metadata.max_effects=64
backend_id=simple-pytorch-gym-v1
execution_mode=eager
total_transitions=4
```

This proves the MPS trainer/collector/checkpoint route, not useful learning or
MPS production throughput.

## Production recurrent collector

The final production-shaped benchmark includes the default 2.61M-parameter
recurrent policy, public-mask-v2, eight native ticks per decision, recurrent
state, reward/outcome handling, and the PPO NumPy handoff. Batch size is 128,
rollout length is eight decisions, and each arm has three deterministic trials.

| Device | Capacity | Median actor decisions/s | Capacity gain |
|---|---:|---:|---:|
| MPS eager | 128/128 | 20.63 | 1.00x |
| MPS eager | 48/64 | 143.83 | 6.97x |
| A6000 CUDA Graph | 128/128 | 101.77 | 1.00x |
| A6000 CUDA Graph | 48/64 | 629.30 | 6.18x |

The 48/64 CUDA collector alone exceeds the historical Python trainer's full
255--360 learner-decision/s range, but that is not an end-to-end comparison
because this collector timer excludes PPO learning. The sweep below supplies
the comparable complete-update number. The capacity gain itself survives every
production collector boundary; it is not a raw tick-only artifact.

## PPO learner batch sweep

Two-update CUDA smokes used the same 128 environments, 48/64 runtime, eight
rollout decisions, four PPO epochs, 2.61M-parameter policy, and seed. Only the
sequence minibatch changed. Values below are update-two checkpoint metrics.

| Sequence batch | Optimizer steps | Collect | Learn | Total transitions/s | KL | Clip |
|---:|---:|---:|---:|---:|---:|---:|
| 8 | 128 | 3.32 s | 15.55 s | 108.55 | 0.00152 | 0.0249 |
| 32 | 32 | 3.31 s | 4.04 s | 278.62 | 0.00148 | 0.0245 |
| 64 | 16 | 3.31 s | 2.49 s | 352.70 | 0.00104 | 0.0137 |
| 128 | 8 | 3.33 s | 1.85 s | 395.40 | 0.00061 | 0.0044 |

The simulator is no longer the only dominant phase: at sequence batch eight,
learning consumes 82% of update wall time. Batch 64 is the recommended first
real-training arm because it retains 16 optimizer steps while reaching the top
of the historical Python throughput range. Batch 128 is a throughput ceiling,
not yet a learning-quality recommendation; it needs matched multi-update
sample-efficiency and gameplay gates.
