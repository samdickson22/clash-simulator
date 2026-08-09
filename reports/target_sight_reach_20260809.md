# Exact fast-target sight-reach allocation reduction

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

## Change

Every vectorized nearest-target query previously allocated a collision-radius
fallback, two nested `where` results, a float conversion, and a division result
to derive sight reach. The candidate starts from the required radius array and
applies nonzero building/crown extensions directly with `np.add(..., where=)`.

The established implementation remains as a private reference for exact tests
and matched attribution. Both implementations read the shared client globals
at call time. The candidate therefore supports arbitrary collision-radius,
building-extension, and crown-extension combinations without card-name or
enabled-deck branches.

## Clean bounded benchmarks

Machine: Apple M4 Pro, 24 GiB RAM, Darwin arm64, Python 3.12.13. The training
population was between evaluation bursts; an immediate process guard verified
that no Clasher training, evaluation, DAgger, RoadForge, or MPS worker was live.
All measurements were single-process CPU runs.

Crowded-engine command:

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_target_sight_reach.py \
  --seed 2301 --card Knight --per-side 12 --ticks 64 --repetitions 7
```

The driver warms the exact dense route cache, then alternates reference and
candidate ordering.

| mode | median seconds | mean seconds | stdev | median ticks/s |
| --- | ---: | ---: | ---: | ---: |
| reference | 0.185101 | 0.185232 | 0.000779 | 345.757725 |
| candidate | 0.181925 | 0.181649 | 0.001700 | 351.793482 |

This is +1.75% crowded-engine throughput. All 14 measured rows produced exact
battle hash
`d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`.

Production-shaped stationary rollouts used the existing driver with seed 2301,
one environment, 64 steps, seven repetitions, eight warmup steps, two Torch
threads, and the exact fast path. Each variant was selected before loading the
driver:

```python
from clasher import entities
entities._target_sight_reach = entities._target_sight_reach_reference  # baseline
entities._target_sight_reach = entities._target_sight_reach_candidate  # candidate
```

| workload | reference seconds | candidate seconds | reference decisions/s | candidate decisions/s | gain |
| --- | ---: | ---: | ---: | ---: | ---: |
| stationary random | 0.612162 | 0.608670 | 104.547475 | 105.147245 | 0.57% |
| balanced strategy | 0.649706 | 0.642057 | 98.506094 | 99.679611 | 1.19% |

Both random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`.
Both strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Exactness and integration

The dedicated test compares the candidate and established expressions bit for
bit across both radius modes, zero/nonzero building extensions, and three crown
extensions. Gates:

```text
56 direct sight-reach/targeting/target-switch/action-mask tests passed
16 enabled target-geometry/sight/nearest-target tests passed
1 pinned scalar/off, shadow, optimized/on rollout digest test passed
shadow checks > 0; shadow mismatches = 0
Ruff clean for owned test/benchmark and changed code excluding existing findings
py_compile and git diff --check clean
```

Cherry-pick the isolated commit. It changes only the shared target-reach helper,
its direct exact test, one bounded benchmark, and this report. It changes no
action, observation, reward, target ordering, RNG use, planner configuration,
corpus metadata, or checkpoint format.
