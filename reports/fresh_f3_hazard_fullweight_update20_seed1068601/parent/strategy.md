# Strategy benchmark: update 10

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000010.pt`

Protocol: 6 paired-seat games per opponent, seed 1068601, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-6-0 | 0.000 | -2.833 | 0.1428 | 0.021 | 0.176 |
| slow-push | 0-6-0 | 0.000 | -3.000 | 0.2121 | 0.021 | 0.176 |
| spell-control | 0-6-0 | 0.000 | -3.000 | 0.1146 | 0.019 | 0.176 |
| reactive-defense | 0-6-0 | 0.000 | -2.667 | 0.1249 | 0.020 | 0.176 |
| split-lane | 1-5-0 | 0.167 | -1.667 | 0.1088 | 0.020 | 0.122 |
| balanced | 0-6-0 | 0.000 | -2.667 | 0.1141 | 0.019 | 0.176 |

Mean score: **0.028**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
