# Deferred exact Crown fallback validation

## Change

The direct native Crown fallback previously validated both Princess objectives
and the King objective before applying serialized horizontal Princess
preference. Native layouts now classify the exact semantic slots first,
validate the horizontally preferred Princess, validate the farther Princess
only if the preferred one is dynamically ineligible, and validate King only
when no Princess remains eligible. A symmetric horizontal tie validates both
Princess objectives and retains the existing adjusted-distance/tie selector.

Every target still passes the complete dynamic targetability, pending
projectile, attacker-mechanic, and air/ground-plane checks before it can be
selected. Unclassified objectives, duplicate King slots, or more than two
Princess slots use the complete compatibility selector. The ordering follows
serialized global mechanics and contains no card-name or enabled-deck branch.

## Profile attribution

The `70d6699` oracle profile `/tmp/clasher_oracle_70d6699.prof` recorded 27,714
direct Crown selections (197 ms cumulative) and 271,909 `_is_valid_target`
calls (243 ms). Native fallback layouts usually need only one of their three
dynamic validations.

## Machine and benchmark method

- Apple M4 Pro, 12 CPU cores, 24 GiB RAM
- macOS 26.5.2 arm64; Python 3.12.13
- single process, `nice -n 15`, one BLAS/OpenMP/VecLib thread
- fixed snapshots, seeds, and alternating eager/deferred order
- 11 matched pairs per workload; deterministic 95% bootstrap interval for the
  paired mean
- direct process inspection found no live Clasher or RoadForge worker

| workload | eager validation | deferred validation | paired median | positive pairs | paired-mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Oracle, 3 labels | 3.47563 labels/s | 3.53457 labels/s | +1.6950% | 11/11 | +1.3650% to +1.7934% | `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9` |
| Strategy rollout, 256 decisions | 207.73597 decisions/s | 208.38823 decisions/s | +0.3830% | 11/11 | +0.2790% to +1.4127% | `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d` |
| Random rollout, 256 decisions | 201.53690 decisions/s | 202.47704 decisions/s | +0.4683% | 10/11 | +0.2648% to +1.6058% | `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a` |

The first rollout pair was a wider roughly 4% host/cold outlier. Attribution
uses the paired medians, not the larger means.

## Commands

```bash
nice -n 15 env PYTHONPATH=src:.:scripts/perf \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv/bin/python scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison deferred-crown-validation --seed 2301 --planner-seed 901 \
  --states 3 --state-stride 4 --repetitions 11 --decision-interval 8 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on

nice -n 15 env PYTHONPATH=src:. \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv/bin/python scripts/perf/benchmark_deployment_blocker_guard_rollout.py \
  --comparison deferred-crown-validation --workload WORKLOAD \
  --strategy balanced --seed 2301 --num-envs 8 --rollout-steps 32 \
  --repetitions 11 --warmup-steps 8 --torch-threads 1 \
  --engine-fast-path on --reward-profile defense-v2
```

Raw clean outputs:

- `/tmp/deferred_crown_validation_oracle.json`
- `/tmp/deferred_crown_validation_strategy.json`
- `/tmp/deferred_crown_validation_random.json`

## Exactness gates

- Seed 8981, 64 decisions, eager/deferred scalar/off, shadow, and optimized/on
  digest
  `d5fa766676707859a5debab488e74f9e3f89d26f32994311b52e668a762b32fa`.
- Seed 8831, 64 decisions, eager/deferred scalar/off, shadow, and optimized/on
  digest
  `747f97fcfda1118899b6d42922a191c53914920dd2fe79163395dfba694efe8e`,
  with one comparison and zero shadow mismatches per mode.
- Direct validation-count tests prove native valid-near checks one Princess,
  invalid-near checks both Princesses, and both-invalid checks King last.
  Existing direct/listed tests cover left/right/center positions and every
  dead native Crown slot; custom unclassified objectives retain fallback.
- 790 Crown, targetability, targeting, target switching, action-mask, clone,
  enabled-interaction, and determinism tests passed in 11.72 seconds.
- New tests and benchmark drivers are Ruff-clean; all changed Python files
  compile; `git diff --check` is clean.
- `entities.py` retains exactly its inherited lint and mypy counts, with no
  finding at a changed line.
