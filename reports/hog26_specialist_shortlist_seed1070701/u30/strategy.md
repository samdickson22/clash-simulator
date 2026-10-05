# Strategy benchmark: update 30

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_specialist_seed1070301/policy_v2_update_000030.pt`

Protocol: 4 paired-seat games per opponent, seed 1070702, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.250 | 0.1342 | 0.054 | 0.208 |
| slow-push | 0-4-0 | 0.000 | -2.000 | 0.1478 | 0.054 | 0.208 |
| spell-control | 2-2-0 | 0.500 | -0.250 | 0.0725 | 0.051 | 0.052 |
| reactive-defense | 0-4-0 | 0.000 | -1.750 | 0.0795 | 0.058 | 0.208 |
| split-lane | 0-4-0 | 0.000 | -2.000 | 0.1457 | 0.051 | 0.208 |
| balanced | 1-3-0 | 0.250 | -1.000 | 0.0864 | 0.057 | 0.117 |

Mean score: **0.125**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
