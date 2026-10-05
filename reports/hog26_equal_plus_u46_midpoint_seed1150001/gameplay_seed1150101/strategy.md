# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_equal_plus_u46_midpoint_seed1150001/candidate.pt`

Protocol: 4 paired-seat games per opponent, seed 1136202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -1.250 | 0.1124 | 0.071 | 0.213 |
| slow-push | 1-3-0 | 0.250 | -1.750 | 0.1672 | 0.070 | 0.120 |
| spell-control | 0-4-0 | 0.000 | -1.250 | 0.0914 | 0.073 | 0.213 |
| reactive-defense | 0-4-0 | 0.000 | -1.000 | 0.0591 | 0.071 | 0.213 |
| split-lane | 1-3-0 | 0.250 | +0.000 | 0.0824 | 0.069 | 0.120 |
| balanced | 1-3-0 | 0.250 | -1.000 | 0.0894 | 0.070 | 0.120 |

Mean score: **0.125**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
