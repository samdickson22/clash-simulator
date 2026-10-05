# Strategy benchmark: update 46

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000046.pt`

Protocol: 2 paired-seat games per opponent, seed 1083502, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-1-0 | 0.500 | -1.000 | 0.1017 | 0.051 | 0.048 |
| slow-push | 0-2-0 | 0.000 | -2.000 | 0.1179 | 0.058 | 0.190 |
| spell-control | 0-2-0 | 0.000 | -1.500 | 0.1027 | 0.058 | 0.190 |
| reactive-defense | 0-2-0 | 0.000 | -2.000 | 0.0831 | 0.058 | 0.190 |
| split-lane | 0-2-0 | 0.000 | -1.500 | 0.1764 | 0.060 | 0.190 |
| balanced | 0-2-0 | 0.000 | -1.000 | 0.0767 | 0.056 | 0.190 |

Mean score: **0.083**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
