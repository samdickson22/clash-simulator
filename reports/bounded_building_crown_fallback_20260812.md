# Range-bounded building Crown fallback

Date: 2026-08-12

Baseline: `fce4d8d`

## Change and exactness argument

Immobile buildings previously requested the target selector's infinite-sight
Crown fallback whenever their current target was invalid, then immediately
discarded any returned Crown that was outside attack range. The candidate
disables that fallback when:

```text
attack range <= sight range + Crown sight extension
```

Both exact reach calculations add the same target collision radius and the
same geometry epsilon. Therefore every Crown that can be attacked under this
condition is already in the ordinary sight candidate set. A building whose
serialized attack reach can exceed Crown visibility retains the fallback.
This is driven only by shared ranges and balance globals; it contains no card
name, deck, or enabled-card special case.

Focused tests cover an ordinary building whose unreachable fallback is
skipped and a synthetic long-range building that still acquires an
out-of-sight but attackable Crown identically.

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
  --comparison bounded-building-crown-fallback \
  --seed 9091 --planner-seed 2091 --states 2 --state-stride 4 \
  --repetitions 11 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

Eleven alternating matched pairs ran after one warmup label per mode.

| mode | median seconds / 2 labels | median labels/s |
| --- | ---: | ---: |
| unbounded fallback | 1.317193 | 1.518381 |
| range-bounded fallback | 1.267259 | 1.578209 |

- ratio-of-medians gain: **+3.940%**
- paired gain: **+3.859% median**, +3.920% mean
- positive pairs: **11/11**
- bootstrap 95% CI for paired mean: **+3.241% to +4.453%**
- exact action/state/planner digest in every row:
  `d0e7f7a4298210a0272a8ba6fae50330164010f7ac6f957dfe6108a085494b2d`

## Stationary rollouts

Commands:

```bash
nice -n 10 .venv/bin/python \
  scripts/perf/benchmark_conditional_combat_quantization_rollout.py \
  --comparison bounded-building-crown-fallback --workload random \
  --seed 9091 --num-envs 4 --rollout-steps 24 --warmup-steps 4 \
  --repetitions 15 --max-ticks 2048

nice -n 10 .venv/bin/python \
  scripts/perf/benchmark_conditional_combat_quantization_rollout.py \
  --comparison bounded-building-crown-fallback --workload strategy \
  --strategy balanced --seed 9091 --num-envs 4 --rollout-steps 24 \
  --warmup-steps 4 --repetitions 15 --max-ticks 2048
```

Each workload used 15 alternating matched pairs, defense-v2, optimized/on,
preallocated observation buffers, stationary-opponent mask reuse, and one
Torch thread.

| workload | reference decisions/s | candidate decisions/s | ratio gain | paired median | positive pairs | paired mean 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| random | 175.5578 | 178.7997 | **+1.847%** | **+1.859%** | 15/15 | +1.756% to +3.137% |
| balanced strategy | 180.0910 | 182.7522 | **+1.478%** | **+2.208%** | 14/15 | +1.281% to +3.136% |

Random digest in every row:
`5a7db7049ea8f86e7a91bad47c45f17186b56dfbdb2a4cb44540f15c67c1df1c`.
Strategy digest in every row:
`c43a7e82897bb4de8c18d1c161fc0bd668c34b7e5e18f8e418b7b2d0c79c827d`.

## Parity and focused gates

The fixed seed-2301, 64-decision, 8-tick, max-ticks-2048 defense-v2 rollout
was run twice for each unbounded/bounded pair in scalar/off, shadow, and
optimized/on modes. All 12 runs produced:

`9f190f2efd15954d8105db43b2352e8b50c1bafd3fea9f2921964c6123389349`

Shadow performed one action-mask comparison per trial with zero mismatches.
One hundred six focused tests passed across the new boundary test, targeting,
collision, action masks, pathing, hover traits, and exact oracle traces. Ruff
passes for all owned test/benchmark files; shared legacy modules retain only
their pre-existing lint/type backlog.
