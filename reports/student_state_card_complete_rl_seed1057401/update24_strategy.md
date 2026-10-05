# Strategy benchmark: update 24

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/student_state_card_complete_rl_seed1057401/policy_v2_update_000024.pt`

Protocol: 4 paired-seat games per opponent, seed 1057401, reward profile `defense-v2`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 3-1-0 | 0.750 | +0.750 | 0.1168 | 0.060 | 0.075 |
| slow-push | 4-0-0 | 1.000 | +1.750 | 0.1300 | 0.030 | 0.024 |
| spell-control | 3-1-0 | 0.750 | +1.750 | 0.0642 | 0.064 | 0.075 |
| reactive-defense | 3-1-0 | 0.750 | +0.250 | 0.0826 | 0.062 | 0.075 |
| split-lane | 3-1-0 | 0.750 | +0.750 | 0.0777 | 0.052 | 0.075 |
| balanced | 1-3-0 | 0.250 | -0.250 | 0.1016 | 0.061 | 0.676 |

Mean score: **0.708**. Worst matchup: **balanced** at **0.250**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
