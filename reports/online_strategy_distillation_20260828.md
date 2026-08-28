# On-policy hierarchical StrategyBot distillation

## Motivation

Two numerically stable PPO campaigns with different opponent mixtures failed
the same broad promotion gate. They moved wins between matchup buckets but did
not create a robust improvement. The balanced public-information StrategyBot,
by contrast, scored 19-9 in the existing Hog teacher matrix across all six
strategy opponents plus random, with a 0.679 mean score and no matchup below
0.5.

That matrix used the tuned Candidate-17 `BalancedStrategyConfig`, not the
default balanced configuration. The first seed-1164501 pilot did not persist
or load Candidate-17 and therefore distilled the weaker default controller.
Every saved checkpoint from that run lost a 12-game balanced/bridge/random
screen 0-12, so the entire seed-1164501 lineage is rejected. It is evidence
against the default teacher at learning rate `5e-5`, not evidence against the
tuned teacher.

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
name and, when balanced, every exact configuration weight. A supplied balanced
configuration is rejected for any other teacher name, preventing silent
fallback to defaults.

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
- Candidate-17 tensor actions exactly match the Python StrategyBot on initial
  and pressured public states.
- CPU and MPS checkpoint metadata exactly preserve all 13 Candidate-17 values.
- Broad Simple Gym gate after tuned-config integration: 459 passed, 260 skipped.
- Focused backend gate: 39 passed, 5 skipped.
- Ruff and isolated Simple backend mypy: clean.

A 10-update CPU learning probe confirmed end-to-end operation on changing
learner states. Timing and card agreement were already near-perfect for the
retained champion; the remaining loss was overwhelmingly exact tile placement.
This identifies spatial teacher supervision—not more no-op/action-type fitting—
as the useful signal for the first production pilot.

## Pilot

`scripts/run_hog26_simple_tuned_teacher_pilot_seed1164521.sh` uses the paired
heterogeneous league, the exact versioned Candidate-17 learner-state teacher,
independently normalized decision/card/tile losses, play weight 4, learning
rate `1e-5`, and anchor-policy KL coefficient `0.1`. It deliberately runs only
20 updates and saves every two updates for early free-running rejection.

No promotion is implied by teacher loss or teacher agreement. Every checkpoint
must still be screened in free-running paired gameplay against strategy,
random, Hog mirror, and held-out archetype gates.

## Result

The exact tuned pilot is rejected. The parent scored 4-8 in the matched
balanced/bridge/random screen; the best trained checkpoints scored 3-9 and no
checkpoint matched the parent. See
`reports/hog26_simple_tuned_teacher_pilot_seed1164521/decision_20260828.md`.
This closes coefficient/configuration tuning of StrategyBot distillation as the
next move. A future spatial repair must use outcome- or value-ranked targets
and pass free-running gates before policy fine-tuning.
