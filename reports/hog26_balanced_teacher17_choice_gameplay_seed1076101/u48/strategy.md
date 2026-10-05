# Strategy benchmark: update 48

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_balanced_teacher17_choice_seed1075901/policy_v2_update_000048.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-3-0 | 0.250 | -1.750 | 0.1564 | 0.051 | 0.120 |
| slow-push | 0-4-0 | 0.000 | -2.000 | 0.1567 | 0.050 | 0.213 |
| spell-control | 1-3-0 | 0.250 | -1.000 | 0.0515 | 0.059 | 0.120 |
| reactive-defense | 0-4-0 | 0.000 | -1.500 | 0.0914 | 0.056 | 0.213 |
| split-lane | 1-3-0 | 0.250 | -0.500 | 0.1814 | 0.056 | 0.120 |
| balanced | 0-4-0 | 0.000 | -1.000 | 0.0744 | 0.052 | 0.213 |

Mean score: **0.125**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
