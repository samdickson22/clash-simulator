# Exact direct strategy action geometry

Date: 2026-08-11

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

## Change

Strategy opponents score every legal placement action. The reference scorer
called `DiscreteTileActionSpace.decode_action` for each action, allocating an
`ActionSelection` and `Position`, converting the already canonical tile to
world space, and then converting it back to canonical space.

The candidate reads the same slot and canonical 18x32 tile coordinates
directly from the legal action ID. No score term changes. No battle state,
action mask, observation, reward, RNG, or policy-model path changes. The logic
is common to all six data-driven strategy modes and contains no card names or
enabled-deck cases.

## Machine and shared-load controls

- Apple M4 Pro, 12 logical CPUs, 24 GiB RAM, macOS 26.5.2 arm64
- Python 3.12.13 through `uv`
- all timings single-process CPU-only with two Torch threads for rollouts
- candidate/reference order alternated by repetition
- commands used `nice -n 15`
- one RoadForge CPU reconstruction shared the host; no optimizer-owned MPS or
  model training was launched

## Direct balanced-strategy attribution

Seed 2301, one fixed public battle state, both player perspectives, 64
selections per row, 11 alternating matched pairs after four warmups:

```bash
nice -n 15 env PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_strategy_action_geometry.py \
  --strategy balanced --seed 2301 --selections 64 \
  --repetitions 11 --warmup-selections 4
```

| geometry | median seconds | mean | stdev | median selections/s |
| --- | ---: | ---: | ---: | ---: |
| decoded world round-trip | 0.100478 | 0.100246 | 0.001640 | 636.953 |
| direct canonical ID | 0.058166 | 0.058365 | 0.001288 | 1,100.294 |

The direct scorer improves median rate by **72.74%**. Its paired median was
71.02%, paired mean 71.82%, approximate two-sided 95% interval 69.35% to
74.28%, and all 11 pairs were positive. Every action sequence matched digest
`5356c3fc1ff9b65b14a546c11873ca10a7c7d7f305dce605fbd2274110bbc88e`.

## Production-shaped stationary rollouts

Both screens used the exact engine fast path, the verified optimization stack,
balanced strategy opponents, fixed Torch/model/environment seeds, and
alternating candidate/reference order.

```bash
nice -n 15 env PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_strategy_action_geometry_rollout.py \
  --strategy balanced --seed 2301 --num-envs 1 --rollout-steps 64 \
  --repetitions 7 --warmup-steps 8 --torch-threads 2 \
  --engine-fast-path on

nice -n 15 env PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_strategy_action_geometry_rollout.py \
  --strategy balanced --seed 2301 --num-envs 8 --rollout-steps 16 \
  --repetitions 7 --warmup-steps 8 --torch-threads 2 \
  --engine-fast-path on
```

| workload | decoded seconds / decisions/s | direct seconds / decisions/s | median-rate gain | paired median | positive pairs |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 env x 64 decisions | 0.484271 / 132.157 | 0.453800 / 141.031 | **+6.71%** | +6.50% | 7/7 |
| 8 envs x 16 decisions | 0.703336 / 181.990 | 0.638875 / 200.352 | **+10.09%** | +10.10% | 7/7 |

The one-environment paired mean interval was +5.40% to +8.84%. The
eight-environment paired mean interval was +9.23% to +13.51%. The respective
full-rollout digests were
`edb2effdd1a3c926b9b9ef8bb583eb4912618ab29e0c804439d9da3382810645`
and
`d87bdd871c9bb012c55aff818085f7da385061d83e445c632a601bdb23737590`.

Random-opponent collection does not invoke `StrategyBot`, so this change has
no executed path and no claimed effect for that workload.

## Exactness gates

The score test compares every legal action for all six strategies and both
player perspectives. The trace test compares reference/direct choices for six
successive two-player decisions in scalar/off, shadow, and optimized/on modes.

```text
48 direct-score, fixed-trace, and strategy/PFSP tests passed
all reference/direct score floats and action traces matched exactly
Ruff and py_compile clean for owned files
strategy_bots.py mypy clean
git diff --check clean
```

Reference and direct 32-decision rollouts produced the same digest in all
three engine modes:
`500a76e31cb0d8112664d047b445afa16d695d8adf0e68965fe94ede2a75c475`.
Shadow performed one action-mask comparison per variant and reported zero
mismatches.

## Integration

The optimizer worktree inherited `strategy_bots.py` as an untracked pipeline
file, so committing its complete contents would incorrectly capture unrelated
strategy/PFSP work. The isolated delivery commit therefore contains the exact
test, two benchmark drivers, and this report; port the narrow production hunk
manually into the authoritative tracked file:

1. import `BOARD_WIDTH` and `NUM_TILES` from `.common`;
2. retain a private `_USE_DIRECT_CANONICAL_ACTION_GEOMETRY = True` reference
   switch while integrating the A/B test, and enter the direct branch only
   when both that switch and `action_space.canonical_perspective` are true;
   world-coordinate action spaces must keep the decoded fallback;
3. in `_score_action`, handle no-op/invalid and ability IDs exactly as the
   existing decoded path does;
4. for placement IDs set `slot = action_id // NUM_TILES`,
   `tile = action_id % NUM_TILES`, `x = float(tile % BOARD_WIDTH) + 0.5`, and
   `y = float(tile // BOARD_WIDTH) + 0.5`;
5. keep the existing `decode_action` plus `_canonical_position_xy` block under
   the false/reference branch.

The test file exercises the exact required switch and method shape. No CLI,
corpus, metadata, checkpoint, observation, reward, or PPO-policy format change
is required.
