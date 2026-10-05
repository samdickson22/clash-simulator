# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_balanced_weighted_spatial_seed1124001/candidate.pt`

Protocol: 4 paired-seat games per opponent, seed 1124202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.000 | 0.1227 | 0.070 | 0.241 |
| slow-push | 0-4-0 | 0.000 | -1.750 | 0.1303 | 0.071 | 0.241 |
| spell-control | 1-3-0 | 0.250 | -0.750 | 0.0860 | 0.069 | 0.136 |
| reactive-defense | 0-4-0 | 0.000 | -1.500 | 0.0787 | 0.072 | 0.241 |
| split-lane | 4-0-0 | 1.000 | +1.500 | 0.0522 | 0.061 | 0.005 |
| balanced | 1-3-0 | 0.250 | -1.000 | 0.0650 | 0.068 | 0.136 |

Mean score: **0.250**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
