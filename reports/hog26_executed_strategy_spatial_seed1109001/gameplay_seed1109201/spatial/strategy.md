# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_executed_strategy_spatial_seed1109001/candidate.pt`

Protocol: 4 paired-seat games per opponent, seed 1109202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.500 | 0.1718 | 0.071 | 0.213 |
| slow-push | 0-4-0 | 0.000 | -2.750 | 0.1517 | 0.071 | 0.213 |
| spell-control | 1-3-0 | 0.250 | -1.250 | 0.1047 | 0.064 | 0.120 |
| reactive-defense | 0-4-0 | 0.000 | -1.250 | 0.0880 | 0.073 | 0.213 |
| split-lane | 1-3-0 | 0.250 | -1.250 | 0.1194 | 0.070 | 0.120 |
| balanced | 1-3-0 | 0.250 | -1.500 | 0.1098 | 0.075 | 0.120 |

Mean score: **0.125**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
