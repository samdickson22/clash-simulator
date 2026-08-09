# Exact row-major dense bucket scanning

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

Depends on: `7086b80`

## Change

The fast dense entity-bucket grid is stored row-major, but radius queries
visited it column-major and recomputed `by * width` for every cell. Every query
subsequently restores exact ascending entity-ID encounter order, so the
pre-sort grid traversal order is not observable. Dense queries now visit rows
in storage order and compute one row offset per queried row.

Candidate cells, bucket contents, final ID order, ties, collision inputs, and
target inputs are unchanged. Sparse buckets retain their original path. There
are no card, deck, policy, action, reward, or enabled-interaction branches.

## Machine and controls

- Apple M4 Pro, 24 GiB RAM
- macOS 26.5.2 arm64
- Python 3.12.13
- single-process CPU only; no MPS/GPU, training, checkpoint, or corpus write
- fixed battle seed 2301 and oracle seed 901
- executable-prefix process guards before and after accepted commands
- alternating oracle order and candidate-first production confirmation

## Exact oracle labels

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_oracle_bucket_scan_order.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 9 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

The driver alternates column/row-major order. Its digest includes before/after
planner state keys, both selected actions, battle RNG before/after every label,
and the complete final planner RNG.

| scan order | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| column-major | 1.151348 | 1.159799 | 0.016084 | 2.605641 |
| row-major | 1.124718 | 1.133761 | 0.014477 | 2.667334 |

Row-major scanning improves exact oracle throughput by **2.37%** and reduces
median wall time by 2.31%. All eighteen rows produced digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.

## Production-shaped stationary rollouts

Each variant used one environment, 64 decisions, nine repetitions after two
untimed warmup decisions, two Torch threads, exact fast mode, and all preceding
optimizations. The candidate ran before the reference in each workload.

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_stationary_rollout.py \
  --workload random --seed 2301 --num-envs 1 --rollout-steps 64 \
  --repetitions 9 --warmup-steps 2 --torch-threads 2 \
  --engine-fast-path on --target-cache-refresh reuse \
  --building-cache-refresh reuse --targetability-refresh classified \
  --crown-fallback-membership cached \
  --crown-distance-order preferred-first \
  --inactive-stealth-time deferred --bucket-id-sort inplace \
  --targetability-fields direct \
  --bucket-scan-order {column-major,row-major}

# Repeat with --workload strategy --strategy balanced.
```

| workload | column seconds / decisions/s | row seconds / decisions/s | gain |
| --- | ---: | ---: | ---: |
| stationary random | 0.420442 / 152.220924 | 0.417638 / 153.242776 | **+0.67%** |
| balanced strategy | 0.492417 / 129.971120 | 0.492756 / 129.881704 | **−0.07%** |

Random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.
The deterministic-strategy workload is neutral; the gain is attributed to
oracle/random/crowded workloads with more bucket traversal.

## Crowded exact engine

The candidate-first 12-versus-12 Knight check used 64 ticks and 15
repetitions per variant. Column-major measured 0.123654 seconds / 517.573
ticks/s; row-major measured 0.122926 seconds / 520.640 ticks/s, a **+0.59%**
improvement. Both produced state digest
`d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`.

## Exactness gates

```text
6 direct candidate-set and off-shadow-on fixed-seed cases passed
103 targeting/collision/action-mask/clone/batched/determinism focused tests passed
736 enabled troop/spell/projectile/reachable-child interaction tests passed
scalar/off = shadow = optimized/on digest remains
  6580da7847703ca63be431ab815c494c419abd39f439557dd3f9418c8e3a464e
shadow checks are positive; shadow mismatches = 0
new test and oracle driver Ruff/py_compile clean
existing benchmark-driver additions checked with inherited EXE001/UP012 excluded
git diff --check clean
```

## Integration

Cherry-pick after `7086b80`. The production source change is limited to the
benchmark switch and dense row-major branch in `iter_entities_in_radius`.
Existing stationary/crowded drivers only gain `--bucket-scan-order`. The
dedicated oracle driver and test are standalone. If `battle.py` conflicts,
exclude the unrelated live-building cache hunk from this optimizer worktree.
