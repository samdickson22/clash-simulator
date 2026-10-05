# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_balanced_only_spatial_seed1122001/candidate.pt`

Protocol: 4 paired-seat games per opponent, seed 1122202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.000 | 0.0958 | 0.069 | 0.180 |
| slow-push | 0-4-0 | 0.000 | -2.000 | 0.1166 | 0.072 | 0.180 |
| spell-control | 1-3-0 | 0.250 | -1.000 | 0.0696 | 0.067 | 0.101 |
| reactive-defense | 0-4-0 | 0.000 | -1.750 | 0.1027 | 0.073 | 0.180 |
| split-lane | 0-4-0 | 0.000 | -2.000 | 0.0875 | 0.067 | 0.180 |
| balanced | 0-4-0 | 0.000 | -1.000 | 0.0542 | 0.064 | 0.180 |

Mean score: **0.042**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
