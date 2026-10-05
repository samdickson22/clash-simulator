# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_executed_strategy_spatial_seed1109001/candidate.pt`

Protocol: 8 paired-seat games per opponent, seed 1136302, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-8-0 | 0.000 | -2.250 | 0.1488 | 0.069 | 0.227 |
| slow-push | 0-8-0 | 0.000 | -2.125 | 0.1348 | 0.073 | 0.227 |
| spell-control | 0-8-0 | 0.000 | -1.875 | 0.0996 | 0.068 | 0.227 |
| reactive-defense | 4-4-0 | 0.500 | -0.375 | 0.0425 | 0.070 | 0.057 |
| split-lane | 1-7-0 | 0.125 | -1.000 | 0.1163 | 0.069 | 0.174 |
| balanced | 3-5-0 | 0.375 | -0.250 | 0.0775 | 0.069 | 0.089 |

Mean score: **0.167**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
