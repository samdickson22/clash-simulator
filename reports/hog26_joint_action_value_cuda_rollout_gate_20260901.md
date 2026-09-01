# Hog 2.6 joint-Q pre-optimization rollout gate

Date: 2026-09-01

## Decision

The transferable CUDA A/B now fails closed unless the control and joint-Q arms
collect the exact same first rollout before GAE or optimization.  This closes a
gap in the earlier package, which proved shared initial model tensors but did
not persist or compare the resulting trajectories.

## Contract

- Every NumPy array in `RolloutBatch` is hashed from its dtype, shape, and
  contiguous bytes.
- Scalar outcome counters and absent optional fields are included.
- The audit is written before GAE and PPO, is atomically published, and refuses
  to overwrite prior evidence.
- The A/B driver compares the aggregate rollout hash and attributes any mismatch
  to exact named fields.
- The three-seed driver pins the exact SHA-256 of every initializer before any
  CUDA work begins.

## Local end-to-end smoke

A real two-environment, one-step Simple Gym collection was run independently for
the control and zero-gated joint-Q arms on CPU with seed `1246001`.  Both audits
were byte-identical:

`18c11507f44b28a9bc121ac88b450a008bd3f06d684ec3f83ee2ca2dcfcfb4c0`

The candidate also produced finite nonzero selected-action Q loss (`1.6878`)
while the control Q loss remained zero.  This smoke proves the audit is wired to
the real recurrent collector.  It is not CUDA throughput or gameplay evidence.

## Gates

- Bash syntax clean for both CUDA drivers.
- Ruff clean for owned Python changes.
- Mypy clean for `rollout_audit.py` and `train_recurrent.py`.
- `57 passed, 5 skipped` across rollout audit, CUDA driver, joint-Q,
  factorized-pretrain, and Simple backend focused tests.
- Local end-to-end control/candidate first-rollout equality passed.

The next required evidence remains the one-update, three-seed CUDA Graph smoke,
followed by the five-update matched pilot only if every device gate passes.
