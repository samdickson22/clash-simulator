# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_equal_plus_u46_spatial_seed1136001/candidate.pt`

Protocol: 4 paired-seat games per opponent, seed 1136202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -1.250 | 0.1011 | 0.071 | 0.235 |
| slow-push | 1-3-0 | 0.250 | -1.500 | 0.1552 | 0.070 | 0.132 |
| spell-control | 1-3-0 | 0.250 | -1.000 | 0.0977 | 0.071 | 0.132 |
| reactive-defense | 1-3-0 | 0.250 | -0.500 | 0.0607 | 0.070 | 0.132 |
| split-lane | 0-4-0 | 0.000 | -1.000 | 0.1103 | 0.071 | 0.235 |
| balanced | 1-3-0 | 0.250 | -0.500 | 0.0588 | 0.069 | 0.132 |

Mean score: **0.167**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
