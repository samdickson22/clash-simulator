# Exact scalar structured-observation clipping

Date: 2026-08-11

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

## Change and attribution

Structured entity and global features repeatedly clipped Python scalar values
by dispatching through `numpy.clip`. A production-shaped 8-environment random
rollout profile attributed 0.209 seconds to 80,507 `_unit_clip` calls. The
candidate replaces that scalar NumPy dispatch with two ordered comparisons and
returns the input float when it is already in range.

The comparison order preserves the reference behavior for finite values,
infinities, NaN, and negative zero. It does not change observation layout,
dtype, legal actions, rewards, battle state, RNG consumption, or policy
semantics. There are no card-name or enabled-deck branches.

## Bounded shared-CPU benchmark

- Apple M4 Pro, 12 logical CPUs, 24 GiB RAM
- macOS 26.5.2 arm64; Python 3.12 through `uv`
- fixed battle/model seed 2301; exact fast path on
- 8 environments, 32 decisions, 8 untimed warmup decisions
- 7 matched pairs per workload, alternating reference/candidate order
- 2 Torch CPU threads; preallocated rollout observation buffers enabled
- invoked with `nice -n 10`
- a single RoadForge reconstruction process was active at approximately one
  CPU core throughout; no Clasher model-training process was visible before
  either timed command

Commands:

```bash
nice -n 10 env PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_rollout.py \
  --workload random --seed 2301 --num-envs 8 --rollout-steps 32 \
  --repetitions 7 --warmup-steps 8 --torch-threads 2 \
  --engine-fast-path on --observation-buffers preallocated \
  --unit-clip both

nice -n 10 env PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_rollout.py \
  --workload strategy --strategy balanced --seed 2301 --num-envs 8 \
  --rollout-steps 32 --repetitions 7 --warmup-steps 8 \
  --torch-threads 2 --engine-fast-path on \
  --observation-buffers preallocated --unit-clip both
```

| workload | NumPy median seconds | scalar median seconds | NumPy decisions/s | scalar decisions/s | median-rate gain |
| --- | ---: | ---: | ---: | ---: | ---: |
| stationary random | 1.405842 | 1.342225 | 182.097255 | 190.728053 | **+4.74%** |
| balanced strategy | 1.383869 | 1.335278 | 184.988558 | 191.720406 | **+3.64%** |

The within-repetition elapsed-time gains were positive in all 14 matched
pairs. Random's paired gain median was 4.53% (mean 5.31%, sample standard
deviation 2.58 percentage points, approximate two-sided 95% t interval for
the mean 2.92% to 7.70%). Strategy's paired gain median was 3.54% (mean 3.46%,
sample standard deviation 1.95 points, interval 1.66% to 5.27%). The loaded
host makes absolute rates nonportable; alternating pairs isolate the source
change and both intervals remain positive.

All 14 random rows produced full-rollout digest
`8bcf61259509b1f2f80750fa29ccaf695ba9f11e46b46e2967069d2d90fce432`.
All 14 strategy rows produced
`67faf6c5e975db614868686ead0c2515840dfd02729342a228127e837f22844d`.

This optimization also applies to actor-only DAgger corpus observation
serialization. It does not run inside the exact oracle planner's battle-tree
inner loop, so no planner-only speedup is claimed.

## Exactness and focused gates

```text
12 scalar boundary/NaN/infinity/signed-zero bit-parity cases passed
59 structured-policy/rollout/action-mask/DAgger focused tests passed
benchmark, owned test, and changed helper Ruff clean (excluding inherited
  structured_obs import-modernization findings)
py_compile and git diff --check clean
mypy reports only the inherited untyped action_space._is_legal_deploy argument
```

Canonical fixed-seed command, repeated for `off`, `shadow`, and `on`:

```bash
nice -n 10 env PYTHONPATH=src:. uv run python \
  -m clasher.rl.determinism_check --seed 2301 --decisions 64 \
  --max-ticks 2048 --trials 2 --quiet-engine \
  --engine-fast-path MODE --reward-profile defense-v2
```

Every scalar/off, shadow, and optimized/on trial produced digest
`9f190f2efd15954d8105db43b2352e8b50c1bafd3fea9f2921964c6123389349`.
Shadow performed one mask check per trial with zero mismatches.

## Integration

Cherry-pick the isolated commit. The production source change is only the
`_unit_clip` helper in `src/clasher/rl/structured_obs.py`. The retained
`_unit_clip_numpy` helper is an internal benchmark reference. The remaining
files are a direct parity test, the existing bounded rollout driver's new
`--unit-clip` selector, and this report.
