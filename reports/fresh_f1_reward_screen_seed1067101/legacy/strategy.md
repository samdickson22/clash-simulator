# Strategy benchmark: update 20

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_f1_reward_screen_seed1067101/legacy/policy_v2_update_000020.pt`

Protocol: 6 paired-seat games per opponent, seed 1067201, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 2-4-0 | 0.333 | -0.500 | 0.0850 | 0.069 | 0.203 |
| slow-push | 1-5-0 | 0.167 | -1.500 | 0.1253 | 0.066 | 0.316 |
| spell-control | 2-4-0 | 0.333 | -0.333 | 0.0671 | 0.069 | 0.203 |
| reactive-defense | 4-2-0 | 0.667 | +0.000 | 0.0430 | 0.095 | 0.051 |
| split-lane | 3-3-0 | 0.500 | +0.000 | 0.0974 | 0.102 | 0.114 |
| balanced | 3-3-0 | 0.500 | -0.167 | 0.0806 | 0.067 | 0.114 |

Mean score: **0.417**. Worst matchup: **slow-push** at **0.167**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
