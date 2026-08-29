# Conditional Hog 2.6 competence curriculum stage 1

Date: 2026-08-29

Status: prepared, not launched.  Launch only if the seed-1192101 long-sequence
update-15 gameplay screen fails to beat the retained parent.

## Rationale

The retained parent scored only 10-62 across the corrected paired strategy
matrix.  The rejected heterogeneous schedules devoted 24/32 logical matchups
to those strong strategy controllers, creating an estimated roughly 80% losing
on-policy distribution before the learner had basic defensive competence.

Stage 1 keeps the proven 64-decision temporal horizon but changes opponent
difficulty, not model architecture or reward:

- random diverse-deck opponents: 14/32 matchups
- frozen-parent Hog mirrors: 10/32
- balanced: 2/32
- slow-push: 2/32
- bridge-pressure, reactive-defense, spell-control, split-lane: 1/32 each

Every logical matchup remains duplicated across both learner seats.  Random
and strategy rows retain diverse opponent decks; frozen-parent rows use the
exact Hog mirror.  Hard opponents remain present from the start, but cannot
dominate the gradient distribution.

## Training and gates

- initializer and safety anchor: retained Hog candidate SHA `28f575c9...4372`
- 64 environments, rollout length 64, sequence minibatch 8
- update 15 stop gate: 61,440 transitions and at least one full terminal cycle
- identical optimizer, reward, public mask, vocabulary, capacity, and entropy
  contracts to seed 1192101
- paired screen against balanced, bridge-pressure, and random at update 15

Reject if update 15 fails to improve total wins without a strategy-bucket
regression.  Only a passing stage-1 checkpoint may initialize a harder stage 2;
stage transitions reset optimizer/simulator state but preserve the original
parent as the anchor and rollback target.
