# Strategy benchmark: update 45

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000045.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.000 | 0.1434 | 0.056 | 0.180 |
| slow-push | 0-4-0 | 0.000 | -3.000 | 0.1837 | 0.053 | 0.180 |
| spell-control | 0-4-0 | 0.000 | -1.250 | 0.0601 | 0.068 | 0.180 |
| reactive-defense | 0-4-0 | 0.000 | -1.750 | 0.1078 | 0.061 | 0.180 |
| split-lane | 1-3-0 | 0.250 | -0.500 | 0.1659 | 0.055 | 0.101 |
| balanced | 0-4-0 | 0.000 | -1.000 | 0.0705 | 0.058 | 0.180 |

Mean score: **0.042**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
