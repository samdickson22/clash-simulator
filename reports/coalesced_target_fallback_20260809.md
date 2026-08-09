# Coalesced target and Crown-fallback scan

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

## Change

While a troop is pathing, the engine first queried for ordinary in-sight
targets with Crown fallback disabled. If that returned no target, the usual
case in open-lane movement, it immediately repeated the complete spatial,
targetability, plane, sight, and mechanics scan with Crown fallback enabled.

The troop path now makes one query with the correct fallback permission known
up front. The shared target selector returns an internal boolean identifying
whether its selected target came from the existing Crown-fallback branch. The
backward-path retention condition still disables fallback exactly as before.
Public target selection keeps the same return behavior.

This is general engine logic. It adds no card, deck, policy, player, or arena
special case and consumes no RNG.

## Machine and controls

- Apple M4 Pro, 24 GiB RAM
- macOS 26.5.2 arm64
- Python 3.12.13
- single-process CPU only; no MPS/GPU or checkpoint/corpus writes
- full-command process guard run immediately before every timed invocation
- fixed battle seed 2301 and oracle seed 901

The oracle benchmark alternated reference/candidate order for five paired
repetitions after one warmup label per variant. The stationary benchmarks used
eleven repetitions and eight untimed warmup decisions per variant.

## Exact oracle labels

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_oracle_coalesced_fallback.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 5 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

The digest includes every before/after planner state key, both selected action
labels, battle RNG before/after every label, and the complete final planner RNG.

| mode | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| duplicate scan | 1.760805 | 1.757763 | 0.012483 | 1.703766 |
| coalesced scan | 1.714813 | 1.713517 | 0.008978 | 1.749462 |

Coalescing improves exact oracle label throughput by **2.68%**. All ten rows
produced digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.

## End-to-end stationary rollouts

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_coalesced_fallback.py \
  --coalesced-fallback-scan {off,on} --workload random --seed 2301 \
  --num-envs 1 --rollout-steps 64 --repetitions 11 --warmup-steps 8 \
  --torch-threads 2 --engine-fast-path on

PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_coalesced_fallback.py \
  --coalesced-fallback-scan {off,on} --workload strategy \
  --strategy balanced --seed 2301 --num-envs 1 --rollout-steps 64 \
  --repetitions 11 --warmup-steps 8 --torch-threads 2 \
  --engine-fast-path on
```

| workload | duplicate seconds | coalesced seconds | duplicate decisions/s | coalesced decisions/s | gain |
| --- | ---: | ---: | ---: | ---: | ---: |
| stationary random | 0.507876 | 0.460582 | 126.015001 | 138.954552 | **+10.27%** |
| balanced strategy | 0.522402 | 0.517702 | 122.511134 | 123.623293 | **+0.91%** |

Random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Exactness gates

```text
5 dedicated scalar/off, shadow, optimized/on, and scalar/vector status cases passed
91 targeting/collision/action-mask/pathfinding exactness cases passed
661 broader targeting/sight/switching/enabled-interaction cases passed
pinned 64-decision scalar/off, shadow, and optimized/on digest unchanged:
6580da7847703ca63be431ab815c494c419abd39f439557dd3f9418c8e3a464e
shadow checks > 0; shadow mismatches = 0
benchmark drivers and dedicated test: Ruff and py_compile clean
entities.py: no candidate-specific Ruff or mypy findings; inherited file has
existing modernization/style and 46 existing mypy findings
git diff --check clean for owned changes
```

## Rejected adjacent probes

Two exact candidates were measured and removed before this change:

- rebuilding derived caches after `BattleState.clone`: -0.48% clone throughput
  and -0.14% oracle throughput;
- passing an already computed scalar distance into the sight check: -1.08%
  oracle throughput.

Both probes preserved their complete fixed-seed hashes but did not meet the
throughput acceptance threshold.

## Integration

Cherry-pick the isolated commit. If `entities.py` conflicts, port the private
`_COALESCE_CROWN_FALLBACK_TARGET_SCAN` benchmark switch, the internal fallback
status return from scalar and vector target selection, and the single-query
troop update branch. The remaining files are the direct parity test, two
bounded benchmark drivers, and this report. No observation, legal action,
reward, policy, RNG, checkpoint, corpus, or fingerprint format changes are
required.
