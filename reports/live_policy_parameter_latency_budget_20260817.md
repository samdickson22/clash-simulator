# Live policy parameter and latency budget

Date: 2026-08-17

## Decision

Use the accepted structured policy's scale—not the historical 6.19M policy—as
the fresh F0-F3 architecture budget.  With the frozen 494-token current-client
vocabulary, target **1.645M-1.670M total trainable parameters** and
**1.053M-1.077M deployable actor/recurrent/action parameters**.  The four arms
span only 1.48% of F0, safely inside the predeclared 5% matching bound.

For batch-one live inference on this M4 Pro, use CPU as the policy device.  The
accepted structured checkpoint's packed current-frame actor call was
1.44/1.50 ms p50/p95 at the small bucket, 1.45/1.48 ms at the median bucket,
1.51/1.53 ms at p95 entity load, and 1.91/1.98 ms in the 67-entity maximum.
MPS was stable but slower: 8.36-8.98 ms p50 inference plus 1.60-1.63 ms p50
tensor ingress.  MPS remains useful for larger vision or training work; it is
not the batch-one policy latency authority.

This closes the architecture queue's size/latency ambiguity.  It does **not**
promote a policy, validate the new 494-token model, or predict H200 latency from
MPS.

## Bound artifacts

- measurement driver:
  `scripts/audit_live_policy_budget.py`
- focused tests:
  `tests/test_audit_live_policy_budget.py`
- raw machine-readable evidence:
  `reports/live_policy_parameter_latency_budget_raw_20260817.json`
- raw evidence SHA-256:
  `f8bfa2821385466e7983f08f545465919b796f00cd0d3331a7884396ee37d9d0`
- source corpus:
  `datasets/derived/fresh_compact_cf_seed1062301/pretrain_balanced.npz`
- source corpus SHA-256:
  `c84d5fbe98f9aacbccb218b73cc1f3549bd016ff9ad39187dce6f8290b1230e1`

The benchmark ran with Python 3.12.13, Torch 2.10.0, two Torch CPU threads,
batch size one, sequence length one, packed entity tensors, 30 warmups, and 100
timed repetitions per checkpoint/device/bucket.  Every arm used deterministic
decoding and retained an exact action digest.  CPU and MPS each passed the
predeclared stability check (`p95 / p50 <= 2.0`) in all 16 measurements.

## Checkpoint authority and parameter partition

### Accepted structured policy

- path:
  `checkpoints/fresh_structured_causal_v1_seed1062701/resource_belief_gated_seed1063602/resource_u10_gate0.pt`
- SHA-256:
  `3353615954fdcfdb24f2ba570f1888cd6130242238391a9bcf98dcedbcfc5b88`
- trainable parameters: **1,536,447**
- state-dict tensor elements, including persistent buffers: **1,554,519**

| Partition | Parameters | Deployment status |
|---|---:|---|
| Actor encoder, model-owned recurrence, action/type/tile heads | 1,009,378 | live actor |
| Privileged critic encoder | 496,128 | learner only |
| Value head | 16,641 | learner/evaluation only |
| Opponent-hand/elixir auxiliary heads | 14,300 | training diagnostics only |
| **Total training-only** | **527,069** | exclude from actor artifact |

The value head currently also runs when the full `model.act()` method is called
without privileged critic tensors.  The latency numbers therefore conservatively
include its actor-global readout and the opponent auxiliary readouts.  Exporting
an actor-only module can remove their parameters and work, but that optimization
is not claimed here.

### Historical 6.19M accepted policy

The exact historical accepted artifact is absent from the current checkout:

- recorded path:
  `checkpoints/mechanics_slot_probe/accepted6m_zero_seed1056701/zero_adapter.pt`
- recorded SHA-256:
  `cf783bdef5c3ce0b529606839b3887a3e3457045394642ad72466cc3087cc305`
- recorded trainable count: **6,194,196**

The available `human_safety_student6m_u64_interp050.pt` was measured only as a
same-family 6M architecture reference.  It is **not** claimed weight-equivalent
to the missing accepted file:

- SHA-256:
  `5485e85df4a4d9ac0158f41d67ec293a44a8c1dddb5a6e0ad36d62a8d068e9e8`
- trainable parameters: **6,170,628**
- deployable actor/recurrent/action: **4,556,967**
- training-only critic/value/auxiliary: **1,613,661**

This reference remained fast enough on CPU (2.08/2.24 ms median-bucket p50/p95,
3.15/3.33 ms crowded) but provides no accuracy argument for spending four times
the structured model's deployable parameters.

## Entity-load authority

The 121,917-row causal corpus has packed visible-entity counts of 6 at p05, 10
at p50, 17 at p95, and 67 at the maximum.  The driver selects an actual row with
each exact count and trims only trailing padding; it does not synthesize a
different board.

### Accepted structured checkpoint

| Device | Bucket | Entities | Serialization p50/p95 ms | Inference p50/p95 ms | Combined p50/p95 ms |
|---|---|---:|---:|---:|---:|
| CPU | p05 | 6 | 0.017 / 0.020 | 1.444 / 1.499 | 1.461 / 1.517 |
| CPU | p50 | 10 | 0.017 / 0.019 | 1.447 / 1.476 | 1.464 / 1.493 |
| CPU | p95 | 17 | 0.017 / 0.019 | 1.506 / 1.531 | 1.523 / 1.547 |
| CPU | max | 67 | 0.017 / 0.018 | 1.907 / 1.982 | 1.925 / 1.999 |
| MPS | p05 | 6 | 1.595 / 1.737 | 8.474 / 8.804 | 10.088 / 10.485 |
| MPS | p50 | 10 | 1.632 / 1.768 | 8.797 / 9.512 | 10.435 / 11.140 |
| MPS | p95 | 17 | 1.633 / 1.758 | 8.978 / 9.337 | 10.627 / 10.996 |
| MPS | max | 67 | 1.610 / 1.668 | 8.362 / 8.604 | 9.969 / 10.223 |

### Available 6M-family reference

| Device | Bucket | Entities | Serialization p50/p95 ms | Inference p50/p95 ms | Combined p50/p95 ms |
|---|---|---:|---:|---:|---:|
| CPU | p05 | 6 | 0.011 / 0.016 | 2.137 / 2.383 | 2.149 / 2.399 |
| CPU | p50 | 10 | 0.011 / 0.013 | 2.083 / 2.240 | 2.094 / 2.252 |
| CPU | p95 | 17 | 0.011 / 0.017 | 2.182 / 2.580 | 2.193 / 2.591 |
| CPU | max | 67 | 0.011 / 0.013 | 3.153 / 3.329 | 3.165 / 3.340 |
| MPS | p05 | 6 | 1.502 / 1.562 | 7.497 / 7.821 | 9.000 / 9.353 |
| MPS | p50 | 10 | 1.471 / 1.556 | 7.706 / 8.000 | 9.171 / 9.476 |
| MPS | p95 | 17 | 1.503 / 1.564 | 7.408 / 7.536 | 8.904 / 9.089 |
| MPS | max | 67 | 1.274 / 1.384 | 8.238 / 8.512 | 9.442 / 9.826 |

“Serialization” here means NumPy current-frame arrays to device-resident policy
tensors and confidence tensors.  It excludes video decoding, vision inference,
neutral-state construction, networking, and action dispatch.  CPU's near-zero
number benefits from zero-copy `torch.as_tensor`; the caller must keep the NumPy
storage alive for the call.

## Fresh F0-F3 matched parameter target

The 494-token F0 calculation preserves the accepted structured trunk and grows
only the actor/critic token embeddings plus the opponent-hand auxiliary output
from 155 to 494 IDs.  It sets `canonical_lane_globals=true`; that flag changes
no parameter shape.

| Arm | Head change | Total target | Deployable actor target | Delta vs F0 |
|---|---|---:|---:|---:|
| F0 | Current positional slot/type head | 1,645,266 | 1,052,770 | 0 |
| F1 | Three-way gate + positional four-card head | 1,645,331 | 1,052,835 | +65 |
| F2 | Current timing control + shared card pointer | 1,669,582 | 1,077,086 | +24,316 |
| F3 | Three-way gate + shared card pointer | 1,669,647 | 1,077,151 | +24,381 |

The pointer arithmetic is a bias-free `Linear(d_model + memory_size, d_model)`
query over shared hand-card tokens.  The heatmap, actor/critic trunks, and
structured memory remain unchanged.  If the implemented pointer needs a small
normalization/bias layer, pad the smaller arms with training-neutral hidden
capacity—not duplicated card-specific heads—so every final arm remains within
5% of the largest arm.  Parameter matching does not permit behavior-changing
post-hoc adapters.

## Live 400 ms cadence budget

The following is the acceptance budget for F0-F3 on the intended live device:

| Component | p50 maximum | p95 maximum |
|---|---:|---:|
| Tensor serialization | 1.0 ms | 2.5 ms |
| Ordinary policy inference (through p95 entity load) | 10 ms | 20 ms |
| Crowded policy inference | 15 ms | 25 ms |
| Ordinary serialization + policy | — | 25 ms |
| Crowded serialization + policy | — | 30 ms |

The crowded combined ceiling consumes 7.5% of the 400 ms decision interval and
leaves at least 370 ms for vision, state assembly, scheduling jitter, transport,
and action dispatch.  CPU passes every policy/serialization gate.  MPS passes
the inference and p95 serialization ceilings but misses the 1.0 ms p50
serialization target, another reason not to route this batch-one policy through
MPS.

Online search remains outside this budget.  If introduced later, it retains the
separate 100 ms p95 / 200 ms hard-maximum queried-search gate and must run on at
most 10% of decisions.  No CUDA/H100/H200 latency should be inferred from these
MPS measurements; benchmark the final exported actor directly on the rented
device.

## Reproduction and gates

```bash
uv run python scripts/audit_live_policy_budget.py \
  --warmups 30 \
  --repetitions 100 \
  --torch-threads 2 \
  --output reports/live_policy_parameter_latency_budget_raw_20260817.json

uv run ruff check \
  scripts/audit_live_policy_budget.py \
  tests/test_audit_live_policy_budget.py
uv run mypy scripts/audit_live_policy_budget.py
uv run pytest -q tests/test_audit_live_policy_budget.py
```

Validation: Ruff clean, script mypy clean, and 3 focused tests passed.  No
checkpoint, production model, trainer, or gameplay state was modified; no
training was run.
