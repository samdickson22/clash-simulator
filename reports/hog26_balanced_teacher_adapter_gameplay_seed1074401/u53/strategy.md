# Strategy benchmark: update 53

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_balanced_teacher_adapter_seed1074201/policy_v2_update_000053.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -1.750 | 0.1277 | 0.110 | 0.229 |
| slow-push | 0-4-0 | 0.000 | -3.000 | 0.1469 | 0.097 | 0.229 |
| spell-control | 1-3-0 | 0.250 | -0.750 | 0.0304 | 0.139 | 0.129 |
| reactive-defense | 0-4-0 | 0.000 | -0.250 | 0.0673 | 0.151 | 0.229 |
| split-lane | 1-3-0 | 0.250 | -1.000 | 0.1355 | 0.123 | 0.129 |
| balanced | 2-2-0 | 0.500 | -0.750 | 0.0480 | 0.142 | 0.057 |

Mean score: **0.167**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
