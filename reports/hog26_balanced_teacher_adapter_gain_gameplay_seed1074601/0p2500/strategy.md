# Strategy benchmark: update 51

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_balanced_teacher_adapter_gain_sweep_seed1074501/policy_v2_update_000051_gain_0p2500.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.000 | 0.1307 | 0.062 | 0.213 |
| slow-push | 0-4-0 | 0.000 | -2.500 | 0.1338 | 0.054 | 0.213 |
| spell-control | 1-3-0 | 0.250 | -1.000 | 0.0547 | 0.068 | 0.120 |
| reactive-defense | 0-4-0 | 0.000 | -1.750 | 0.0964 | 0.061 | 0.213 |
| split-lane | 1-3-0 | 0.250 | -0.750 | 0.1936 | 0.062 | 0.120 |
| balanced | 1-3-0 | 0.250 | -0.500 | 0.0642 | 0.064 | 0.120 |

Mean score: **0.125**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
