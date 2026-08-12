# Lazy exact Crown compatibility fallback builder

## Change

`Entity.get_nearest_target` previously allocated a nested closure for the
complete Crown compatibility fallback on every target query. Live native
battles almost always return from an ordinary in-sight target or the existing
exact direct Crown selector before that compatibility builder is called.

The compatibility implementation now lives in an ordinary method and is
called only when required. The benchmark reference switch recreates the former
per-query closure. Target candidates, validation, encounter order, semantic
Crown classification, adjusted distances, and tie rules are unchanged. The
change is general and contains no card-name or enabled-deck branch beyond the
existing serialized compatibility classifier it moves intact.

## Profile attribution

The optimized-stack oracle profile `/tmp/clasher_oracle_62e49a2.prof`
recorded 75,244 calls to `get_nearest_target` in 9.502 seconds. Its direct
Crown fallback handled 73,196 queries. The complete compatibility fallback was
therefore being prepared repeatedly in the same hot routine despite being
unneeded on the native direct path.

## Machine and benchmark method

- Apple M4 Pro, 12 CPU cores, 24 GiB RAM
- macOS 26.5.2 arm64; Python 3.12.13
- single process, `nice -n 15`, one BLAS/OpenMP/VecLib thread
- fixed snapshots, seeds, and alternating eager/lazy order
- 11 matched pairs per workload; deterministic 95% bootstrap interval for the
  paired mean
- direct process inspection found no live Clasher or RoadForge worker

| workload | eager closure | lazy method | paired median | positive pairs | paired-mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Oracle, 3 labels | 3.35414 labels/s | 3.37991 labels/s | +0.9076% | 11/11 | +0.7967% to +1.2500% | `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9` |
| Strategy rollout, 256 decisions | 205.51315 decisions/s | 205.93583 decisions/s | +0.3764% | 11/11 | +0.2209% to +1.2990% | `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d` |
| Random rollout, 256 decisions | 197.14843 decisions/s | 197.78144 decisions/s | +0.3495% | 11/11 | +0.2701% to +3.5206% | `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a` |

One late random pair carried a 10.7% host-jitter outlier and the first rollout
pair was also wider than steady state. Attribution therefore uses the paired
medians, not the inflated random mean.

## Commands

```bash
nice -n 15 env PYTHONPATH=src:.:scripts/perf \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv/bin/python scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison lazy-crown-fallback-builder --seed 2301 --planner-seed 901 \
  --states 3 --state-stride 4 --repetitions 11 --decision-interval 8 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on

nice -n 15 env PYTHONPATH=src:. \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv/bin/python scripts/perf/benchmark_deployment_blocker_guard_rollout.py \
  --comparison lazy-crown-fallback-builder --workload WORKLOAD \
  --strategy balanced --seed 2301 --num-envs 8 --rollout-steps 32 \
  --repetitions 11 --warmup-steps 8 --torch-threads 1 \
  --engine-fast-path on --reward-profile defense-v2
```

Raw clean outputs:

- `/tmp/lazy_crown_builder_oracle.json`
- `/tmp/lazy_crown_builder_strategy.json`
- `/tmp/lazy_crown_builder_random.json`

## Exactness gates

- Seed 8969, 64 decisions, eager/lazy scalar/off, shadow, and optimized/on
  digest
  `a9d2da72a05ccc4945ab0619a1a3f8e098a519786ca9fab1264bf13301509220`.
- Seed 8831, 64 decisions, eager/lazy scalar/off, shadow, and optimized/on
  digest
  `747f97fcfda1118899b6d42922a191c53914920dd2fe79163395dfba694efe8e`.
- Each shadow variant performed one action-mask comparison and reported zero
  mismatches.
- The compatibility-path unit test disables direct Crown selection and proves
  eager/lazy identity equality with an unclassified custom Crown objective.
- 198 Crown fallback, targeting, target-switching, cache, collision,
  action-mask, gather, clone, and determinism tests passed in 13.06 seconds.
- New tests and benchmark drivers are Ruff-clean; all changed Python files
  compile; `git diff --check` is clean.
- `entities.py` retains its inherited lint and mypy backlog, with no finding at
  a changed line.
