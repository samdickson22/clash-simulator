# Strategy benchmark: update 47

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_balanced_teacher17_choice_seed1075901/policy_v2_update_000047.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.000 | 0.1365 | 0.059 | 0.222 |
| slow-push | 0-4-0 | 0.000 | -2.500 | 0.1705 | 0.049 | 0.222 |
| spell-control | 2-2-0 | 0.500 | +0.000 | 0.0524 | 0.061 | 0.056 |
| reactive-defense | 0-4-0 | 0.000 | -1.750 | 0.1004 | 0.055 | 0.222 |
| split-lane | 2-2-0 | 0.500 | -0.500 | 0.1752 | 0.058 | 0.056 |
| balanced | 0-4-0 | 0.000 | -1.250 | 0.0830 | 0.057 | 0.222 |

Mean score: **0.167**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
