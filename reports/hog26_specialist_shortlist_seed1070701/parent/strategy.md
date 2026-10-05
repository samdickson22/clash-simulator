# Strategy benchmark: update 28

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_f3_hazard_parentheavy_ab_seed1069901/plain/policy_v2_update_000028.pt`

Protocol: 4 paired-seat games per opponent, seed 1070702, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.500 | 0.1196 | 0.054 | 0.229 |
| slow-push | 0-4-0 | 0.000 | -2.250 | 0.1671 | 0.054 | 0.229 |
| spell-control | 1-3-0 | 0.250 | -1.000 | 0.0822 | 0.055 | 0.129 |
| reactive-defense | 1-3-0 | 0.250 | -1.000 | 0.0548 | 0.054 | 0.129 |
| split-lane | 2-2-0 | 0.500 | -0.250 | 0.1239 | 0.053 | 0.057 |
| balanced | 0-4-0 | 0.000 | -1.500 | 0.0863 | 0.057 | 0.229 |

Mean score: **0.167**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
