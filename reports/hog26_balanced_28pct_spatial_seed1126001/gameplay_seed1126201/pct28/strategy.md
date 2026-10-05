# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_balanced_28pct_spatial_seed1126001/candidate.pt`

Protocol: 4 paired-seat games per opponent, seed 1126202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.500 | 0.1755 | 0.070 | 0.229 |
| slow-push | 1-3-0 | 0.250 | -1.250 | 0.1324 | 0.073 | 0.129 |
| spell-control | 2-2-0 | 0.500 | -0.250 | 0.0767 | 0.070 | 0.057 |
| reactive-defense | 1-3-0 | 0.250 | -1.500 | 0.1000 | 0.067 | 0.129 |
| split-lane | 0-4-0 | 0.000 | -1.750 | 0.1313 | 0.070 | 0.229 |
| balanced | 0-4-0 | 0.000 | -1.250 | 0.0653 | 0.065 | 0.229 |

Mean score: **0.167**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
