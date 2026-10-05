# Strategy benchmark: update 28

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_f3_hazard_parentheavy_ab_seed1069901/plain/policy_v2_update_000028.pt`

Protocol: 4 paired-seat games per opponent, seed 1070502, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -1.750 | 0.1330 | 0.054 | 0.208 |
| slow-push | 0-4-0 | 0.000 | -2.000 | 0.1493 | 0.054 | 0.208 |
| spell-control | 2-2-0 | 0.500 | +0.000 | 0.0652 | 0.061 | 0.052 |
| reactive-defense | 0-4-0 | 0.000 | -2.250 | 0.1156 | 0.053 | 0.208 |
| split-lane | 0-4-0 | 0.000 | -1.500 | 0.1084 | 0.056 | 0.208 |
| balanced | 1-3-0 | 0.250 | -0.750 | 0.1091 | 0.056 | 0.117 |

Mean score: **0.125**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
