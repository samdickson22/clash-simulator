# Exact deployment-blocker action-mask guard

Date: 2026-08-11

Machine: Apple M4 Pro, 12 logical CPUs, 24 GiB RAM, arm64, macOS 26.5.2,
Python 3.12.13

Execution: single-process CPU, `nice -n 15`; RoadForge occupied one CPU during the
production-shaped screens. No MPS work was started by this optimizer thread.

## Change

The exact fast action mask now scans live entities once to collect the general
`blocks_deployment` capability. When that ordered tuple is empty, it skips all
per-tile payload-occupancy calls. When it is non-empty, the same ordered tuple is
reused for every queried tile instead of rescanning the complete entity mapping.
The collision geometry, alive/capability checks, insertion order, card stats, and
troop/building radii are unchanged. There are no card-name or deck special cases.

The reference behavior remains selectable through the private benchmark flag
`clasher.rl.action_space._USE_DEPLOYMENT_BLOCKER_GUARD`.

## Fixed before/after evidence

All comparisons alternate reference/candidate order. Percentages below are
paired `100 * (reference_seconds / candidate_seconds - 1)`. The 95% intervals
are deterministic percentile-bootstrap intervals for the paired mean (20,000
resamples, seed 0). Every listed pair favored the candidate and all fixed output
hashes matched within its workload.

| Workload | Fixed config | Reference | Guarded | Paired result |
| --- | --- | ---: | ---: | ---: |
| Empty-blocker fast masks | seed 2301, 128 decision pairs, 11 pairs | 0.092416 s, 1,385.04 pairs/s | 0.016827 s, 7,606.60 pairs/s | median +448.76%, mean +450.47%, 95% CI [+447.25%, +454.37%], 11/11 |
| Live timed-payload fast masks | seed 2301, 64 decision pairs, 11 pairs | 0.067298 s, 951.00 pairs/s | 0.032449 s, 1,972.31 pairs/s | median +107.45%, mean +107.11%, 95% CI [+106.42%, +107.76%], 11/11 |
| Stationary-random RL rollout | seed 2301, 8 envs x 32 steps, 7 pairs, fast path on | 1.260221 s, 203.14 decisions/s | 1.238963 s, 206.62 decisions/s | median +1.49%, mean +2.57%, 95% CI [+0.92%, +4.80%], 7/7 |
| Balanced-strategy RL rollout | seed 2301, 8 envs x 32 steps, 7 pairs, fast path on | 1.215394 s, 210.63 decisions/s | 1.189444 s, 215.23 decisions/s | median +2.11%, mean +3.65%, 95% CI [+2.01%, +6.85%], 7/7 |
| Fixed-depth oracle labels | 3 states, depth 6, 32 sims, 64 action samples, 5 pairs | 1.072292 s, 2.798 labels/s | 1.062847 s, 2.823 labels/s | median +1.04%, mean +1.03%, 95% CI [+0.62%, +1.47%], 5/5 |

The first rollout pair in each seven-pair screen was slower under shared host
load; therefore the paired median is the primary production attribution. Keeping
all pairs still gives a positive paired-mean interval.

An earlier independent matched screen in the source commit reached the same
conclusion with different rollout sizes: random 1 env x 64 was +0.73% paired
median (10/11 positive), random 8 envs x 16 was +1.05% (10/11), and balanced
strategy 8 envs x 16 was +3.38% (6/7). Its scan/candidate hashes matched for
each workload. This second screen is retained as replication rather than mixed
into the fixed 8-env x 32-step attribution above.

Exact workload hashes:

- empty blocker mask: `87dce9035addfb75cdfac39781f1d89aa7a1854e07b9af1487364aababe1f29f`
- live payload mask: `bbb165549c0796452def8f204fe14e7c17033bb9448f949cc2dd5d01d1bc0601`
- stationary-random rollout: `8bcf61259509b1f2f80750fa29ccaf695ba9f11e46b46e2967069d2d90fce432`
- balanced-strategy rollout: `67faf6c5e975db614868686ead0c2515840dfd02729342a228127e837f22844d`
- oracle labels/actions: `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`

## Determinism and parity

The canonical 32-decision random-action determinism trace at seed 9989 produced
the same digest for reference and candidate in scalar/off, shadow, and optimized/on
modes:

`852721d45a01fee27444e613a8c1d7dc1a862d5124747adcb8936dc3dc9e66aa`

Shadow performed one sampled mask comparison with zero mismatches. Dedicated
tests also compare exact masks with no blocker and with a real Balloon timed-death
payload; troop and building placement remain blocked at the payload tile.

The earlier 256-decision seed-2301 determinism matrix independently matched
reference/candidate and off/shadow/on at
`be1a849cd1702967db11b8f82050ebc49e3848efeb5e01848740800e875b6888`,
with two shadow checks and zero mismatches in each shadow run.

The stationary-random collector's shadow mode consumes its environment RNG to
sample parity checks, so its shadow rollout is compared reference-vs-candidate
within mode. The canonical determinism harness uses an independent fixed action
RNG and is the authoritative cross-mode state/action/reward trace above.

## Commands

```sh
nice -n 15 env PYTHONPATH=src:.:scripts/perf uv run python scripts/perf/benchmark_deployment_blocker_guard.py --seed 2301 --decisions 128 --repetitions 11 --warmup-decisions 4
nice -n 15 env PYTHONPATH=src:.:scripts/perf uv run python scripts/perf/benchmark_deployment_blocker_guard.py --seed 2301 --decisions 64 --repetitions 11 --warmup-decisions 2 --live-payload-blocker
nice -n 15 env PYTHONPATH=src:.:scripts/perf uv run python scripts/perf/benchmark_deployment_blocker_guard_rollout.py --workload random --seed 2301 --num-envs 8 --rollout-steps 32 --repetitions 7 --warmup-steps 8 --torch-threads 2 --engine-fast-path on
nice -n 15 env PYTHONPATH=src:.:scripts/perf uv run python scripts/perf/benchmark_deployment_blocker_guard_rollout.py --workload strategy --strategy balanced --seed 2301 --num-envs 8 --rollout-steps 32 --repetitions 7 --warmup-steps 8 --torch-threads 2 --engine-fast-path on
nice -n 15 env PYTHONPATH=src:.:scripts/perf uv run python scripts/perf/benchmark_deployment_blocker_guard_oracle.py --seed 2301 --planner-seed 901 --states 3 --state-stride 4 --repetitions 5 --decision-interval 8 --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 --engine-fast-path on
nice -n 15 env PYTHONPATH=src:. uv run pytest -q tests/test_rl_deployment_blocker_guard.py tests/test_rl_action_mask.py tests/test_rl_action_mask_gather.py tests/test_cached_entity_collision_radius.py tests/test_cached_mover_hover_trait.py tests/test_coalesced_target_fallback.py tests/test_coalesced_target_plane_checks.py tests/test_collision_broadphase_parity.py tests/test_collision_bucket_candidates.py tests/test_direct_collision_plane.py tests/test_direct_targetability_fields.py tests/test_enabled_troop_interactions.py tests/test_fast_target_exhaustive_none.py tests/test_fast_target_small_set.py tests/test_inactive_stealth_targetability.py tests/test_spatial_targeting_parity.py tests/test_static_targetability_cache.py tests/test_target_sight_reach.py tests/test_target_switching.py
```

Focused result: 747 passed in 18.41 seconds. Ruff and `git diff --check` pass for
the touched source, tests, drivers, and report. Mypy reports only the existing
22 legacy errors in `battle.py`/`action_space.py`; none points at a changed line.
