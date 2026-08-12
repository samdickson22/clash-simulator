# Exact scalar structured-entity range clipping

Date: 2026-08-11

Worktree: `/Users/sam/.codex/worktrees/f872/clasher`

## Change

After `adce131` removed scalar NumPy dispatch for `[0, 1]` observation
features, each visible entity still used `numpy.clip` three times for its
data-driven entity-kind index and normalized facing vector. This candidate
uses the same exact ordered scalar comparisons for those remaining bounded
values.

The scalar helper preserves finite values, infinities, NaN, and signed zero
bit-for-bit against NumPy. It changes no feature index, shape, dtype, entity
order, legal action, reward, battle state, RNG use, or policy semantics. There
are no card-name or enabled-deck branches.

## Direct fixed-state attribution

- Apple M4 Pro, 12 logical CPUs, 24 GiB RAM, macOS 26.5.2 arm64
- Python 3.12 through `uv`
- seed 2301; one state after 24 fixed random-legal decision windows
- 512 full actor/critic observation builds per row
- 11 alternating matched pairs after 8 warmup builds per variant
- invoked with `nice -n 10`
- one RoadForge CPU reconstruction and a Clasher MPS imitation fit were active

```bash
nice -n 10 env PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_structured_entity_range_clip.py \
  --seed 2301 --state-decisions 24 --builds 512 --repetitions 11
```

| variant | median seconds | mean seconds | stdev | median builds/s |
| --- | ---: | ---: | ---: | ---: |
| NumPy range clip | 0.050504 | 0.050575 | 0.001293 | 10,137.861 |
| scalar range clip | 0.027283 | 0.027083 | 0.001084 | 18,766.150 |

This is **+85.11%** by median build rate. The within-pair gain median was
86.48% (mean 86.87%, sample standard deviation 4.66 points, approximate
two-sided 95% t interval for the mean 83.74% to 90.00%). All 22 rows produced
observation digest
`08851e1b15b3619563faf68f50f635666e67788b316feda9db5b4317800da478`.

## Production-shaped rollout evidence

Both screens fixed `adce131`'s unit clip and preallocated observation buffers
on, alternating only this range helper. They used 8 environments, 8 warmup
decisions, 2 Torch threads, the exact fast path, and `nice -n 10` under the
same shared workload.

```bash
nice -n 10 env PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_rollout.py \
  --workload random --seed 2301 --num-envs 8 --rollout-steps 32 \
  --repetitions 7 --warmup-steps 8 --torch-threads 2 \
  --engine-fast-path on --observation-buffers preallocated \
  --unit-clip scalar --entity-range-clip both

nice -n 10 env PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_rollout.py \
  --workload strategy --strategy balanced --seed 2301 --num-envs 8 \
  --rollout-steps 16 --repetitions 11 --warmup-steps 8 \
  --torch-threads 2 --engine-fast-path on \
  --observation-buffers preallocated --unit-clip scalar \
  --entity-range-clip both
```

| workload | NumPy median seconds | scalar median seconds | NumPy decisions/s | scalar decisions/s | median-rate gain | paired gain median |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| stationary random, 32 steps | 1.800702 | 1.758041 | 142.166810 | 145.616647 | **+2.43%** | +2.02% |
| balanced strategy, 16 steps | 0.805140 | 0.794319 | 158.978472 | 161.144250 | **+1.36%** | +1.44% |

The strategy confirmation was run after a first 32-step screen suffered one
unrelated between-variant host spike. Its seven-pair central estimate was still
positive (+0.79% paired median), but the unpaired median was discarded. The
11-pair confirmation above is the accepted production screen. Shared-load
outliers keep the rollout confidence intervals wide; the direct attribution
has low variance and explains the stable positive central estimates.

Every random row produced full-rollout digest
`8bcf61259509b1f2f80750fa29ccaf695ba9f11e46b46e2967069d2d90fce432`.
Every accepted strategy row produced
`d87bdd871c9bb012c55aff818085f7da385061d83e445c632a601bdb23737590`.

## Exactness and focused gates

```text
20 range-boundary/NaN/infinity/signed-zero bit-parity cases passed
49 structured-policy/rollout/DAgger focused tests passed
Ruff, py_compile, and git diff --check clean for owned changes
```

Canonical fixed-seed off, shadow, and on runs all produced digest
`9f190f2efd15954d8105db43b2352e8b50c1bafd3fea9f2921964c6123389349`
for both trials. Shadow performed one action-mask check per trial with zero
mismatches.

## Integration

Cherry-pick the isolated commit after `adce131`. The production hunk is the
range helper plus three call sites in `src/clasher/rl/structured_obs.py`. The
NumPy reference helper and selector exist only for the retained benchmark.
The other files are exact tests, bounded benchmark support, and this report.
