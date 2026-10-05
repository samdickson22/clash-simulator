# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_equal_plus_u46x2_spatial_seed1146001/candidate.pt`

Protocol: 4 paired-seat games per opponent, seed 1136202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -1.250 | 0.1240 | 0.069 | 0.276 |
| slow-push | 0-4-0 | 0.000 | -2.000 | 0.1471 | 0.073 | 0.276 |
| spell-control | 2-2-0 | 0.500 | -0.250 | 0.0860 | 0.074 | 0.069 |
| reactive-defense | 1-3-0 | 0.250 | -0.750 | 0.0610 | 0.070 | 0.155 |
| split-lane | 2-2-0 | 0.500 | +0.500 | 0.0800 | 0.069 | 0.069 |
| balanced | 1-3-0 | 0.250 | -0.750 | 0.0710 | 0.072 | 0.155 |

Mean score: **0.250**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
