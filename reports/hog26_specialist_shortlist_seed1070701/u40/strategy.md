# Strategy benchmark: update 40

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_specialist_seed1070301/policy_v2_update_000040.pt`

Protocol: 4 paired-seat games per opponent, seed 1070702, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-3-0 | 0.250 | -1.250 | 0.1348 | 0.055 | 0.129 |
| slow-push | 0-4-0 | 0.000 | -2.000 | 0.1413 | 0.059 | 0.229 |
| spell-control | 1-3-0 | 0.250 | -0.750 | 0.0957 | 0.057 | 0.129 |
| reactive-defense | 0-4-0 | 0.000 | -1.750 | 0.0664 | 0.059 | 0.229 |
| split-lane | 2-2-0 | 0.500 | +0.250 | 0.1127 | 0.061 | 0.057 |
| balanced | 0-4-0 | 0.000 | -2.000 | 0.0973 | 0.058 | 0.229 |

Mean score: **0.167**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
