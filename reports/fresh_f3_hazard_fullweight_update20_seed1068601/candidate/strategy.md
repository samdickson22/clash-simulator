# Strategy benchmark: update 20

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000020.pt`

Protocol: 6 paired-seat games per opponent, seed 1068601, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-6-0 | 0.000 | -2.333 | 0.1166 | 0.055 | 0.216 |
| slow-push | 0-6-0 | 0.000 | -2.333 | 0.1326 | 0.046 | 0.216 |
| spell-control | 0-6-0 | 0.000 | -1.333 | 0.0649 | 0.051 | 0.216 |
| reactive-defense | 1-5-0 | 0.167 | -0.833 | 0.0837 | 0.045 | 0.150 |
| split-lane | 3-3-0 | 0.500 | +0.000 | 0.0821 | 0.048 | 0.054 |
| balanced | 1-5-0 | 0.167 | -1.000 | 0.0894 | 0.048 | 0.150 |

Mean score: **0.139**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
