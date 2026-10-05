# Strategy benchmark: update 40

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_specialist_seed1070301/policy_v2_update_000040.pt`

Protocol: 4 paired-seat games per opponent, seed 1070502, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -1.750 | 0.1358 | 0.059 | 0.239 |
| slow-push | 0-4-0 | 0.000 | -1.750 | 0.1695 | 0.060 | 0.239 |
| spell-control | 3-1-0 | 0.750 | +0.750 | 0.0491 | 0.059 | 0.015 |
| reactive-defense | 0-4-0 | 0.000 | -2.000 | 0.1195 | 0.058 | 0.239 |
| split-lane | 1-3-0 | 0.250 | -0.500 | 0.1169 | 0.057 | 0.134 |
| balanced | 1-3-0 | 0.250 | -0.750 | 0.0971 | 0.060 | 0.134 |

Mean score: **0.208**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
