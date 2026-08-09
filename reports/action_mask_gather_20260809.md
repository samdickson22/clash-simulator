# Canonical occupancy-mask gather optimization

Date: 2026-08-09

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

## Change

The fast action mask converts world-coordinate building and troop occupancy
masks into the 18x32 canonical player perspective. The prior implementation
copied all 576 entries in Python for each distinct footprint or collision
radius in a hand. The candidate performs the same ordered copy with NumPy
advanced indexing over the already immutable per-player world-coordinate
table.

It does not alter candidate tiles, occupancy geometry, legal action order,
arena data, card mechanics, or fast-path selection. There are no card-name or
enabled-deck branches.

## Clean bounded benchmarks

Machine: Apple M4 Pro, 24 GiB RAM, Darwin arm64, Python 3.12.13. The host had
no live Clasher or RoadForge worker. All runs were single-process CPU, with
alternating baseline/candidate order.

Mixed-hand fast-mask command:

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_action_mask_gather.py \
  --seed 2301 --decisions 128 --repetitions 7 --warmup-decisions 4
```

| mode | median seconds | mean seconds | stdev | median decision loops/s |
| --- | ---: | ---: | ---: | ---: |
| Python loop | 0.137163 | 0.137362 | 0.001242 | 933.198822 |
| indexed gather | 0.061890 | 0.061805 | 0.000377 | 2068.202199 |

This is +121.63% for the live-building mixed-hand mask workload. All 14 rows
produced exact mask hash
`79764f99d5043bc8d05f789a28e3525aee2cf88376c6cd196f863127c909eb30`.

Exact-oracle command:

```bash
PYTHONPATH=src:. uv run python scripts/perf/benchmark_action_mask_gather_oracle.py \
  --seed 2301 --planner-seed 901 --states 3 --state-stride 4 \
  --repetitions 5 --decision-interval 8 --planner-depth 6 \
  --planner-simulations 32 --planner-action-samples 64 --engine-fast-path on
```

The loop median was 2.052518 seconds / 1.461620 labels/s. Gather median was
2.043372 seconds / 1.468162 labels/s, a +0.45% exact-label gain. All ten rows
produced label/state/planner-RNG digest
`72ac36812d5128f446b1eb98d2f40b6487e36d9c357c61f65148729f7f51e7b9`.

Production-shaped 64-step, seven-pair stationary screens used seed 2301, one
environment, eight warmup steps, two Torch threads, and the exact fast path.
Balanced strategy improved 99.040379 to 99.714794 decisions/s (+0.68%), with
digest `edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`.
Random improved only 106.777025 to 106.879847 decisions/s (+0.10%) in the
first screen and +0.18% in a persistent-model rerun, both below a material
claim; digest remained
`1a585dd8f5159d030435096005b8483dcd52079e309df554712150ea9e240785`.

## Exactness and integration

The focused unit test proves both player perspectives and both occupancy-mask
helpers match a scalar ordered copy and return independent arrays. Gates:

```text
46 action-mask/targeting/target-switch tests passed
1 pinned reference/off/shadow/on digest test passed
Ruff clean excluding only pre-existing modernization/style findings
py_compile and git diff --check clean
mypy adds no error; it retains 1 pre-existing untyped action-space function
and the same 9 dynamic Entity pathfinding attributes
```

Cherry-pick the isolated commit. It changes only the two internal gather
helpers, one exact test, bounded benchmark drivers, and this report. No CLI,
corpus metadata, observation, reward, RNG, or checkpoint format changes are
required.
