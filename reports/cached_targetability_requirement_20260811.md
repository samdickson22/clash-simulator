# Reuse exact cached targetability requirement

Date: 2026-08-11

## Change

The exact fast target cache already publishes one Boolean per eligible entity:
whether its non-stealth targetability can change and must be refreshed during
per-component synchronization. Read that Boolean in `_sync_fast_target_entity`
instead of rescanning the entity's death-spawn state, hidden-building marker,
and mechanics list on every sync.

The classification is populated by the existing authoritative helper at every
structural cache rebuild. Mechanics are attached before manager insertion and
remain stable for the entity lifetime; the cache's existing documentation and
clone-isolation tests already establish that invariant. A private switch keeps
the recomputing reference path.

## Profile attribution

A current optimized-stack strategy profile (4 environments x 32 steps,
defense-v2, exact fast path) recorded 48,432 calls to
`_sync_fast_target_entity`. Those calls spent 0.093 seconds total and each
recomputed `_requires_targetability_check` even though the exact result was
already stored at the entity's target-cache index.

## Machine and conditions

- Apple M4 Pro, 24 GiB RAM
- macOS 26.5.2 arm64, Python 3.12.13
- single benchmark process, two Torch threads, `nice -n 15`
- an unrelated MPS imitation fit and one single-core RoadForge solver shared
  the host
- alternating reference/candidate order; deterministic 20,000-resample
  percentile bootstrap of paired mean (seed 0)

Absolute rates should not be compared with clean historical runs. The paired
oracle evidence is tight and supports the optimization under shared load.

## Production-shaped results

### Oracle

```text
nice -n 15 env PYTHONPATH=src:.:scripts/perf uv run python scripts/perf/benchmark_deployment_blocker_guard_oracle.py --comparison targetability-requirement --seed 2301 --planner-seed 901 --states 3 --state-stride 4 --repetitions 11 --decision-interval 8 --planner-depth 6 --planner-simulations 32 --planner-action-samples 64 --engine-fast-path on
```

- Recomputed median: 1.167253 s, 2.570 decisions/s
- Cached median: 1.138521 s, 2.635 decisions/s
- Paired median: **+2.690%**
- Paired mean: **+2.305%**, 95% CI **+1.706% to +2.885%**
- 11/11 pairs positive
- Both hashes: `72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`

### Stationary rollouts

Command shape:

```text
nice -n 15 env PYTHONPATH=src:.:scripts/perf uv run python scripts/perf/benchmark_deployment_blocker_guard_rollout.py --comparison targetability-requirement --workload WORKLOAD --strategy balanced --seed 2301 --num-envs 8 --rollout-steps 16 --repetitions 11 --warmup-steps 8 --torch-threads 2 --engine-fast-path on --reward-profile defense-v2
```

| workload | recomputed median | cached median | paired median | paired mean | mean 95% CI | positive | digest |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| random | 187.306 decisions/s | 188.356 decisions/s | +0.437% | +1.380% | -0.488% to +3.510% | 8/11 | `7b30368c51234d9d77efc7ec49d4469a0216c2dc97b72544326d4f64b64829d4` |
| balanced strategy | 196.882 decisions/s | 197.705 decisions/s | +0.918% | +1.297% | +0.060% to +3.134% | 8/11 | `688a582b099968f7bb783780f05055e6d3d5f8d3fb6a87b3df3bedc53c498f17` |

## Exactness gates

- 49 static/dynamic targetability, stealth, exhaustive-none, fast-target,
  spatial targeting, target-switching, and fixed trace tests passed.
- A focused call-count test proves reference recomputation occurs once and the
  candidate reads the cached Boolean zero times through the helper, while a
  mutable targeting-blocker mechanic still changes targetability exactly.
- Fixed seed 8827, stationary strategy, 8 environments x 64 steps:
  - off reference/candidate hash:
    `46540815ea12e25b080300d1420b0a848232307d82065685f4015647ab3a55c5`
  - shadow same hash, two checks each, zero mismatches
  - optimized/on same hash
- Ruff passes with only the file's explicitly excluded inherited findings;
  `git diff --check` passes.

## Integration

Port `_USE_CACHED_TARGETABILITY_REQUIREMENT` and the conditional in
`BattleState._sync_fast_target_entity`, plus the call-count and fixed-trace
tests in `tests/test_static_targetability_cache.py`. No card-name logic or
enabled-deck specialization is involved.
