# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_executed_strategy_spatial_seed1109001/candidate.pt`

Protocol: 4 paired-seat games per opponent, seed 1136202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-3-0 | 0.250 | -1.000 | 0.1110 | 0.069 | 0.143 |
| slow-push | 0-4-0 | 0.000 | -2.000 | 0.1387 | 0.072 | 0.254 |
| spell-control | 0-4-0 | 0.000 | -1.500 | 0.0971 | 0.075 | 0.254 |
| reactive-defense | 2-2-0 | 0.500 | +0.250 | 0.0522 | 0.073 | 0.063 |
| split-lane | 1-3-0 | 0.250 | -0.250 | 0.0610 | 0.067 | 0.143 |
| balanced | 1-3-0 | 0.250 | -0.750 | 0.0744 | 0.070 | 0.143 |

Mean score: **0.208**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
