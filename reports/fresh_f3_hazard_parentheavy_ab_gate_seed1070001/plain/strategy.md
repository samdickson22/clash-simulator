# Strategy benchmark: update 28

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_f3_hazard_parentheavy_ab_seed1069901/plain/policy_v2_update_000028.pt`

Protocol: 4 paired-seat games per opponent, seed 1070002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-3-0 | 0.250 | -0.500 | 0.1082 | 0.052 | 0.237 |
| slow-push | 0-4-0 | 0.000 | -2.000 | 0.1529 | 0.047 | 0.421 |
| spell-control | 2-2-0 | 0.500 | +0.000 | 0.0745 | 0.051 | 0.105 |
| reactive-defense | 2-2-0 | 0.500 | +0.500 | 0.0654 | 0.048 | 0.105 |
| split-lane | 3-1-0 | 0.750 | +1.000 | 0.0719 | 0.052 | 0.026 |
| balanced | 2-2-0 | 0.500 | +0.500 | 0.0873 | 0.048 | 0.105 |

Mean score: **0.417**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
