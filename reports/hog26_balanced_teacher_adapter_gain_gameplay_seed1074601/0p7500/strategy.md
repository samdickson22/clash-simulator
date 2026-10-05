# Strategy benchmark: update 51

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_balanced_teacher_adapter_gain_sweep_seed1074501/policy_v2_update_000051_gain_0p7500.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.500 | 0.1435 | 0.080 | 0.267 |
| slow-push | 0-4-0 | 0.000 | -2.000 | 0.1429 | 0.084 | 0.267 |
| spell-control | 2-2-0 | 0.500 | +0.000 | 0.0438 | 0.089 | 0.067 |
| reactive-defense | 0-4-0 | 0.000 | -1.500 | 0.0989 | 0.080 | 0.267 |
| split-lane | 2-2-0 | 0.500 | +0.250 | 0.1346 | 0.088 | 0.067 |
| balanced | 2-2-0 | 0.500 | -0.250 | 0.0469 | 0.081 | 0.067 |

Mean score: **0.250**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
