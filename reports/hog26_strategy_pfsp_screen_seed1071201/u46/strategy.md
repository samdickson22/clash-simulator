# Strategy benchmark: update 46

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000046.pt`

Protocol: 2 paired-seat games per opponent, seed 1071202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -3.000 | 0.1143 | 0.051 | 0.222 |
| slow-push | 0-2-0 | 0.000 | -3.000 | 0.1643 | 0.056 | 0.222 |
| spell-control | 1-1-0 | 0.500 | +0.500 | 0.0406 | 0.059 | 0.056 |
| reactive-defense | 0-2-0 | 0.000 | -1.000 | 0.1118 | 0.055 | 0.222 |
| split-lane | 1-1-0 | 0.500 | +1.000 | 0.1059 | 0.054 | 0.056 |
| balanced | 0-2-0 | 0.000 | -1.500 | 0.0912 | 0.059 | 0.222 |

Mean score: **0.167**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
