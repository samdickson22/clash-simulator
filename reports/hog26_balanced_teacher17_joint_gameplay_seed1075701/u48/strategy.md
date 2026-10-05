# Strategy benchmark: update 48

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_balanced_teacher17_joint_seed1075501/policy_v2_update_000048.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.000 | 0.1196 | 0.084 | 0.320 |
| slow-push | 0-4-0 | 0.000 | -2.250 | 0.1228 | 0.085 | 0.320 |
| spell-control | 3-1-0 | 0.750 | +0.500 | 0.0280 | 0.095 | 0.020 |
| reactive-defense | 2-2-0 | 0.500 | -0.500 | 0.0646 | 0.085 | 0.080 |
| split-lane | 2-2-0 | 0.500 | -0.250 | 0.1402 | 0.085 | 0.080 |
| balanced | 1-3-0 | 0.250 | -0.500 | 0.0541 | 0.085 | 0.180 |

Mean score: **0.333**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
