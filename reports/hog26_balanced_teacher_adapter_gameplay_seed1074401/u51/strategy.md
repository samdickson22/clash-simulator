# Strategy benchmark: update 51

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_balanced_teacher_adapter_seed1074201/policy_v2_update_000051.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -1.500 | 0.1161 | 0.090 | 0.291 |
| slow-push | 0-4-0 | 0.000 | -2.500 | 0.1707 | 0.091 | 0.291 |
| spell-control | 2-2-0 | 0.500 | -0.250 | 0.0441 | 0.115 | 0.073 |
| reactive-defense | 1-3-0 | 0.250 | -1.000 | 0.0616 | 0.103 | 0.164 |
| split-lane | 1-3-0 | 0.250 | -0.750 | 0.1250 | 0.097 | 0.164 |
| balanced | 3-1-0 | 0.750 | -0.500 | 0.0726 | 0.107 | 0.018 |

Mean score: **0.292**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
