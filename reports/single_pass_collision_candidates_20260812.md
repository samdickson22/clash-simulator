# Single-pass exact collision candidates

## Change

Ground collision pressure from nearby troops and static buildings is additive.
`BattleState._accumulate_troop_collision_for` now consumes the exact ordered
candidate list once, accumulating troop and building contributions as each
entity is encountered, instead of traversing that same list again for
buildings. Air units retain the troop-only path.

The accumulated components and count are Python integers, and normalization is
performed only after the method returns, so interleaving the additions cannot
change the result. Candidate membership, alive and transit filters, collision
planes, radii, masses, and the exact broadphase remain unchanged. The change is
general shared-engine logic with no card-name or enabled-deck branch.

## Profile attribution

The optimized `62e49a2` oracle profile `/tmp/clasher_oracle_62e49a2.prof`
recorded 33,756 collision-broadphase calls through
`iter_entities_in_radius`. The existing exact broadphase already returns the
complete encounter-ordered list needed by both troop and static-object
collision checks; this candidate removes only its second Python traversal.

## Machine and benchmark method

- Apple M4 Pro, 12 CPU cores, 24 GiB RAM
- macOS 26.5.2 arm64; Python 3.12.13
- single process, `nice -n 15`, one BLAS/OpenMP/VecLib thread
- fixed snapshots, seeds, and alternating two-pass/single-pass order
- deterministic 95% bootstrap interval for the paired mean
- direct process inspection excluded active Clasher and RoadForge workers

| workload | two-pass reference | single pass | paired median | positive pairs | paired-mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Oracle, 3 labels, 11 pairs | 3.24951 labels/s | 3.26111 labels/s | +0.4440% | 10/11 | +0.1140% to +0.5514% | `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9` |
| Strategy rollout, 256 decisions, 21 pairs | 201.55480 decisions/s | 201.87031 decisions/s | +0.2341% | 16/21 | +0.1018% to +0.7042% | `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d` |
| Random rollout, 256 decisions, 21 pairs | 193.56345 decisions/s | 194.20177 decisions/s | +0.2382% | 16/21 | +0.2150% to +1.1513% | `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a` |

The rollout means contain several roughly 3% host-jitter pairs, including the
first pair of each extended run. The conservative whole-rollout attribution is
therefore the stable paired median: about +0.23%, not the larger mean.

## Commands

```bash
nice -n 15 env PYTHONPATH=src:.:scripts/perf \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv/bin/python scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison single-pass-collision --seed 2301 --planner-seed 901 \
  --states 3 --state-stride 4 --repetitions 11 --decision-interval 8 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on

nice -n 15 env PYTHONPATH=src:. \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv/bin/python scripts/perf/benchmark_deployment_blocker_guard_rollout.py \
  --comparison single-pass-collision --workload WORKLOAD --strategy balanced \
  --seed 2301 --num-envs 8 --rollout-steps 32 --repetitions 21 \
  --warmup-steps 8 --torch-threads 1 --engine-fast-path on \
  --reward-profile defense-v2
```

Raw clean outputs:

- `/tmp/single_pass_collision_oracle.json`
- `/tmp/single_pass_collision_strategy_21.json`
- `/tmp/single_pass_collision_random_21.json`

## Exactness gates

- Seed 8963, 64 decisions, both switch settings: scalar/off, shadow, and
  optimized/on digest
  `f0faaf835d8c2307851763bf73b1fb6a8c73b9e835088c05d22fb921aa327070`.
- Seed 8831, 64 decisions, both switch settings: scalar/off, shadow, and
  optimized/on digest
  `747f97fcfda1118899b6d42922a191c53914920dd2fe79163395dfba694efe8e`.
- Each shadow variant performed one action-mask comparison and reported zero
  mismatches.
- 194 Crown fallback, targeting, target-switching, cache, collision,
  action-mask, gather, clone, and determinism tests passed in 12.51 seconds.
- The new test and benchmark drivers are Ruff-clean; all changed Python files
  compile; `git diff --check` is clean.
- `battle.py` retains its inherited lint and mypy backlog, with no finding at a
  changed line.
