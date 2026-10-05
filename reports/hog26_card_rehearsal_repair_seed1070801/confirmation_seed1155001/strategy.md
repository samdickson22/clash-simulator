# Strategy benchmark: update 46

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000046.pt`

Protocol: 4 paired-seat games per opponent, seed 1155002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.500 | 0.1740 | 0.065 | 0.246 |
| slow-push | 0-4-0 | 0.000 | -2.000 | 0.1327 | 0.065 | 0.246 |
| spell-control | 2-2-0 | 0.500 | +0.750 | 0.0788 | 0.064 | 0.062 |
| reactive-defense | 1-3-0 | 0.250 | -0.500 | 0.0814 | 0.065 | 0.138 |
| split-lane | 2-2-0 | 0.500 | +0.250 | 0.1050 | 0.059 | 0.062 |
| balanced | 0-4-0 | 0.000 | -1.250 | 0.0748 | 0.065 | 0.246 |

Mean score: **0.208**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
