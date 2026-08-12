# Exact deployment-payload blocker snapshot

## Outcome

The fast legal-action mask now snapshots the exact live, capability-based
deployment blockers once per mask. An empty snapshot skips every per-tile
payload query; a non-empty snapshot is passed to the existing exact occupancy
predicate so it does not rescan all battle entities for every candidate tile.
The snapshot is local to one mask construction, so it introduces no persistent
cache or invalidation surface. No card name is consulted.

This is an exact throughput change. The scalar mask remains the reference and
the public `BattleState.is_deployment_payload_occupied` behavior is unchanged
when the optional snapshot is omitted.

## Machine and coordination

- Apple M4 Pro, 12 logical CPUs, 24 GiB RAM
- macOS 26.5.2 arm64, Python 3.12.13
- all timing commands used one process at `nice -n 15`
- RoadForge production attempt 49 occupied one CPU core during measurement;
  paired order alternated each repetition and the positive-pair counts below
  disclose the remaining shared-host variance
- no MPS/GPU work was launched by this benchmark

## Fixed before/after timing

All rates count decisions, not individual player masks.

| Workload | Fixed configuration | Scan baseline | Guard/snapshot | Paired result |
| --- | --- | ---: | ---: | ---: |
| fast action-mask kernel | seed 2301, 64 decisions, 11 pairs | 0.047466 s, 1,348.34 decisions/s | 0.008450 s, 7,573.70 decisions/s | +468.07% median, 11/11 positive |
| stationary random | 1 env x 64 steps, 11 pairs | 0.404784 s, 158.11 decisions/s | 0.401946 s, 159.23 decisions/s | +0.73% median, 10/11 positive |
| stationary random | 8 envs x 16 steps, 11 pairs | 0.635908 s, 201.29 decisions/s | 0.630153 s, 203.13 decisions/s | +1.05% median, 10/11 positive |
| balanced strategy | 8 envs x 16 steps, 7 pairs | 0.641239 s, 199.61 decisions/s | 0.623841 s, 205.18 decisions/s | +3.38% median, 6/7 positive |
| exact oracle | 3 states, depth 6, 32 sims, 64 samples, 5 pairs | 1.072292 s, 2.7977 decisions/s | 1.062847 s, 2.8226 decisions/s | +1.04% median, 5/5 positive |

The rollout/oracle wall-clock gains are the production attribution; the 5.62x
mask-kernel result only explains the source of that smaller end-to-end gain.

## Exactness evidence

The 256-decision seed-2301 determinism matrix produced the same digest for
scan/guard and scalar/shadow/on:

`be1a849cd1702967db11b8f82050ebc49e3848efeb5e01848740800e875b6888`

Shadow mode performed two sampled scalar comparisons in each scan/guard run and
reported zero mismatches. The matched workload hashes were also identical:

- action-mask kernel: `640614c29015b001128a181630b61456725801db1df3b197edc9109ec9b4c707`
- random 1x64: `1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`
- random 8x16: `6997ecb8893e3b2a0f867d5392ad8fe6bf4743fe87e63008359952996cfb3249`
- strategy 8x16: `d87bdd871c9bb012c55aff818085f7da385061d83e445c632a601bdb23737590`
- exact oracle: `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`

The focused tests cover an empty blocker set, a live timed payload, exact mask
equality, and fixed rollout digests in off/shadow/on modes. The complete shared
engine gate passed 125 action-mask, targeting, collision, hover, and target-
switching tests in 9.92 seconds. Candidate files are bytecode- and Ruff-clean.
Full-file lint/type checks retain only pre-existing findings outside this hunk:
9 `battle.py` Ruff findings, 21 `battle.py` mypy findings, and the existing
untyped `_is_legal_deploy` parameters in `action_space.py`.

## Commands

```bash
nice -n 15 env PYTHONPATH=src:.:scripts/perf uv run python \
  scripts/perf/benchmark_deployment_blocker_guard.py \
  --seed 2301 --decisions 64 --repetitions 11 --warmup-decisions 2

nice -n 15 env PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_rollout.py --workload random --seed 2301 \
  --num-envs 8 --rollout-steps 16 --repetitions 11 --warmup-steps 2 \
  --torch-threads 2 --engine-fast-path on --observation-buffers preallocated \
  --unit-clip scalar --entity-range-clip scalar \
  --deployment-blocker-guard both

nice -n 15 env PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_rollout.py --workload strategy \
  --strategy balanced --seed 2301 --num-envs 8 --rollout-steps 16 \
  --repetitions 7 --warmup-steps 2 --torch-threads 2 \
  --engine-fast-path on --observation-buffers preallocated \
  --unit-clip scalar --entity-range-clip scalar \
  --deployment-blocker-guard both

nice -n 15 env PYTHONPATH=src:.:scripts/perf uv run python \
  scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 5 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on

env PYTHONPATH=src:. uv run pytest -q \
  tests/test_rl_deployment_blocker_guard.py tests/test_rl_action_mask.py \
  tests/test_rl_action_mask_gather.py tests/test_cached_entity_collision_radius.py \
  tests/test_cached_mover_hover_trait.py tests/test_coalesced_target_fallback.py \
  tests/test_coalesced_target_plane_checks.py \
  tests/test_collision_broadphase_parity.py \
  tests/test_collision_bucket_candidates.py tests/test_direct_collision_plane.py \
  tests/test_direct_targetability_fields.py tests/test_fast_target_exhaustive_none.py \
  tests/test_fast_target_small_set.py tests/test_inactive_stealth_targetability.py \
  tests/test_spatial_targeting_parity.py tests/test_static_targetability_cache.py \
  tests/test_target_sight_reach.py tests/test_target_switching.py
```
