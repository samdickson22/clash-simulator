# Strategy benchmark: update 47

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_balanced_teacher17_joint_seed1075501/policy_v2_update_000047.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -1.750 | 0.1326 | 0.073 | 0.246 |
| slow-push | 0-4-0 | 0.000 | -2.750 | 0.1620 | 0.070 | 0.246 |
| spell-control | 2-2-0 | 0.500 | -0.250 | 0.0482 | 0.071 | 0.062 |
| reactive-defense | 0-4-0 | 0.000 | -1.500 | 0.0801 | 0.074 | 0.246 |
| split-lane | 1-3-0 | 0.250 | -1.000 | 0.1355 | 0.073 | 0.138 |
| balanced | 2-2-0 | 0.500 | +0.000 | 0.0563 | 0.072 | 0.062 |

Mean score: **0.208**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
