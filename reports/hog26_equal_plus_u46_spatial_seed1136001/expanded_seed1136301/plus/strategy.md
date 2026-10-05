# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_equal_plus_u46_spatial_seed1136001/candidate.pt`

Protocol: 8 paired-seat games per opponent, seed 1136302, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-8-0 | 0.000 | -2.000 | 0.1584 | 0.069 | 0.300 |
| slow-push | 1-7-0 | 0.125 | -1.750 | 0.1421 | 0.072 | 0.230 |
| spell-control | 0-8-0 | 0.000 | -1.750 | 0.1083 | 0.072 | 0.300 |
| reactive-defense | 4-4-0 | 0.500 | -0.625 | 0.0554 | 0.070 | 0.075 |
| split-lane | 6-2-0 | 0.750 | +0.375 | 0.0972 | 0.069 | 0.019 |
| balanced | 4-4-0 | 0.500 | +0.000 | 0.0725 | 0.068 | 0.075 |

Mean score: **0.312**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
