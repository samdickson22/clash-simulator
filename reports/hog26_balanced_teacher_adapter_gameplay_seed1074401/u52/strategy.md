# Strategy benchmark: update 52

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_balanced_teacher_adapter_seed1074201/policy_v2_update_000052.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-3-0 | 0.250 | -1.000 | 0.1088 | 0.110 | 0.132 |
| slow-push | 0-4-0 | 0.000 | -2.750 | 0.1554 | 0.093 | 0.235 |
| spell-control | 1-3-0 | 0.250 | -0.750 | 0.0374 | 0.112 | 0.132 |
| reactive-defense | 1-3-0 | 0.250 | -1.000 | 0.0876 | 0.115 | 0.132 |
| split-lane | 1-3-0 | 0.250 | -1.000 | 0.1339 | 0.111 | 0.132 |
| balanced | 0-4-0 | 0.000 | -1.000 | 0.0610 | 0.124 | 0.235 |

Mean score: **0.167**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
