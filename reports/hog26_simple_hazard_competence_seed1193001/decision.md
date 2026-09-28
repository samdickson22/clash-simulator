# Stored-gate competence stage: no promotion

The stored-gate PPO repair is numerically successful but update 6 does not
promote as a policy.

## Training evidence

The repaired run crossed the previous update-3 failure boundary with finite PPO
KL, kept placement cadence near 7%, and reached 36-14 cumulative on-policy
outcomes by update 8.  That proves the sampling/PPO contract is viable.

## Parent-relative evidence

The small retrospective identified update 6 as the only plausible peak (9-3
candidate versus 8-4 parent, crown margin -0.083/game).  The expanded matched
seven-opponent matrix then evaluated 56 games per arm:

- candidate: 29-27, crown margin +0.142857/game
- parent: 30-26, crown margin +0.142857/game
- delta: -1 win, +1 loss, exact crown-margin tie

Candidate improved balanced, reactive-defense, and split-lane results, tied
slow-push/random closely, and regressed bridge-pressure and spell-control.  It
is not a broad improvement and must not replace the retained parent.

The on-policy optimism came from curriculum weighting: 24 of 32 league entries
were random or the frozen parent, while each hard strategy appeared only once
or twice.  The next stage should start again from the retained parent, weight
the actual hard strategy opponents substantially more, reduce LR, and strengthen
the anchor.  Do not continue update 6 or any later checkpoint.

Evidence:

- `development_screens/update_000008/summary.json`
- `retrospective_screens/update_000004/summary.json`
- `retrospective_screens/update_000006/summary.json`
- `retrospective_screens/update_000009/summary.json`
- `promotion_update_000006_seed1193101/summary.json`
