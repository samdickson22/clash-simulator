# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_executed_strategy_spatial_seed1109001/candidate.pt`

Protocol: 4 paired-seat games per opponent, seed 1122202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-3-0 | 0.250 | -1.000 | 0.1097 | 0.069 | 0.175 |
| slow-push | 0-4-0 | 0.000 | -2.000 | 0.1295 | 0.073 | 0.312 |
| spell-control | 4-0-0 | 1.000 | +1.000 | 0.0442 | 0.064 | 0.006 |
| reactive-defense | 0-4-0 | 0.000 | -2.000 | 0.1152 | 0.071 | 0.312 |
| split-lane | 1-3-0 | 0.250 | -1.000 | 0.0881 | 0.066 | 0.175 |
| balanced | 3-1-0 | 0.750 | +0.500 | 0.0626 | 0.071 | 0.019 |

Mean score: **0.375**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
