# Hog 2.6 parallel online-teacher bridge

Date: 2026-09-01

## Decision

The fast Python bridge now supports public/legal online strategy labels on the
learner's own visited states.  Full teacher supervision is rejected.  Spatial-
only supervision at coefficient 0.10 is retained as a development lineage, but
it is not promoted because its Python gameplay gain did not yet improve the
matched Simple Gym result.

## Implementation contract

The parallel CPU actor workers can now construct a data/config-driven
`StrategyBot` teacher for the learner seat.  Before each policy action they:

- use the already-computed public legal action mask;
- select the teacher action without mutating the environment;
- persist one teacher label per learner transition;
- concatenate labels across workers into the existing PPO batch;
- apply the existing independently weighted decision/card/tile imitation loss.

A real four-environment/two-worker MPS smoke published an exact teacher-action
field, verified every label legal, and backpropagated finite decision/card/tile
loss.  Comparing the 28-environment teacher rollout against the prior plain
control found zero differences in every non-teacher rollout field.

## Rejected controls

- Plain PPO to update 100 remained 0-2 against balanced at every staged
  checkpoint and regressed random from 2-0 at initialization to 0-2 at updates
  40, 80, and 100 (update 60 was 1-1).  Stop.
- Full teacher coefficient 0.25 shifted aggregate six-game balanced from 0-6 to
  1-5 but random from 5-1 to 3-3.  Stop.
- Spatial-only coefficient 0.25 improved strategy play but lost one matched
  random game on the breadth seed.  It was superseded by the lower weight.

## Spatial-only coefficient 0.10

Checkpoint:

- path: `/private/tmp/hog26-legacy-spatial-teacher010-u20-seed1248201/checkpoints/policy_v2_update_000020.pt`
- SHA-256:
  `4ec5585f63fd65c30ed977b78a87cc66208ab64d7e125116f1dd32f7d120d8f4`
- transitions: 35,840

On the fixed two-game breadth seed, compared with the initializer:

| opponent | initializer | spatial 0.10 |
|---|---:|---:|
| bridge-pressure | 2-0 | 2-0 |
| slow-push | 0-2 | 2-0 |
| spell-control | 1-1 | 1-1 |
| reactive-defense | 1-1 | 1-1 |
| split-lane | 1-1 | 1-1 |
| balanced | 1-1 | 1-1 |
| random | 2-0 | 1-1 |

The disputed random bucket was expanded.  Across 16 games, initializer was
12-4 and spatial 0.10 was 13-3, eliminating the apparent aggregate regression.
Across three balanced seed groups, initializer was 1-7 and spatial 0.10 was
2-6.  The most material strategy gain was slow-push.

## Simple Gym transfer gate

The exact same base/candidate pair was evaluated with seeded deterministic
policy behavior on MPS against balanced and random, two games each.  Both went
0-4.  All games were legal and naturally terminated at decision 449; placement
rates were 10.89%/11.33% for base and 11.56%/11.33% for candidate.

Therefore the Python result is promising development evidence but not verified
cross-backend skill.  It cannot replace the retained initializer or champion.
Further spatial training is allowed only with staged rollback checkpoints, and
promotion still requires a CUDA Simple-Gym breadth gate.

## Performance finding

The matched four-game Simple/MPS arms each took about 22 minutes and grew to
roughly 5-6 GiB RSS.  The evaluator now explicitly releases each opponent
collector and empties the MPS cache between opponent buckets.  Future broad
Simple evaluation should use the packaged CUDA Graph route.
