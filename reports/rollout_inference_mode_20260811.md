# Exact rollout inference mode

Date: 2026-08-11

## Change

Run the two PPO rollout collectors under `torch.inference_mode()` instead of
`torch.no_grad()`. Both modes disable gradient recording; inference mode also
removes view tracking and version-counter work that actor-only execution never
uses. A private benchmark switch retains the no-grad reference path.

This changes no simulator, action-mask, observation, policy-logit, sampling,
reward, or PPO update code. Returned recurrent tensors are inference tensors;
unit coverage proves exact values and successful reuse by the next collection.

## Machine and attribution conditions

- Apple M4 Pro, 24 GiB RAM
- macOS 26.5.2 arm64
- Python 3.12.13, PyTorch from the locked project environment
- single benchmark process, two Torch threads, `nice -n 15`
- unrelated MPS imitation fitting used about 62% CPU and 24.5% RAM
- one unrelated RoadForge solver used one CPU core

The comparisons alternate reference/candidate order inside one process. The
paired intervals are valid for deciding this low-risk change under shared host
load; absolute rates must not be compared with clean historical runs. Each
95% interval is a deterministic 20,000-resample percentile bootstrap of the
paired mean (seed 0).

## Production-shaped results

Common command shape:

```text
nice -n 15 env PYTHONPATH=src:.:scripts/perf uv run python scripts/perf/benchmark_deployment_blocker_guard_rollout.py --comparison inference-mode --workload WORKLOAD --strategy balanced --seed 3401 --num-envs 8 --rollout-steps STEPS --repetitions PAIRS --warmup-steps 8 --torch-threads 2 --engine-fast-path on --reward-profile defense-v2
```

| workload | shape | no-grad median | inference median | paired median | paired mean | mean 95% CI | positive | digest |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| random | 8 x 32, 7 pairs | 182.043 decisions/s | 184.090 decisions/s | +1.304% | +1.776% | +0.251% to +3.854% | 6/7 | `47cfb083396d0afd791163ac006f3e1f67df31d81e47ae32431a1cc78e027b19` |
| strategy | 8 x 32, 7 pairs | 184.080 decisions/s | 185.906 decisions/s | +0.848% | +2.256% | +0.380% to +5.437% | 6/7 | `d5919d636abd01e9ffe7db299bd9b0b81226278c2744c23149ef598b5d2d5d25` |
| random | 8 x 16, 11 pairs | 191.840 decisions/s | 193.534 decisions/s | +0.600% | +1.339% | +0.432% to +2.590% | 8/11 | `2df2f4bac083bcf0bec1f77cfa687d2eee096b3d80f7494cbfffea5dc671b20e` |
| strategy | 8 x 16, 11 pairs | 180.302 decisions/s | 182.872 decisions/s | +1.047% | +2.102% | +0.413% to +4.648% | 8/11 | `efa0cf4f8f8152c04b99b2fa4f041b8a895497dac82b0a9fe8302db593eacbbd` |

The first pair in each loaded-host screen favored inference mode unusually
strongly. The paired medians remain positive and representative after limiting
that outlier's influence; the longer 11-pair screens also retain positive
bootstrap intervals.

## Scalar, shadow, and optimized parity

Fixed config: stationary random, seed 9989, 8 environments x 64 steps, one
reference/candidate pair per engine mode, defense-v2.

| engine mode | no-grad digest | inference digest | shadow checks | mismatches |
| --- | --- | --- | ---: | ---: |
| off | `db92b946bcc462b52d8a1366335fa7ad9b32373e32d8621690a2790fb9850f8b` | same | 0 | 0 |
| shadow | `3514e81fe182e00fe49324d2090c48241099a77bc8711ff96d9f34c2c88f8cf0` | same | 4 each | 0 |
| on | `db92b946bcc462b52d8a1366335fa7ad9b32373e32d8621690a2790fb9850f8b` | same | 0 | 0 |

Off and on match one another exactly. Shadow intentionally consumes its
established parity-sampling RNG, so its trace differs from off/on while the
reference/candidate shadow traces and metrics match exactly.

## Gates

```text
env PYTHONPATH=src:. uv run pytest -q tests/test_rollout_observation_buffers.py tests/test_rl_structured_policy.py tests/test_rl_determinism_check.py tests/test_rl_opponent_league.py
```

- 18 passed.
- Exact unit comparison covers every rollout array/value and both recurrent
  tensors, then feeds the returned inference state into a second collection.
- PPO-update smoke remains green after inference collection.
- Ruff and `git diff --check` pass.
- Isolated candidate typing is clean; whole-file mypy still reports only the
  eight inherited NumPy local `var-annotated` findings at the rollout/GAE sites.

## Integration

Port the `wraps`/typing imports, `_USE_ROLLOUT_INFERENCE_MODE`, typed
`_rollout_grad_mode`, and the two decorator replacements in
`src/clasher/rl/train_recurrent.py`. Port the inference lifecycle test from
`tests/test_rollout_observation_buffers.py`. The benchmark driver change is
reproducibility-only.
