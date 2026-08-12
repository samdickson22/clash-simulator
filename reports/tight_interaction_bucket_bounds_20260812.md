# Exact tight interaction bucket bounds

## Change

The shared bucket query historically adds a two-tile halo to every requested
radius. Target acquisition retains that conservative halo because its caller
uses sight semantics. Collision and native avoidance already pass complete
center-distance bounds: own/probe radius plus the maximum collision radius of
any live target. Those two callers now request tight bucket bounds and avoid
enumerating unrelated neighboring cells.

This changes only candidate over-inclusion. The subsequent exact integer
circle tests, entity encounter ordering, target acquisition, collision planes,
radii, masses, mechanics, and movement accumulation are unchanged. The bound
is derived from shared data-driven radii and contains no card-name or deck
branch.

## Profile attribution

The `ec7a652` oracle profile `/tmp/clasher_oracle_ec7a652.prof` recorded 47,722
bucket queries (194 ms cumulative), including 11,951 collision and 7,609
avoidance calls. The previous halo makes those high-frequency local
interaction scans cover up to two extra bucket rows and columns on every side.

## Machine and benchmark method

- Apple M4 Pro, 12 CPU cores, 24 GiB RAM
- macOS 26.5.2 arm64; Python 3.12.13
- single process, `nice -n 15`, one BLAS/OpenMP/VecLib thread
- fixed snapshots, seeds, and alternating halo/tight order
- 11 matched pairs per workload; deterministic 95% bootstrap interval for the
  paired mean
- direct process inspection found no live Clasher or RoadForge worker

| workload | halo reference | tight bounds | paired median | positive pairs | paired-mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Oracle, 3 labels | 3.43039 labels/s | 3.48998 labels/s | +1.6279% | 11/11 | +1.4869% to +1.7695% | `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9` |
| Strategy rollout, 256 decisions | 206.90091 decisions/s | 208.31175 decisions/s | +0.8137% | 11/11 | +0.7457% to +1.8935% | `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d` |
| Random rollout, 256 decisions | 198.61951 decisions/s | 200.51855 decisions/s | +1.1334% | 11/11 | +0.9576% to +2.0149% | `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a` |

The first rollout pair was a wider roughly 4.4% cold/host outlier. Every one
of the remaining 20 strategy/random pairs was still positive; attribution uses
the paired medians rather than the larger means.

## Commands

```bash
nice -n 15 env PYTHONPATH=src:.:scripts/perf \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv/bin/python scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison tight-interaction-buckets --seed 2301 --planner-seed 901 \
  --states 3 --state-stride 4 --repetitions 11 --decision-interval 8 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on

nice -n 15 env PYTHONPATH=src:. \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv/bin/python scripts/perf/benchmark_deployment_blocker_guard_rollout.py \
  --comparison tight-interaction-buckets --workload WORKLOAD \
  --strategy balanced --seed 2301 --num-envs 8 --rollout-steps 32 \
  --repetitions 11 --warmup-steps 8 --torch-threads 1 \
  --engine-fast-path on --reward-profile defense-v2
```

Raw clean outputs:

- `/tmp/tight_interaction_buckets_oracle.json`
- `/tmp/tight_interaction_buckets_strategy.json`
- `/tmp/tight_interaction_buckets_random.json`

## Exactness gates

- Seed 8973, 64 decisions, halo/tight scalar/off, shadow, and optimized/on
  digest
  `33b6ac92244c4eb30ab7390e77ec00916e10319a2bb3ed8271e09430163ff195`.
- Seed 8831, 64 decisions, halo/tight scalar/off, shadow, and optimized/on
  digest
  `747f97fcfda1118899b6d42922a191c53914920dd2fe79163395dfba694efe8e`.
- Each shadow variant performed one action-mask comparison and reported zero
  mismatches.
- Direct tests prove that every bucket whose unit cell can contain a center
  within the query square remains covered and that exact collision vector
  components/count match the halo path.
- 749 collision, avoidance, targeting, target switching, action-mask, clone,
  route, enabled-interaction, and determinism tests passed in 10.30 seconds.
- New tests and benchmark drivers are Ruff-clean; all changed Python files
  compile; `git diff --check` is clean.
- `battle.py` and `entities.py` retain exactly their inherited lint counts and
  combined mypy backlog, with no finding at a changed line.
