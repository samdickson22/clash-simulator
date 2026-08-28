# On-policy hierarchical StrategyBot distillation

## Motivation

Two numerically stable PPO campaigns with different opponent mixtures failed
the same broad promotion gate. They moved wins between matchup buckets but did
not create a robust improvement. The balanced public-information StrategyBot,
by contrast, scored 19-9 in the existing Hog teacher matrix across all six
strategy opponents plus random, with a 0.679 mean score and no matchup below
0.5.

Prior offline StrategyBot imitation reached high aggregate exact accuracy by
predicting abundant no-ops, but recalled only about 42% of teacher plays and
had weak spatial accuracy. The new route changes both the data distribution and
the objective.

## Contract

The resident Simple Gym collector may now evaluate one tensor StrategyBot on
the learner's own pre-action public state at every rollout decision. These are
DAgger-style labels on the current policy's state distribution; the teacher
does not drive the trajectory and receives no critic/private state.

Every teacher label is checked against public-mask-v2 before use. The PPO batch
stores only the learner-seat label. Checkpoint metadata persists the teacher
name.

The auxiliary loss factors the flat action into independently normalized
components:

1. play vs wait vs ability;
2. card slot, only on teacher placements;
3. tile, conditioned on the teacher card slot.

Play decisions receive a configurable sample weight so wait frequency cannot
drown them out. Card and tile denominators contain only placements, so their
gradient does not shrink when a batch contains many waits. PPO, value, entropy,
anchor-KL, and teacher terms remain separately reported.

## Evidence

- Synthetic loss test proves nonzero timing/card/tile gradients, with tile
  gradients confined to the teacher-selected card and placement row.
- Resident teacher labels are public-legal and have exact learner-only shape.
- Real CPU PPO+teacher update passed.
- Real MPS learner+actor PPO+teacher update passed.
- Broad Simple Gym gate: 457 passed, 261 skipped.
- Focused backend gate: 39 passed, 5 skipped.
- Ruff and isolated Simple backend mypy: clean.

A 10-update CPU learning probe confirmed end-to-end operation on changing
learner states. Timing and card agreement were already near-perfect for the
retained champion; the remaining loss was overwhelmingly exact tile placement.
This identifies spatial teacher supervision—not more no-op/action-type fitting—
as the useful signal for the first production pilot.

## Pilot

`scripts/run_hog26_simple_balanced_teacher_seed1164501.sh` uses the paired
heterogeneous league, the balanced learner-state teacher, independently
normalized decision/card/tile losses, play weight 4, learning rate `5e-5`, and
anchor-policy KL coefficient `0.1`. It runs through one terminal horizon and
saves every five updates.

No promotion is implied by teacher loss or teacher agreement. Every checkpoint
must still be screened in free-running paired gameplay against strategy,
random, Hog mirror, and held-out archetype gates.
