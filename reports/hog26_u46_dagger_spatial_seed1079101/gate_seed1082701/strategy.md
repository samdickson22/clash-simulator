# Strategy benchmark: update 46

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_u46_dagger_spatial_seed1079101/epoch3.pt`

Protocol: 2 paired-seat games per opponent, seed 1082702, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -1.500 | 0.2331 | 0.064 | 0.190 |
| slow-push | 0-2-0 | 0.000 | -2.500 | 0.1399 | 0.066 | 0.190 |
| spell-control | 1-1-0 | 0.500 | -0.500 | 0.0715 | 0.067 | 0.048 |
| reactive-defense | 0-2-0 | 0.000 | -2.500 | 0.0850 | 0.066 | 0.190 |
| split-lane | 0-2-0 | 0.000 | -1.000 | 0.0725 | 0.062 | 0.190 |
| balanced | 0-2-0 | 0.000 | -2.000 | 0.0673 | 0.062 | 0.190 |

Mean score: **0.083**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
