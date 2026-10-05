# Strategy benchmark: update 51

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_balanced_teacher_adapter_gain_sweep_seed1074501/policy_v2_update_000051_gain_0p5000.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.000 | 0.1413 | 0.074 | 0.235 |
| slow-push | 0-4-0 | 0.000 | -2.250 | 0.1351 | 0.073 | 0.235 |
| spell-control | 1-3-0 | 0.250 | -0.750 | 0.0493 | 0.077 | 0.132 |
| reactive-defense | 1-3-0 | 0.250 | -1.250 | 0.0863 | 0.077 | 0.132 |
| split-lane | 1-3-0 | 0.250 | -0.250 | 0.1349 | 0.077 | 0.132 |
| balanced | 1-3-0 | 0.250 | -0.500 | 0.0594 | 0.080 | 0.132 |

Mean score: **0.167**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
