# A12 hierarchical masked imitation prototype

## Decision

The bounded prototype is ready for the fresh F0-F3 architecture implementation,
but is deliberately not wired into the dirty accepted-lineage trainer. It adds
only:

- `src/clasher/rl/hierarchical_imitation.py`;
- `tests/test_rl_hierarchical_imitation.py`; and
- this report.

It does not modify `imitation_objective.py`, `imitation.py`, `model.py`, or
`train_recurrent.py`, and it does not change the environment's flat 2,306-action
serialization.

## Contract

The objective consumes three independent model outputs:

1. three logits for `play`, `wait`, and `ability`;
2. four shared-pointer scores for the current hand, conditional on play; and
3. four card-conditioned 576-tile heatmaps.

It consumes legality separately through `HierarchicalPublicMasks`. The helper
`factor_public_action_mask()` derives those tensors using only the public flat
action mask:

- decision support: any playable placement, public no-op legality, public
  ability legality;
- card support: whether each current hand slot has any public-legal tile; and
- tile support: the original public-legal per-card placement mask.

No label is an argument to mask factorization. The objective never edits or
"repairs" a mask to make a target legal; a trusted but illegal target fails
closed.

Labels remain a separate `HierarchicalImitationLabels` object. Each component
has its own trust mask. An untrusted value must be the sentinel `-1`, so weak
evidence cannot silently become wait, hand slot zero, or tile zero. Card
supervision requires a trusted play decision. Tile supervision requires a
trusted play and card identity because the tile map is card-conditioned.

Each component is averaged over its own trusted count. Therefore a batch with
many timing labels and no locations does not dilute a later spatial batch, and
a component with zero trusted rows returns a finite differentiable zero rather
than NaN or a fake target.

## Verified behavior

The focused test suite proves:

- uncertain decision/card/tile labels contribute exactly zero gradient;
- empty card and tile components remain finite and backpropagate zero gradients;
- a simultaneous permutation of hand-pointer logits, card-conditioned
  heatmaps, public masks, and target slot leaves the loss and every metric
  invariant;
- changing targets cannot mutate the original public flat mask or its factored
  tensors;
- inconsistent hierarchical masks, broken trust implications, non-sentinel
  unknowns, and trusted illegal targets fail closed;
- a tiny mixed play/play/ability batch produces finite nonzero gradients through
  all three heads; and
- additive metrics use explicit trusted denominators for overall and per-class
  decisions, conditional card accuracy, exact tile accuracy, and Chebyshev
  within-one-tile accuracy.

Commands:

```bash
uv run ruff check src/clasher/rl/hierarchical_imitation.py tests/test_rl_hierarchical_imitation.py
uv run pytest -q tests/test_rl_hierarchical_imitation.py
uv run mypy src/clasher/rl/hierarchical_imitation.py
```

## Exact fresh-architecture integration plan

1. **Corpus schema.** Emit `decision_target`, `decision_trusted`,
   `card_target`, `card_trusted`, `tile_target`, and `tile_trusted`. Preserve
   fixed-cadence rows. Future frames may confirm a label but must never enter
   `PolicyInputs`. Store `-1` for every untrusted component. Do not restore an
   expert target into a public action mask.
2. **F0 control.** Train the current head from initialization on the same
   corrected corpus and sequences. Do not compare the fresh head against an old
   checkpoint or old data contract.
3. **F1 gate.** Add a learned three-way mode head to the encoder output. Keep
   the old positional card selector for this diagnostic arm.
4. **F2 pointer.** Score each current-hand token with the same learned query and
   scoring function. Keep the control's play-mass formulation for this
   diagnostic arm. Current-hand role embeddings must be shared; Next remains a
   distinct role.
5. **F3 composition.** Use the learned mode gate plus shared pointer and retain
   the exact card-conditioned 18-by-32 heatmap. Compose the flat distribution as
   `P(mode) * P(card | play) * P(tile | card, play)`; map wait and ability to
   flat IDs 2,304 and 2,305. Apply public legality before each conditional
   normalization and verify that the resulting 2,306 probabilities sum to one.
6. **BC hook.** At the fresh trainer boundary, flatten batch and time, derive
   `HierarchicalPublicMasks` from the already-built label-independent actor
   action mask, and call `hierarchical_masked_imitation_loss`. Log component
   losses and trusted counts; never average already-averaged per-minibatch
   metrics without their counts.
7. **PPO hook.** PPO continues to receive the composed flat distribution, so
   replay serialization, action decoding, and exact public legality remain
   unchanged. Do not optimize independent heads with three unrelated PPO
   objectives.
8. **Equivariance gate.** Run all 24 current-hand permutations on at least 1,000
   recurrent states. The semantic card distribution and remapped flat action
   distribution must match within numerical tolerance.
9. **Promotion evidence.** Compare F0-F3 with matched seeds, parameter count
   within five percent, sequences, optimizer, data order, and update budget.
   Screen play/wait/ability calibration and collapse, card accuracy conditional
   on trusted play, spatial NLL/exact/within-one conditional on trusted
   placement, held-out cards/decks, then paired complete games. Offline loss
   alone cannot promote the candidate.

## Deliberate non-goals

This prototype does not choose no-op reweighting, spatial label smoothing,
memory architecture, or corpus confidence thresholds. It also does not claim
that physical hand-slot targets are semantic identities; the fresh corpus must
resolve the played card and then map it to its current public hand token. Those
choices remain separately gated experiments.
