# Strategy benchmark: update 46

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000046.pt`

Protocol: 2 paired-seat games per opponent, seed 1083202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -3.000 | 0.2050 | 0.055 | 0.190 |
| slow-push | 0-2-0 | 0.000 | -1.500 | 0.1414 | 0.054 | 0.190 |
| spell-control | 1-1-0 | 0.500 | +0.000 | 0.0799 | 0.057 | 0.048 |
| reactive-defense | 0-2-0 | 0.000 | -2.500 | 0.1347 | 0.055 | 0.190 |
| split-lane | 0-2-0 | 0.000 | -1.000 | 0.1401 | 0.057 | 0.190 |
| balanced | 0-2-0 | 0.000 | -2.500 | 0.1363 | 0.055 | 0.190 |

Mean score: **0.083**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
