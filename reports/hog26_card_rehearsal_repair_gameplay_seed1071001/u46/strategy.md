# Strategy benchmark: update 46

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000046.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.000 | 0.1297 | 0.057 | 0.213 |
| slow-push | 0-4-0 | 0.000 | -2.750 | 0.1664 | 0.052 | 0.213 |
| spell-control | 1-3-0 | 0.250 | -1.000 | 0.0570 | 0.055 | 0.120 |
| reactive-defense | 0-4-0 | 0.000 | -1.500 | 0.0908 | 0.059 | 0.213 |
| split-lane | 2-1-1 | 0.625 | +0.500 | 0.1689 | 0.056 | 0.030 |
| balanced | 0-4-0 | 0.000 | -1.000 | 0.0694 | 0.058 | 0.213 |

Mean score: **0.146**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
