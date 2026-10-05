# Strategy benchmark: update 40

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_specialist_seed1070301/policy_v2_update_000040.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -1.750 | 0.1437 | 0.058 | 0.180 |
| slow-push | 0-4-0 | 0.000 | -2.750 | 0.1675 | 0.049 | 0.180 |
| spell-control | 0-4-0 | 0.000 | -1.500 | 0.0636 | 0.057 | 0.180 |
| reactive-defense | 0-4-0 | 0.000 | -1.750 | 0.0978 | 0.062 | 0.180 |
| split-lane | 1-3-0 | 0.250 | -0.500 | 0.1772 | 0.057 | 0.101 |
| balanced | 0-4-0 | 0.000 | -1.250 | 0.0783 | 0.063 | 0.180 |

Mean score: **0.042**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
