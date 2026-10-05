# Strategy benchmark: update 46

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000046.pt`

Protocol: 8 paired-seat games per opponent, seed 1109302, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 2-6-0 | 0.250 | -1.625 | 0.1326 | 0.054 | 0.138 |
| slow-push | 0-8-0 | 0.000 | -1.875 | 0.1503 | 0.055 | 0.245 |
| spell-control | 3-5-0 | 0.375 | -0.500 | 0.0880 | 0.057 | 0.096 |
| reactive-defense | 0-8-0 | 0.000 | -1.750 | 0.1031 | 0.057 | 0.245 |
| split-lane | 2-6-0 | 0.250 | -0.500 | 0.1150 | 0.053 | 0.138 |
| balanced | 2-6-0 | 0.250 | -1.000 | 0.1001 | 0.057 | 0.138 |

Mean score: **0.188**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
