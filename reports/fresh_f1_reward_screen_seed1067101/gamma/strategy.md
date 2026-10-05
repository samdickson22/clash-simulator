# Strategy benchmark: update 20

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_f1_reward_screen_seed1067101/gamma/policy_v2_update_000020.pt`

Protocol: 6 paired-seat games per opponent, seed 1067201, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 3-3-0 | 0.500 | +0.167 | 0.0825 | 0.074 | 0.105 |
| slow-push | 1-5-0 | 0.167 | -1.333 | 0.1295 | 0.067 | 0.291 |
| spell-control | 4-2-0 | 0.667 | +0.667 | 0.0685 | 0.072 | 0.047 |
| reactive-defense | 2-4-0 | 0.333 | -0.500 | 0.0575 | 0.098 | 0.186 |
| split-lane | 2-4-0 | 0.333 | -0.167 | 0.0900 | 0.094 | 0.186 |
| balanced | 2-4-0 | 0.333 | -0.667 | 0.0760 | 0.070 | 0.186 |

Mean score: **0.389**. Worst matchup: **slow-push** at **0.167**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
