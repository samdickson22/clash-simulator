# Strategy benchmark: update 0

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_medium_reactive_dagger2_seed1078701/epoch5.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 2-2-0 | 0.500 | +0.000 | 0.0873 | 0.124 | 0.075 |
| slow-push | 0-4-0 | 0.000 | -2.500 | 0.1750 | 0.097 | 0.302 |
| spell-control | 2-2-0 | 0.500 | -0.250 | 0.0416 | 0.145 | 0.075 |
| reactive-defense | 0-4-0 | 0.000 | -1.000 | 0.0795 | 0.142 | 0.302 |
| split-lane | 1-3-0 | 0.250 | -0.500 | 0.1091 | 0.136 | 0.170 |
| balanced | 2-2-0 | 0.500 | -1.000 | 0.0555 | 0.137 | 0.075 |

Mean score: **0.292**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
