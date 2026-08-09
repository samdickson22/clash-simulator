# Exact spatial collision candidates

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

## Change

Every active troop previously scanned every battle entity twice for dynamic
troop pressure and static-building pressure. After exact dense entity buckets
landed, collision accumulation still consumed 0.213 seconds across 5,807 calls
inside one profiled exact oracle label.

Fast-path collisions now reuse the exact spatial iterator. The query radius is
the moving troop radius plus the cache's data-driven maximum target collision
radius; the iterator retains its existing two-tile conservative pad. The same
candidate list feeds both troop and building passes. Scalar/off mode and a
private benchmark switch retain the full entity scan.

Every accepted contribution is quantized to integer logic units, then integer-
summed with a count; the only flag is OR-reduced before one final normalization.
Candidate order therefore cannot change the result. The spatial iterator still
sorts by native entity ID. No card, deck, player, or enabled-interaction branch
is introduced, and collision consumes no RNG.

## Clean bounded benchmarks

Machine: Apple M4 Pro, 24 GiB RAM, macOS 26.5.2 arm64, Python 3.12.13. All
measurements were single-process CPU-only with no MPS work. A full-command-line
guard before each command rejected live training, evaluation, DAgger, and
multiprocessing workers. Oracle variant order alternated.

### Production-shape exact oracle

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_oracle_collision_buckets.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 5 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

The digest includes before/after planner state keys, joint action labels,
complete input-battle RNG before/after each label, and complete final planner
RNG.

| collision candidates | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| full entity scan | 1.783190 | 1.783148 | 0.013841 | 1.682378 |
| exact spatial buckets | 1.767394 | 1.767167 | 0.008680 | 1.697414 |

Spatial candidates improve exact oracle label throughput by **0.89%** and
reduce wall time by 0.89%. The candidate was faster in all five matched pairs.
Every row produced digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.

### Production-shaped stationary rollouts

Runs used seed 2301, one environment, 64 decisions, eleven repetitions, eight
warmup decisions, two Torch threads, and the exact fast path.

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_collision_buckets.py \
  --collision-candidates {scalar,bucketed} --workload random --seed 2301 \
  --num-envs 1 --rollout-steps 64 --repetitions 11 --warmup-steps 8 \
  --torch-threads 2 --engine-fast-path on

PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_collision_buckets.py \
  --collision-candidates {scalar,bucketed} --workload strategy \
  --strategy balanced --seed 2301 --num-envs 1 --rollout-steps 64 \
  --repetitions 11 --warmup-steps 8 --torch-threads 2 \
  --engine-fast-path on
```

| workload | scalar seconds | bucketed seconds | scalar decisions/s | bucketed decisions/s | gain |
| --- | ---: | ---: | ---: | ---: | ---: |
| stationary random | 0.544173 | 0.533813 | 117.609675 | 119.892191 | +1.94% |
| balanced strategy | 0.606756 | 0.599992 | 105.478995 | 106.668111 | +1.13% |

The stationary rows were noisier than the oracle pairs, so their medians are
reported as supporting attribution rather than combined with the oracle gain.
Both random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
both strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Exactness gates

The direct regression forces full and spatial candidates in scalar/off,
shadow, and optimized/on modes. A separate synthetic case raises both troop
collision radii to three tiles through shared card stats and proves the
data-driven maximum still includes the colliding pair.

```text
8 direct fixed-seed/broadphase/large-radius cases passed
66 collision/dense/target/action-mask/pathfinding/scalar-shadow cases passed
17 enabled interaction collision/body-pressure cases passed
pinned scalar/off, shadow, and optimized/on rollout digests unchanged
shadow checks > 0; shadow mismatches = 0
Ruff, py_compile, and git diff --check clean for owned changes
```

## Integration

Cherry-pick the isolated commit. If `battle.py` conflicts, port the `Iterable`
typing import, private benchmark switch, the candidate-list selection after
`own_air_collision`, and reuse that list in the static-building loop. The
remaining files are the direct test, two benchmark drivers, and this report.
No CLI, action, observation, reward, RNG, corpus, fingerprint, or checkpoint
format changes are required.
