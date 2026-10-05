# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt`

Protocol: 4 paired-seat games per opponent, seed 1136202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 3-1-0 | 0.750 | +0.750 | 0.1045 | 0.068 | 0.025 |
| slow-push | 3-1-0 | 0.750 | +0.500 | 0.1311 | 0.073 | 0.025 |
| spell-control | 0-4-0 | 0.000 | -1.500 | 0.1062 | 0.074 | 0.400 |
| reactive-defense | 2-2-0 | 0.500 | -0.250 | 0.0620 | 0.070 | 0.100 |
| split-lane | 1-3-0 | 0.250 | -0.250 | 0.0962 | 0.071 | 0.225 |
| balanced | 1-3-0 | 0.250 | -0.500 | 0.0943 | 0.071 | 0.225 |

Mean score: **0.417**. Worst matchup: **spell-control** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
