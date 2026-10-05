# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt`

Protocol: 8 paired-seat games per opponent, seed 1136302, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 3-5-0 | 0.375 | -0.500 | 0.1532 | 0.070 | 0.212 |
| slow-push | 4-4-0 | 0.500 | +0.000 | 0.1408 | 0.072 | 0.136 |
| spell-control | 2-6-0 | 0.250 | -0.875 | 0.1048 | 0.069 | 0.305 |
| reactive-defense | 4-4-0 | 0.500 | -0.625 | 0.0600 | 0.068 | 0.136 |
| split-lane | 5-3-0 | 0.625 | +0.500 | 0.1034 | 0.068 | 0.076 |
| balanced | 4-4-0 | 0.500 | +0.250 | 0.0761 | 0.068 | 0.136 |

Mean score: **0.458**. Worst matchup: **spell-control** at **0.250**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
