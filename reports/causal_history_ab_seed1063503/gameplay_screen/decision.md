# Causal-history gameplay screen

Date: 2026-08-18

## Question

Does the one-epoch type-head fit using source behavior history improve on the
otherwise matched fit whose recurrent previous-action inputs were derived from
oracle labels?

The causal corpus is the only semantically valid corpus.  This screen decides
whether its already-produced one-epoch checkpoint is a safe parent; it does not
make the contaminated checkpoint eligible for future training.

## Contract

- Old arm: `checkpoints/causal_history_ab_seed1063503/old_history_type_e1.pt`
- Clean arm: `checkpoints/causal_history_ab_seed1063503/clean_history_type_e1.pt`
- Four games per opponent, identical seeds and seat alternation
- Opponents: bridge-pressure, slow-push, spell-control, reactive-defense,
  split-lane, balanced
- CPU inference, two Torch threads, `objective-v1`
- 24 games per arm, 48 simulations total

## Result

| Metric | Old-history fit | Clean-history fit |
|---|---:|---:|
| Aggregate score | 15/24 | 14/24 |
| Aggregate crown difference | +4 | +2 |
| Matched outcomes unchanged | - | 23/24 |
| Improvements | - | 0 |
| Regressions | - | 1 |

The only outcome regression was bridge-pressure seed `1066310`, candidate seat
one: old-history win (+1 crown) to clean-history loss (-1 crown).  Slow-push,
spell-control, and reactive-defense game records were byte-identical.  Split-lane
and balanced changed trajectories without changing outcomes.

## Decision

Reject `clean_history_type_e1.pt` as a promotion parent under the predeclared
strict no-regression screen.  Do not use `old_history_type_e1.pt`: its apparent
retention came from causally fabricated recurrent inputs.  Resume from the
pre-mixture `checkpoints/fresh_structured_causal_v1_seed1062701/structured_e3.pt`
and treat the clean-history corpus as valid rehearsal data only in fresh,
independently gated experiments.

The next reward screen must therefore start from one common clean parent rather
than stacking on either history arm.
