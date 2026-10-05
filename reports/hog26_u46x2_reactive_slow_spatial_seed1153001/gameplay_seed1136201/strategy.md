# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_u46x2_reactive_slow_spatial_seed1153001/candidate.pt`

Protocol: 4 paired-seat games per opponent, seed 1136202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 3-1-0 | 0.750 | +1.000 | 0.0886 | 0.068 | 0.030 |
| slow-push | 1-3-0 | 0.250 | -1.500 | 0.1163 | 0.072 | 0.273 |
| spell-control | 1-3-0 | 0.250 | -0.750 | 0.0991 | 0.071 | 0.273 |
| reactive-defense | 1-3-0 | 0.250 | -0.250 | 0.0501 | 0.071 | 0.273 |
| split-lane | 2-2-0 | 0.500 | +0.000 | 0.1047 | 0.070 | 0.121 |
| balanced | 3-1-0 | 0.750 | +0.500 | 0.0628 | 0.065 | 0.030 |

Mean score: **0.458**. Worst matchup: **slow-push** at **0.250**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
