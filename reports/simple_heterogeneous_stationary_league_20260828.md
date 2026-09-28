# Simple Gym heterogeneous stationary league

## Why this exists

The strategy-only PFSP pilot was numerically stable and fast, but failed policy
promotion. Update 20 improved diverse-random and Hog-mirror play while
regressing held-out balanced matchups; later checkpoints lost even those early
gains. The evidence points to opponent-mixture imbalance, not optimizer
instability.

The old Simple Gym league also assigned strategy entries row-by-row while deck
matchups were paired on adjacent rows. A single logical deck matchup could
therefore use different opponent controllers on the two physical seats. That
confounded opponent behavior with learner seat at schedule boundaries.

## New contract

One resident learner-only collector can now mix these opponent kinds in the
same rollout:

- uniform legal random;
- any tensor-native StrategyBot;
- one exact frozen checkpoint policy.

The schedule unit is a logical matchup, not a physical row. Every schedule
entry is duplicated onto adjacent rows with the same deck and opposite learner
seat. Checkpoint recurrence is evaluated only on checkpoint rows and is stored
as zero on every other row. Random sampling and strategy inference likewise
run only on their owned row shards.

The optional `--simple-checkpoint-opponent-deck-name` decouples controller type
from the default diverse opponent deck row. The next Hog-specialist pilot sets
it to `Hog 2.6 Cycle`, producing a true frozen-parent Hog mirror instead of
asking the Hog checkpoint to control an unrelated deck.

Checkpoint metadata now persists:

- the full expanded per-row opponent schedule;
- `opponent_schedule_unit=logical-matchup-pair`;
- the frozen checkpoint SHA-256;
- the checkpoint opponent deck name;
- paired learner seats and exact opponent deck names.

Only one unique checkpoint model is accepted in a Simple Gym mixed league. An
unknown kind, malformed payload, odd environment count, excess matchup slots,
or checkpoint-deck override without a checkpoint fails before simulator
construction.

## Next pilot schedule

`scripts/run_hog26_simple_heterogeneous_seed1164301.sh` freezes 32 logical
matchups across 64 rows:

- 4 random matchups (8 physical rows);
- 4 frozen-parent Hog mirrors (8 rows);
- 8 balanced strategy matchups (16 rows);
- 4 bridge-pressure matchups (8 rows);
- 3 each slow-push, spell-control, reactive-defense, and split-lane matchups
  (24 rows).

The four frozen-parent overrides replace redundant Hog-variant opponent rows.
Random and balanced slots are spread across X-Bow, Wall Breakers, Balloon,
LavaLoon, Giant/Graveyard, Royal Hogs, Graveyard, and Golem deck families.
Every other diverse supported deck remains assigned to a strategy controller.
The script saves every five updates so the early 0-20 window can be screened
without accepting later drift.

## Evidence

- Mixed random/strategy/checkpoint three-decision replay is exact across two
  independently constructed collectors: every rollout array, recurrent state,
  learner boundary, action, reward, done, and outcome matches.
- Frozen checkpoint hidden/cell state is exactly zero on non-checkpoint rows
  and nonzero on checkpoint rows after collection.
- A real CPU PPO update passed with all three opponent kinds, learner-only
  storage, public-mask-v2, and an anchor-policy KL term.
- A real MPS learner+actor PPO update passed with all three opponent kinds.
- A real combined explicit-plus-PFSP CPU update passed.
- A paired CPU smoke persisted the exact row schedule
  `random/random`, `checkpoint/checkpoint`,
  `bridge-pressure/bridge-pressure`, `balanced/balanced`; adjacent rows also
  had identical opponent decks and learner seats `0/1`.
- Broad Simple Gym gate: 455 passed, 261 skipped.
- Focused backend gate: 37 passed, 5 skipped.
- Ruff: clean on the changed source, tests, and run script Python ownership.

No gameplay promotion is claimed. The next production H200 run must still pass
CUDA Graph certification for this exact mixed schedule, then every five-update
checkpoint must face the corrected paired strategy, random, Hog-mirror, and
held-out-archetype gates. The retained champion remains the rollback target.
