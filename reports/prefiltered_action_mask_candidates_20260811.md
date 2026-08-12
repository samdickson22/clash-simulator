# Exact prefiltered action-mask candidates

Date: 2026-08-11

## Result

The fast action-mask builder now treats two already-exact vector candidate
sets as authoritative:

- enemy-side deployers do not repeat blocked-tile and live-tower checks after
  `non_blocked & ~tower_mask` selected their tiles;
- territory-constrained spell payloads do not repeat `can_deploy_at` after the
  cached deployment-zone and non-blocked masks selected their tiles.

Spell payloads with an additional `requires_walkable_target` capability still
use the scalar validator. The optimization is selected only by shared card and
spell metadata; it contains no card-name or enabled-deck special case.

The pre-change production profile
`/tmp/clasher_strategy_b71a045.prof` attributed 8,016 repeated
`is_tower_tile` calls and 17,408 repeated `can_deploy_at` calls to the fast mask
loop in 656 action-mask builds. Focused tests monkeypatch those redundant
queries to fail while proving that the walkability-dependent path is retained.

## Environment and protocol

- Apple M4 Pro, 12 physical/logical CPU cores, 24 GiB RAM
- macOS 26.5.2 build 25F84
- Python 3.12.13
- single process at `nice -n 15`
- `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`,
  `VECLIB_MAXIMUM_THREADS=1`, and Torch limited to one thread
- fixed seeds, warmups outside reported rows, alternating paired order
- 11 repetitions per variant and nonparametric bootstrap mean 95% intervals
- no Clasher or RoadForge worker was active during the timing series

## Exact oracle screen

Output: `/tmp/prefiltered_action_candidates_oracle.json`

```sh
nice -n 15 env PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 .venv/bin/python \
  scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison prefiltered-action-candidates --seed 2301 \
  --planner-seed 901 --states 3 --state-stride 4 --repetitions 11 \
  --decision-interval 8 --planner-depth 6 --planner-simulations 32 \
  --planner-action-samples 64 --engine-fast-path on
```

| Variant | Median seconds / 3 labels | Median labels/s |
| --- | ---: | ---: |
| repeated scalar checks | 1.049295 | 2.859061 |
| authoritative prefilter | 1.038315 | 2.889297 |

- paired gain: **+1.172% median, +1.327% mean**
- positive pairs: **11/11**
- mean 95% bootstrap CI: **+0.970% to +1.707%**
- every label/state/planner-RNG hash:
  `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`

## Production-shaped stationary rollouts

Outputs: `/tmp/prefiltered_action_candidates_strategy.json` and
`/tmp/prefiltered_action_candidates_random.json`.

```sh
nice -n 15 env PYTHONPATH=src:. OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  VECLIB_MAXIMUM_THREADS=1 .venv/bin/python \
  scripts/perf/benchmark_deployment_blocker_guard_rollout.py \
  --comparison prefiltered-action-candidates --workload WORKLOAD \
  --strategy balanced --seed 2301 --num-envs 8 --rollout-steps 32 \
  --repetitions 11 --warmup-steps 8 --torch-threads 1 \
  --engine-fast-path on --reward-profile defense-v2
```

| Workload | Rechecked median s | Prefiltered median s | Rechecked decisions/s | Prefiltered decisions/s | Paired median gain | Positive | Hash |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| balanced strategy | 1.414153 | 1.397598 | 181.027 | 183.171 | **+1.396%** | 9/11 | `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d` |
| random | 1.443264 | 1.443291 | 177.376 | 177.372 | **-0.002%** | 8/11 | `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a` |

- strategy paired mean: **+1.109%**, mean 95% bootstrap CI
  **+0.202% to +1.926%**
- random paired mean: **+0.879%**, mean 95% bootstrap CI
  **+0.240% to +1.649%**; the median pair was effectively flat
  (**-0.002%**) amid larger rollout noise

## Exactness and gates

- seed 8921, 64 decisions: rechecked/prefiltered digest in scalar/off,
  shadow, and optimized/on was
  `58a90eaab393a97f5f9370245fa8ea790fa67cef09c7b3653804ff908bf05e67`
- pinned seed 8831: all modes produced
  `747f97fcfda1118899b6d42922a191c53914920dd2fe79163395dfba694efe8e`;
  shadow recorded one check for each switch setting and zero mismatches
- 41 focused candidate, action-mask, and sample-deck tests passed
- 3 determinism tests passed
- optimized masks match the scalar mask for every enabled card and both
  canonical player sides
- explicit coverage includes Miner-style metadata, all three enabled
  territory-payload spell classes, and a synthetic future walkability-required
  spell capability
- focused Ruff, `py_compile`, and `git diff --check` pass
- targeted mypy retains only the pre-existing untyped helper at
  `action_space.py:123` plus inherited `battle.py` diagnostics; no changed line
  reports an error
