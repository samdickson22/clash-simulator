# Exact cached Crown fallback membership

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

Depends on: `ccab160` (exact static targetability classification)

## Change

When no ordinary target is in sight, small-set fast targeting uses the scalar
Crown fallback. That path scanned every live building for every attacker,
including friendly towers and unrelated deployed buildings, then reclassified
the surviving candidates as Crown towers. In the post-`ccab160` exact oracle
profile, this nested fallback consumed 0.671 seconds across 27,714 calls.

Structural target-cache rebuilds already identify every live Crown target.
They now publish exact insertion-ordered membership by owner. Live fast-path
fallbacks query only the opposing owner's Crown list and skip repeated building
and Crown classification. Identity, targetability, attacker-mechanic, pending
damage, target plane, preference, and distance checks remain unchanged.
Scalar mode, detached entities, and caller-supplied entity collections retain
the complete scan. Static Crown classification changes force a structural
rebuild, and clone state owns independent membership lists and entity objects.

No new card-name, deck, action, observation, reward, or RNG branch was added;
the cache reuses the existing shared Crown classification.

## Machine and controls

- Apple M4 Pro, 24 GiB RAM
- macOS 26.5.2 arm64
- Python 3.12.13
- single-process CPU only; no MPS/GPU, checkpoint, training, or corpus write
- fixed battle seed 2301 and oracle seed 901
- executable-prefix Clasher trainer/eval/actor guard before and after every
  accepted command
- continuous 30-second quiescence window immediately before the accepted
  matched oracle benchmark

## Exact oracle labels

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_oracle_crown_fallback_membership.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 5 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

The driver alternates full-scan/cached order over five matched repetitions. Its
digest includes before/after planner state keys, both action labels, battle RNG
before/after every label, and complete final planner RNG.

| fallback membership | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| full building scan | 1.210702 | 1.210499 | 0.003002 | 2.477902 |
| cached opposing Crowns | 1.187424 | 1.188777 | 0.004191 | 2.526478 |

Cached membership improves exact oracle throughput by **1.96%** and reduces
wall time by 1.92%. All ten rows produced digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.

A three-label `cProfile` attribution reduced `_is_valid_target` calls from
389,441 to 285,128 (104,313 fewer, **−26.8%**) because friendly/unrelated
buildings no longer enter the fallback validation loop.

## Production-shaped stationary rollouts

Each command used one environment, 64 decisions, seven repetitions after two
untimed warmup decisions, two Torch threads, exact fast mode, and all preceding
cache optimizations enabled.

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_stationary_rollout.py \
  --workload random --seed 2301 --num-envs 1 --rollout-steps 64 \
  --repetitions 7 --warmup-steps 2 --torch-threads 2 \
  --engine-fast-path on --target-cache-refresh reuse \
  --building-cache-refresh reuse --targetability-refresh classified \
  --crown-fallback-membership {scan,cached}

# Repeat with --workload strategy --strategy balanced.
```

| workload | scan seconds / decisions/s | cached seconds / decisions/s | gain |
| --- | ---: | ---: | ---: |
| stationary random | 0.432726 / 147.899694 | 0.429008 / 149.181512 | **+0.87%** |
| balanced strategy | 0.503368 / 127.143456 | 0.501024 / 127.738509 | **+0.47%** |

Random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Crowded exact engine

The 12-v-12 Knight workload rapidly acquires ordinary nearby troops, so Crown
fallback is a small fraction of total work. It remains exact and noise-flat to
slightly positive:

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_crowded_engine.py \
  --seed 2301 --card Knight --per-side 12 --ticks 64 --repetitions 11 \
  --mode on --clear-route-cache-per-mode --target-cache-refresh reuse \
  --building-cache-refresh reuse --targetability-refresh classified \
  --crown-fallback-membership {scan,cached}
```

| fallback membership | median seconds / 64 ticks | ticks/s |
| --- | ---: | ---: |
| full scan | 0.125286 | 510.829347 |
| cached | 0.124939 | 512.250491 |

This is +0.28% in ticks/s with unchanged state digest
`d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`.

## Exactness gates

```text
98 target/collision/action-mask/clone/batched/determinism focused tests passed
622 enabled troop-interaction tests passed
direct coverage includes death, same-size replacement, static Crown mutation,
  caller collection fallback, clone isolation, and off/shadow/on fixed seeds
scalar/off = shadow = optimized/on canonical digest
  6580da7847703ca63be431ab815c494c419abd39f439557dd3f9418c8e3a464e
shadow mismatches = 0
new test and benchmark driver Ruff/py_compile clean
git diff --check clean
```

## Integration

Cherry-pick this commit after `ccab160`. If `battle.py` conflicts, port the
`_crown_target_entities_by_player` field, structural rebuild publication,
static-Crown rebuild guard, and `get_fast_crown_target_entities` accessor. In
`entities.py`, port the benchmark switch and cached-candidate selection inside
the existing fallback closure. Include the Crown membership IDs in explicit
batched-cache parity checks. The existing stationary/crowded drivers only gain
the `--crown-fallback-membership` selector.
