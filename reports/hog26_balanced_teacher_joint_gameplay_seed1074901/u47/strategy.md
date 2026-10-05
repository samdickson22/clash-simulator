# Strategy benchmark: update 47

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_balanced_teacher_joint_seed1074701/policy_v2_update_000047.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -1.750 | 0.1443 | 0.073 | 0.195 |
| slow-push | 0-4-0 | 0.000 | -2.500 | 0.1666 | 0.070 | 0.195 |
| spell-control | 1-3-0 | 0.250 | -1.000 | 0.0560 | 0.078 | 0.110 |
| reactive-defense | 0-4-0 | 0.000 | -1.750 | 0.0830 | 0.078 | 0.195 |
| split-lane | 1-3-0 | 0.250 | -0.500 | 0.1580 | 0.074 | 0.110 |
| balanced | 0-4-0 | 0.000 | -1.250 | 0.0719 | 0.075 | 0.195 |

Mean score: **0.083**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
