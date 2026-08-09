# Exact dense entity buckets

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

## Change

After small-target scalar selection, `iter_entities_in_radius` became a
measured hot path: 11,200 calls consumed 0.272 seconds in one profiled exact
oracle label. Each query allocated `(x, y)` tuple keys and performed sparse
dictionary lookups before sorting the same candidate entities into native ID
order.

The candidate publishes the same 2D spatial partition as a flat integer-indexed
table. Empty cells are `None`, so each tick allocates lists only for populated
cells rather than for all 144 arena buckets. Queries retain the same x-major,
y-minor cell traversal, candidate subset, per-cell insertion order, and final
entity-ID sort. The mapping implementation remains behind a private benchmark
switch.

The layout is derived solely from arena dimensions and the shared bucket-cell
size. It has no card, deck, policy, player, or enabled-interaction branch and
consumes no RNG.

## Clean bounded benchmarks

Machine: Apple M4 Pro, 24 GiB RAM, macOS 26.5.2 arm64, Python 3.12.13. All
measurements were single-process CPU-only with no MPS work. A full-command-line
guard immediately before every command rejected live training, evaluation,
DAgger, and multiprocessing workers. Variant order alternated in the oracle
benchmark.

### Production-shape exact oracle

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_oracle_dense_buckets.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 5 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 \
  --engine-fast-path on
```

The three snapshots include the initial state and deterministic random-action
successors. The digest includes before/after planner state keys, joint action
labels, complete input-battle RNG before/after each label, and complete final
planner RNG.

| bucket layout | median seconds / 3 labels | mean | stdev | median labels/s |
| --- | ---: | ---: | ---: | ---: |
| tuple-key mapping | 1.591098 | 1.591459 | 0.004629 | 1.885490 |
| flat sparse-slot table | 1.533394 | 1.533446 | 0.002720 | 1.956444 |

Dense buckets improve exact oracle label throughput by **3.76%** and reduce
wall time by 3.63%. All ten rows produced digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.

### Production-shaped stationary rollouts

The wrapper selects the bucket representation and delegates to the existing
stationary driver. Runs used seed 2301, one environment, 64 decisions, eleven
repetitions, eight warmup decisions, two Torch threads, and the exact fast
path.

```bash
PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_dense_buckets.py \
  --entity-buckets {mapping,dense} --workload random --seed 2301 \
  --num-envs 1 --rollout-steps 64 --repetitions 11 --warmup-steps 8 \
  --torch-threads 2 --engine-fast-path on

PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_dense_buckets.py \
  --entity-buckets {mapping,dense} --workload strategy --strategy balanced \
  --seed 2301 --num-envs 1 --rollout-steps 64 --repetitions 11 \
  --warmup-steps 8 --torch-threads 2 --engine-fast-path on
```

| workload | mapping seconds | dense seconds | mapping decisions/s | dense decisions/s | gain |
| --- | ---: | ---: | ---: | ---: | ---: |
| stationary random | 0.477969 | 0.472802 | 133.899909 | 135.363146 | +1.09% |
| balanced strategy | 0.532385 | 0.526305 | 120.213840 | 121.602377 | +1.16% |

Random variants produced digest
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`;
strategy variants produced
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.

## Exactness gates

The direct regression forces mapping and dense layouts in scalar/off, shadow,
and optimized/on modes. Clone and batched-tick gates additionally prove that
the published bucket membership remains isolated and coherent.

```text
14 direct/clone/batched-cache/spatial-target/collision cases passed
62 dense/target/collision/action-mask/pathfinding/scalar-shadow cases passed
pinned scalar/off, shadow, and optimized/on rollout digests unchanged
shadow checks > 0; shadow mismatches = 0
Ruff and py_compile clean for owned code, tests, and benchmark drivers
git diff --check clean
```

## Integration

Cherry-pick the isolated commit. The training branch has nearby inherited
`battle.py` edits; if cherry-pick conflicts, port only the private switch, two
dense bucket fields, the dense branch in `_rebuild_entity_buckets`, and the
dense lookup branch in `iter_entities_in_radius`. The remaining files are the
direct parity test, two benchmark drivers, and this report. No CLI, action,
observation, reward, RNG, corpus, fingerprint, or checkpoint-format change is
required.
