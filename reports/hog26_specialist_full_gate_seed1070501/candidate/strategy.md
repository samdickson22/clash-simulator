# Strategy benchmark: update 36

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_specialist_seed1070301/policy_v2_update_000036.pt`

Protocol: 4 paired-seat games per opponent, seed 1070502, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.250 | 0.1391 | 0.055 | 0.258 |
| slow-push | 0-4-0 | 0.000 | -2.000 | 0.1609 | 0.057 | 0.258 |
| spell-control | 3-1-0 | 0.750 | +0.500 | 0.0554 | 0.058 | 0.016 |
| reactive-defense | 0-4-0 | 0.000 | -1.750 | 0.1058 | 0.058 | 0.258 |
| split-lane | 2-2-0 | 0.500 | +0.000 | 0.1120 | 0.054 | 0.065 |
| balanced | 1-3-0 | 0.250 | -1.000 | 0.1076 | 0.057 | 0.145 |

Mean score: **0.250**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
