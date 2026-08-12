# Exact target-acquisition bucket bound

## Change

Small target sets use the exact scalar selector over spatial buckets. Its
former query used `sight + maximum collision radius + 1` and then inherited a
generic two-tile bucket halo. The candidate derives the maximum possible
center distance of any in-sight target instead:

```text
sqrt((sight + max target radius + max serialized sight extension + epsilon)^2
     + max target distance-discount squared)
```

The target cache now publishes the maximum squared spawn-priority distance
discount alongside its existing maximum collision radius. Target acquisition
uses the formula with tight bucket bounds. Collision and avoidance retain their
separately proven exact bounds, while the reference switch retains the old
halo query.

The formula is a conservative maximum across all live data-driven targets and
preserves collision-radius reach, building/Crown sight extensions, geometry
epsilon, and death/spawn priority discounts. Subsequent allegiance,
targetability, plane, mechanics, sight-clip, distance, and tie checks are
unchanged. There is no card-name or enabled-deck branch.

## Profile attribution

The `ff5da68` oracle profile `/tmp/clasher_oracle_ff5da68.prof` recorded 47,722
bucket queries (190 ms cumulative) and 28,626 target selections (637 ms). After
tight collision/avoidance bounds, target acquisition was the dominant source
of over-inclusive bucket candidates.

## Machine and benchmark method

- Apple M4 Pro, 12 CPU cores, 24 GiB RAM
- macOS 26.5.2 arm64; Python 3.12.13
- single process, `nice -n 15`, one BLAS/OpenMP/VecLib thread
- fixed snapshots, seeds, and alternating halo/exact order
- 11 matched pairs per workload; deterministic 95% bootstrap interval for the
  paired mean
- direct process inspection found no live Clasher or RoadForge worker

| workload | halo reference | exact bound | paired median | positive pairs | paired-mean 95% CI | digest |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Oracle, 3 labels | 3.45340 labels/s | 3.50990 labels/s | +1.4524% | 11/11 | +1.1757% to +1.6130% | `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9` |
| Strategy rollout, 256 decisions | 207.27158 decisions/s | 208.62533 decisions/s | +0.6677% | 11/11 | +0.5579% to +1.6102% | `38d56debd82d96e73d359afb107aacb19375be36796eaa20eccb3ae832dee86d` |
| Random rollout, 256 decisions | 199.09082 decisions/s | 200.75266 decisions/s | +0.7755% | 11/11 | +0.6158% to +1.6599% | `a1eabfdc581fc92ea4c9ccdd397d37c2255dc93ae70d500b7af64a1c5cbcbc6a` |

The first rollout pair was again a wider roughly 4% host/cold outlier. Every
remaining strategy/random pair stayed positive; attribution uses the paired
medians rather than the larger means.

## Commands

```bash
nice -n 15 env PYTHONPATH=src:.:scripts/perf \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv/bin/python scripts/perf/benchmark_deployment_blocker_guard_oracle.py \
  --comparison exact-target-bucket-bound --seed 2301 --planner-seed 901 \
  --states 3 --state-stride 4 --repetitions 11 --decision-interval 8 \
  --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on

nice -n 15 env PYTHONPATH=src:. \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv/bin/python scripts/perf/benchmark_deployment_blocker_guard_rollout.py \
  --comparison exact-target-bucket-bound --workload WORKLOAD \
  --strategy balanced --seed 2301 --num-envs 8 --rollout-steps 32 \
  --repetitions 11 --warmup-steps 8 --torch-threads 1 \
  --engine-fast-path on --reward-profile defense-v2
```

Raw clean outputs:

- `/tmp/exact_target_bucket_bound_oracle.json`
- `/tmp/exact_target_bucket_bound_strategy.json`
- `/tmp/exact_target_bucket_bound_random.json`

## Exactness gates

- Seed 8977, 64 decisions, halo/exact scalar/off, shadow, and optimized/on
  digest
  `0b0af6bc0164119f07e064e03955a4e93654abf06d191d9dacf0359fe04557a4`.
  Its 128-decision shadow confirmation matched digest
  `a92edcb7ae5ec1a7574f9b06ef9779ea3eee379ea08203b8de08635212331057`
  with one comparison and zero mismatches per mode.
- Seed 8831, 64 decisions, halo/exact scalar/off, shadow, and optimized/on
  digest
  `747f97fcfda1118899b6d42922a191c53914920dd2fe79163395dfba694efe8e`,
  with one comparison and zero shadow mismatches per mode.
- A direct boundary test uses a large data-driven collision radius, Crown sight
  extension, and 1.44 tile-squared spawn discount at the adjusted sight edge;
  the exact query includes it and the scalar sight predicate accepts it.
- 777 collision, avoidance, targeting, target switching, action-mask, clone,
  route, enabled-interaction, and determinism tests passed in 11.49 seconds.
- New tests and benchmark drivers are Ruff-clean; all changed Python files
  compile; `git diff --check` is clean.
- `battle.py` and `entities.py` retain exactly their inherited lint counts and
  combined mypy backlog, with no new finding at a changed line.
