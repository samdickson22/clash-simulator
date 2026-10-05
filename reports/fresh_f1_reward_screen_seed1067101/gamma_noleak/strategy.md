# Strategy benchmark: update 20

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_f1_reward_screen_seed1067101/gamma_noleak/policy_v2_update_000020.pt`

Protocol: 6 paired-seat games per opponent, seed 1067201, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 2-4-0 | 0.333 | -0.500 | 0.0949 | 0.074 | 0.172 |
| slow-push | 1-5-0 | 0.167 | -1.167 | 0.1325 | 0.064 | 0.269 |
| spell-control | 3-3-0 | 0.500 | +0.167 | 0.0626 | 0.075 | 0.097 |
| reactive-defense | 3-3-0 | 0.500 | -0.333 | 0.0481 | 0.091 | 0.097 |
| split-lane | 3-3-0 | 0.500 | +0.167 | 0.0901 | 0.098 | 0.097 |
| balanced | 1-5-0 | 0.167 | -1.333 | 0.0835 | 0.058 | 0.269 |

Mean score: **0.361**. Worst matchup: **slow-push** at **0.167**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
