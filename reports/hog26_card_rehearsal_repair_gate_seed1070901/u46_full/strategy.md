# Strategy benchmark: update 46

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000046.pt`

Protocol: 4 paired-seat games per opponent, seed 1070502, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-3-0 | 0.250 | -1.250 | 0.1345 | 0.055 | 0.138 |
| slow-push | 0-4-0 | 0.000 | -2.250 | 0.1704 | 0.058 | 0.246 |
| spell-control | 2-2-0 | 0.500 | +1.000 | 0.0666 | 0.055 | 0.062 |
| reactive-defense | 0-4-0 | 0.000 | -2.250 | 0.1154 | 0.054 | 0.246 |
| split-lane | 2-2-0 | 0.500 | -0.250 | 0.0957 | 0.054 | 0.062 |
| balanced | 0-4-0 | 0.000 | -1.500 | 0.1216 | 0.058 | 0.246 |

Mean score: **0.208**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
