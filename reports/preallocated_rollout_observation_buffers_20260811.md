# Preallocated CPU rollout observation buffers

Date: 2026-08-11

## Scope

The recurrent collector previously stacked the same ten actor/critic
observation arrays twice per learner step: once into rollout storage and again
into contiguous policy input arrays. CPU actor collection now allocates one
contiguous step buffer per field, fills it with `numpy.stack(..., out=...)`,
copies that exact buffer into rollout storage, and exposes the same contiguous
memory to `torch.as_tensor` for synchronous CPU inference. The buffers are
reused across steps. Non-CPU actor inference, bootstrap inputs, evaluation,
and checkpoint-opponent inputs retain the established stacking path.

This changes no observation builder, action mask, policy input dtype/shape,
action sampling, reward, or battle logic.

## Machine and shared-load controls

- Apple M4 Pro, 24 GiB RAM
- macOS 26.5.2 arm64
- Python 3.12.13 through `uv`
- one bounded low-priority benchmark process, eight environments, two Torch
  threads, 32 rollout decisions, seven alternating repetitions per variant
- no optimizer-owned MPS/GPU or multi-process work
- shared load remained active: one Clasher MPS imitation fit, one Clasher CPU
  evaluation, and one RoadForge CPU reconstruction
- candidate and reference alternated in one process; each run recreated the
  same model RNG, environments, and battle seeds

The loaded measurements are intentionally attributed as production-shaped
shared-host evidence, not an exclusive-window microbenchmark.

## Commands

```bash
nice -n 10 env PYTHONPATH=src:. uv run python \
  scripts/perf/benchmark_stationary_rollout.py \
  --workload random --seed 2301 --num-envs 8 --rollout-steps 32 \
  --repetitions 7 --warmup-steps 2 --torch-threads 2 \
  --engine-fast-path on --target-cache-refresh reuse \
  --building-cache-refresh reuse --targetability-refresh classified \
  --crown-fallback-membership cached \
  --crown-distance-order preferred-first \
  --inactive-stealth-time deferred --bucket-id-sort inplace \
  --targetability-fields direct --bucket-scan-order row-major \
  --bucket-geometry cached --building-membership trusted \
  --mover-hover-trait cached --avoidance-candidates bucketed \
  --collision-plane-fields direct --unit-mass cached \
  --collision-radius cached --target-plane-checks coalesced \
  --observation-buffers both

# Repeat with --workload strategy --strategy balanced.
```

## Results

| workload | duplicate stacks | preallocated buffers | gain |
| --- | ---: | ---: | ---: |
| stationary random | 1.624269 s / 157.609 decisions/s | 1.615387 s / 158.476 decisions/s | **+0.55%** |
| balanced strategy | 1.646862 s / 155.447 decisions/s | 1.639394 s / 156.155 decisions/s | **+0.46%** |

All fourteen random rows produced full-rollout digest
`8bcf61259509b1f2f80750fa29ccaf695ba9f11e46b46e2967069d2d90fce432`.
All fourteen strategy rows produced
`67faf6c5e975db614868686ead0c2515840dfd02729342a228127e837f22844d`.
The digest covers every rollout array plus final battle tick, winner, and live
entity count for each environment.

## Exactness gates

```text
2 buffer/tensor/full fixed-rollout parity tests passed
51 collector/structured-policy/action-mask/reward/league tests passed
train_recurrent.py mypy clean
scalar/off = shadow = optimized/on digest
  9f190f2efd15954d8105db43b2352e8b50c1bafd3fea9f2921964c6123389349
shadow checks = 1 per trial; shadow mismatches = 0
new test and benchmark additions Ruff/format/py_compile clean
git diff --check clean
```

## Integration

Cherry-pick after `bedc010`. The training branch has independent edits in
`train_recurrent.py`; if cherry-pick conflicts, port these exact source pieces:

1. `_USE_PREALLOCATED_STEP_OBSERVATION_BUFFERS` and the shared observation
   field tuple;
2. `_stack_observation_arrays`, `_step_inputs_from_stacked_observations`, and
   `_empty_step_observation_arrays`;
3. one CPU-only reusable buffer allocation in each collector and use of that
   buffer for both rollout storage and learner policy inputs.

Do not replace the bootstrap or checkpoint-opponent `_stack_step_inputs` calls.
