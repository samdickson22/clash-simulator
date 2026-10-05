# Strategy benchmark: update 56

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_strategy_majority_seed1075001/policy_v2_update_000056.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.000 | 0.1344 | 0.058 | 0.180 |
| slow-push | 0-4-0 | 0.000 | -2.500 | 0.1901 | 0.051 | 0.180 |
| spell-control | 0-4-0 | 0.000 | -1.000 | 0.0538 | 0.058 | 0.180 |
| reactive-defense | 0-4-0 | 0.000 | -1.750 | 0.0918 | 0.058 | 0.180 |
| split-lane | 1-3-0 | 0.250 | -1.000 | 0.1669 | 0.056 | 0.101 |
| balanced | 0-4-0 | 0.000 | -1.000 | 0.0792 | 0.055 | 0.180 |

Mean score: **0.042**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
