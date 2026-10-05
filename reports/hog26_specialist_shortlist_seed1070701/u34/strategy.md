# Strategy benchmark: update 34

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_specialist_seed1070301/policy_v2_update_000034.pt`

Protocol: 4 paired-seat games per opponent, seed 1070702, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -3.000 | 0.1511 | 0.055 | 0.213 |
| slow-push | 0-4-0 | 0.000 | -2.250 | 0.1475 | 0.054 | 0.213 |
| spell-control | 1-3-0 | 0.250 | -1.000 | 0.1020 | 0.056 | 0.120 |
| reactive-defense | 1-3-0 | 0.250 | -1.000 | 0.0618 | 0.059 | 0.120 |
| split-lane | 1-3-0 | 0.250 | -0.500 | 0.1303 | 0.058 | 0.120 |
| balanced | 0-4-0 | 0.000 | -1.750 | 0.0868 | 0.060 | 0.213 |

Mean score: **0.125**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
