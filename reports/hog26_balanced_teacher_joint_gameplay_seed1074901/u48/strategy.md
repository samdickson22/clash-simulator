# Strategy benchmark: update 48

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_balanced_teacher_joint_seed1074701/policy_v2_update_000048.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -1.750 | 0.1281 | 0.085 | 0.258 |
| slow-push | 0-4-0 | 0.000 | -2.250 | 0.1252 | 0.086 | 0.258 |
| spell-control | 2-2-0 | 0.500 | -0.500 | 0.0380 | 0.083 | 0.065 |
| reactive-defense | 0-4-0 | 0.000 | -1.250 | 0.0752 | 0.087 | 0.258 |
| split-lane | 1-3-0 | 0.250 | -1.000 | 0.1520 | 0.086 | 0.145 |
| balanced | 3-1-0 | 0.750 | +0.500 | 0.0430 | 0.093 | 0.016 |

Mean score: **0.250**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
