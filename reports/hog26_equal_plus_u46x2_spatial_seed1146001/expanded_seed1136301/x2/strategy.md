# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_equal_plus_u46x2_spatial_seed1146001/candidate.pt`

Protocol: 8 paired-seat games per opponent, seed 1136302, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-7-0 | 0.125 | -1.625 | 0.1469 | 0.070 | 0.208 |
| slow-push | 0-8-0 | 0.000 | -2.125 | 0.1318 | 0.073 | 0.271 |
| spell-control | 1-7-0 | 0.125 | -1.375 | 0.1001 | 0.070 | 0.208 |
| reactive-defense | 1-7-0 | 0.125 | -0.875 | 0.0410 | 0.072 | 0.208 |
| split-lane | 5-3-0 | 0.625 | +0.500 | 0.1073 | 0.068 | 0.038 |
| balanced | 4-4-0 | 0.500 | -0.125 | 0.0652 | 0.066 | 0.068 |

Mean score: **0.250**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
