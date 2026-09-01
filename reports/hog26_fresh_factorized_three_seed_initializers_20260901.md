# Fresh factorized Hog 2.6 three-seed initializer gate

Date: 2026-09-01

Status: all three initializers pass offline behavior and free-play cadence gates;
all remain 0-4 and require matched outcome RL.  No checkpoint is promoted.

## Fixed pipeline

Every seed used the same architecture, 167,631/54,333-row recurrent behavior
train/validation split, five-epoch behavior gate, 78,693/25,470-row executed
six-strategy phase, three-epoch gate, MPS training, and deterministic Simple Gym
balanced/random collapse screen.  Epoch selection thresholds and ranking were
frozen before seeds 2 and 3.

## Selected executed-state checkpoints

| seed | selected epoch | SHA-256 | exact | play recall | wait accuracy | card accuracy | tile accuracy |
|---:|---:|---|---:|---:|---:|---:|---:|
| 1244001 | 1 | `3b651bce56b036b8948eefa0f0b85611c19ac558cbd86e64bece399f23ae3cc5` | 84.42% | 97.03% | 92.22% | 96.65% | 28.74% |
| 1244002 | 1 | `6be554863e9cf2254e7503e3cebccdc25fb8b29682825142e0bcfd4c948788e6` | 84.74% | 97.55% | 92.21% | 96.75% | 31.54% |
| 1244003 | 3 | `1c8323ce6fef49ef8d6420aeb4c2c400b896223a69568e4d86a137f628235776` | 84.89% | 97.96% | 92.02% | 96.79% | 33.89% |

## Free-playing collapse screen

Each checkpoint played two deterministic games against balanced and two against
random, with paired learner seats and natural terminal outcomes.

| seed | W-L | balanced placement | random placement |
|---:|---:|---:|---:|
| 1244001 | 0-4 | 11.11% | 11.33% |
| 1244002 | 0-4 | 13.68% | 11.33% |
| 1244003 | 0-4 | 11.35% | 11.06% |

All twelve games lost.  Unlike the pure-BC one-epoch and epoch-4 checkpoints,
none of the executed-state initializers collapsed to waiting against balanced.
They consistently act and reach long games, but do not yet convert tower/crown
outcomes.

## Decision

Stop imitation-depth work.  The failure is now outcome competence, not cadence
or card recognition.  Run the exact control/action-value CUDA A/B independently
for all three initializers using
`scripts/run_hog26_joint_action_value_cuda_ab.sh`.  A candidate must retain at
least 95% of control CUDA throughput, improve the matched league/collapse result,
and introduce no strategy-bucket regression before any longer run.
