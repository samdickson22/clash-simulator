# Strategy benchmark: update 46

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_u46_dagger_spatial_seed1079101/epoch3.pt`

Protocol: 2 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -2.000 | 0.1243 | 0.058 | 0.167 |
| slow-push | 0-2-0 | 0.000 | -2.000 | 0.1506 | 0.063 | 0.167 |
| spell-control | 0-2-0 | 0.000 | -1.000 | 0.0611 | 0.062 | 0.167 |
| reactive-defense | 0-2-0 | 0.000 | -2.500 | 0.1420 | 0.066 | 0.167 |
| split-lane | 0-2-0 | 0.000 | -1.500 | 0.1216 | 0.064 | 0.167 |
| balanced | 0-2-0 | 0.000 | -1.000 | 0.0572 | 0.063 | 0.167 |

Mean score: **0.000**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
