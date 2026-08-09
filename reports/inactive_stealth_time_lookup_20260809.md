# Deferred inactive-stealth targetability time lookup

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

Depends on: `ccab160`, `e1ee425`, `d5ab677`

## Change

`Entity.is_targetable_by` converted the current battle time to integer
milliseconds for every otherwise-valid target, even when the target's absolute
stealth expiry timestamp was zero (the ordinary case) or the inactive negative
sentinel. Battle time is nonnegative and monotonic, so any nonpositive expiry
is already known to have elapsed. The targetability predicate now returns
immediately in that case. Positive stealth timestamps retain the complete
current-time comparison, and alive, owner, entity-kind, death-spawn immunity,
hidden-building, and mechanic-owned targeting gates remain in their original
order.

This is a shared, data-driven predicate optimization. It adds no card, deck,
policy, action, reward, or enabled-interaction branch.

## Machine and controls

- Apple M4 Pro, 24 GiB RAM
- macOS 26.5.2 arm64
- Python 3.12.13
- single-process CPU only; no MPS/GPU, training, checkpoint, or corpus write
- fixed battle seed 2301 and oracle seed 901
- executable-prefix process guards before and after accepted commands
- alternating oracle order and reverse-order stationary/crowded confirmation

## Exact oracle labels

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_oracle_inactive_stealth.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 5 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

The driver alternates eager/deferred order across five matched repetitions.
Its digest includes before/after planner state keys, both selected actions,
battle RNG before/after every label, and the complete final planner RNG.

| time lookup | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| eager | 1.392608 | 1.392012 | 0.007148 | 2.154231 |
| deferred for inactive stealth | 1.365862 | 1.365214 | 0.012010 | 2.196414 |

Deferring the inactive lookup improves exact oracle throughput by **1.96%**
and reduces wall time by 1.92%. All ten rows produced digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.

## Production-shaped stationary rollouts

Each variant used one environment, 64 decisions, nine repetitions after two
untimed warmup decisions, two Torch threads, exact fast mode, and all preceding
optimizations. The confirmation ran deferred first and eager second to oppose
the initial command order.

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_stationary_rollout.py \
  --workload random --seed 2301 --num-envs 1 --rollout-steps 64 \
  --repetitions 9 --warmup-steps 2 --torch-threads 2 \
  --engine-fast-path on --target-cache-refresh reuse \
  --building-cache-refresh reuse --targetability-refresh classified \
  --crown-fallback-membership cached \
  --crown-distance-order preferred-first \
  --inactive-stealth-time {eager,deferred}

# Repeat with --workload strategy --strategy balanced.
```

| workload | eager seconds / decisions/s | deferred seconds / decisions/s | gain |
| --- | ---: | ---: | ---: |
| stationary random | 0.454347 / 140.861384 | 0.453027 / 141.271842 | **+0.29%** |
| balanced strategy | 0.532531 / 120.180891 | 0.527341 / 121.363510 | **+0.98%** |

Random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Crowded exact engine

The reverse-order 12-versus-12 Knight confirmation used 64 ticks and 15
repetitions per variant. Eager measured 0.124491 seconds / 514.095 ticks/s;
deferred measured 0.124443 seconds / 514.293 ticks/s, a neutral **+0.04%**.
Both produced state digest
`d03a412a495660dcda93c9bd182db19d31e72ccae0a8621606e3c4a6cd23e8cb`.

## Exactness gates

```text
6 direct inactive/active stealth and off-shadow-on fixed-seed cases passed
81 targeting/action-mask/clone/batched/determinism focused tests passed
736 enabled troop/spell/projectile/reachable-child interaction tests passed
scalar/off = shadow = optimized/on digest remains
  6580da7847703ca63be431ab815c494c419abd39f439557dd3f9418c8e3a464e
shadow checks are positive; shadow mismatches = 0
new test and oracle driver Ruff/py_compile clean
existing benchmark-driver additions checked with inherited EXE001/UP012 excluded
git diff --check clean
```

## Integration

Cherry-pick after `ccab160`, `e1ee425`, and `d5ab677`. The production source
change is one exact early return in `Entity.is_targetable_by`, guarded by a
benchmark switch. Existing stationary/crowded drivers only gain the
`--inactive-stealth-time` selector. The dedicated oracle driver and test are
standalone.
