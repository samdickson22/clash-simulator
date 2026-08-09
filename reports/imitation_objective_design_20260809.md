# Hierarchical spatial imitation objective design

Date: 2026-08-09

Scope: source-only design while the authoritative 12-worker stable-root corpus
owns CPU. No test, timing loop, model fit, MPS/GPU command, or corpus reader ran.

## Diagnosis

The policy already represents the 2,306 actions hierarchically:

```text
P(slot, tile) = P(slot/type) * P(tile | slot)
```

Consequently, one-hot exact-action cross entropy is already algebraically equal
to exact slot/type NLL plus exact conditional-tile NLL. Merely splitting the old
loss cannot improve supervision. The useful intervention is a conservative soft
target over mechanically similar legal tiles while retaining exact type/card-slot
supervision.

The authoritative playable-state numbers show why metrics must also be split:

| checkpoint | exact action | action type |
| --- | ---: | ---: |
| update-240 control | 2.51% | 27.73% |
| rejected old DAgger fit | 9.10% | 70.61% |

The old fit learned much of the card-slot/no-op decision while still receiving a
very sharp, noisy target among hundreds of legal locations. Aggregate exact-action
accuracy cannot distinguish wrong card selection from a one-tile placement shift.

## Isolated implementation

`src/clasher/rl/imitation_objective.py` adds a loss and additive metrics without
changing `ClasherPolicy`, `PolicyOutput`, `joint_logits`, action sampling, or PPO.

For every placement label it computes:

```text
L = type_coef * -log P(expert slot/type)
  + location_coef * [
        (1 - epsilon) * -log P(expert tile | expert slot)
        + epsilon * CE(legal neighboring tiles, P(tile | expert slot))
    ]
```

When `epsilon=0` and both coefficients are one, this is algebraically identical
to the current exact 2,306-way cross entropy. No-op and champion ability labels
have only the exact type term. Neighbor distributions are normalized only over
currently legal tiles in the expert card slot; illegal tiles always receive zero
target mass.

The expert tile remains dominant. The default mechanics-derived tolerance is:

- building: exact only, because footprint/pathing changes with a one-tile shift;
- troop/champion deployment: 15% mass over legal tiles within one tile, expanding
  at most to 1.5 tiles from serialized formation radius/width;
- area spell: 25% mass within half of its simulator effect radius, capped at two
  tiles and only enabled when at least a neighboring tile fits;
- rolling/line spell: exact only;
- unknown mechanics: exact only.

These are card-class/mechanic rules derived from public immutable stats and the
shared spell registry. There are no card-name branches or enabled-deck cases.
All strengths and radius caps are explicit configuration fields for A/B rather
than hidden constants.

## Metrics

`imitation_metric_sums` returns additive numerators/denominators so evaluation can
aggregate exactly across batches:

- exact action and action type;
- placement count and correct card slot;
- correct-slot placement within one and two Euclidean tiles;
- mechanic-tolerant accuracy;
- correct-slot distance sum/count;
- troop, building, and spell sample/exact/type/tolerant counts.

Manifests should report rates with their denominators and retain exact-action loss
and accuracy as strict compatibility metrics. Forced-only masks should remain
excluded from fit/validation by the authoritative `informative_indices` path.

## PPO semantics

PPO remains exactly unchanged. It continues to construct
`Categorical(logits=output.joint_logits)`, sample exact action IDs, and compute
exact old/new log-probability ratios and entropy. The spatial objective is used
only by offline imitation fitting. The saved model architecture and state-dict
schema are unchanged.

## Precise training-thread port

Cherry-pick the isolated optimizer commit, then edit only the authoritative
`src/clasher/rl/imitation.py`:

1. Import `SpatialImitationConfig`, `build_token_spatial_semantics`,
   `factorized_spatial_imitation_loss`, and `imitation_metric_sums`.
2. After constructing the builder/model/device, build token semantics once; do
   not rebuild or transfer them per batch.
3. Add an explicit objective mode, defaulting to legacy `exact` for checkpoint
   compatibility. Recommended CLI: `--imitation-objective {exact,spatial-v1}`.
4. In `spatial-v1` training, replace only
   `cross_entropy(output.joint_logits[:, 0], targets)` with
   `factorized_spatial_imitation_loss(...).total`. Pass the batch's
   `action_masks`, `hand_ids[:, 0]`, and the prebuilt semantics.
5. Extend `evaluate_imitation` to accumulate the returned loss components and
   `imitation_metric_sums`. Keep old exact loss/accuracy fields and add explicit
   playable type/slot/within-1/within-2/mechanic rates.
6. Serialize the objective name and complete `SpatialImitationConfig` in both
   control/candidate checkpoint metadata and the fit manifest.
7. Do not change `model.py`, PPO, rollout log-probabilities, or inference.

Minimal training-site shape:

```python
output = model(inputs)
joint_logits = output.joint_logits[:, 0]
breakdown = factorized_spatial_imitation_loss(
    joint_logits,
    targets,
    inputs.action_mask[:, 0],
    inputs.hand_ids[:, 0],
    spatial_semantics,
    config=spatial_config,
)
loss = breakdown.total
```

## Required gates after CPU release

The isolated tests are intentionally not executed while the corpus owns all CPU.
After release:

1. Run `tests/test_rl_imitation_objective.py` plus structured-policy and imitation
   suites.
2. Prove zero-smoothing loss and gradients match exact joint CE on fixed tensors.
3. Prove illegal tiles receive no target mass and special actions have zero
   location loss.
4. Evaluate the exact update-240 control under both metric paths without fitting;
   predictions and exact metrics must match bit-for-bit.
5. Run matched exact-CE versus spatial-v1 fits from the same update-240 tensors,
   split, seed, batches, epochs, and learning rate.
6. Publish playable-only label distributions and exact/type/slot/distance/mechanic
   validation metrics by troop/building/spell.
7. Accept only after the same paired-seat random gate and tactical scenario set;
   loss/accuracy improvement alone is insufficient.

The first A/B should keep the conservative defaults. If it over-smooths, reduce
neighbor mass before changing radius; building and rolling-spell exactness should
remain invariant.
