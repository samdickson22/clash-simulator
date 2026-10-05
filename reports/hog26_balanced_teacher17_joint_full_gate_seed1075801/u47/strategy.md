# Strategy benchmark: update 47

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_balanced_teacher17_joint_seed1075501/policy_v2_update_000047.pt`

Protocol: 4 paired-seat games per opponent, seed 1070502, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-3-0 | 0.250 | -1.500 | 0.1370 | 0.071 | 0.155 |
| slow-push | 0-4-0 | 0.000 | -1.750 | 0.1526 | 0.072 | 0.276 |
| spell-control | 2-2-0 | 0.500 | +0.000 | 0.0576 | 0.077 | 0.069 |
| reactive-defense | 0-4-0 | 0.000 | -1.750 | 0.0971 | 0.071 | 0.276 |
| split-lane | 1-3-0 | 0.250 | -1.250 | 0.0971 | 0.072 | 0.155 |
| balanced | 2-2-0 | 0.500 | +0.000 | 0.0652 | 0.077 | 0.069 |

Mean score: **0.250**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
