# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_executed_strategy_spatial_seed1109001/candidate.pt`

Protocol: 4 paired-seat games per opponent, seed 1112202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-3-0 | 0.250 | -1.250 | 0.1426 | 0.069 | 0.223 |
| slow-push | 1-3-0 | 0.250 | -1.500 | 0.1697 | 0.072 | 0.223 |
| spell-control | 2-2-0 | 0.500 | +0.250 | 0.0743 | 0.069 | 0.099 |
| reactive-defense | 1-3-0 | 0.250 | -1.250 | 0.1138 | 0.072 | 0.223 |
| split-lane | 4-0-0 | 1.000 | +1.000 | 0.0572 | 0.071 | 0.008 |
| balanced | 1-3-0 | 0.250 | -0.750 | 0.0895 | 0.071 | 0.223 |

Mean score: **0.417**. Worst matchup: **bridge-pressure** at **0.250**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
