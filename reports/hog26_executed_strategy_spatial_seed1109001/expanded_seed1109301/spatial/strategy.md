# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_executed_strategy_spatial_seed1109001/candidate.pt`

Protocol: 8 paired-seat games per opponent, seed 1109302, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 2-6-0 | 0.250 | -1.750 | 0.1127 | 0.070 | 0.161 |
| slow-push | 0-8-0 | 0.000 | -2.125 | 0.1427 | 0.073 | 0.286 |
| spell-control | 3-5-0 | 0.375 | -0.375 | 0.0875 | 0.069 | 0.112 |
| reactive-defense | 1-7-0 | 0.125 | -0.875 | 0.0996 | 0.071 | 0.219 |
| split-lane | 3-5-0 | 0.375 | -0.375 | 0.0886 | 0.069 | 0.112 |
| balanced | 3-5-0 | 0.375 | -0.625 | 0.0837 | 0.074 | 0.112 |

Mean score: **0.250**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
