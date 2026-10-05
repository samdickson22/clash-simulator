# Strategy benchmark: update 50

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_strategy_pfsp_seed1071101/policy_v2_update_000050.pt`

Protocol: 2 paired-seat games per opponent, seed 1071202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -2.500 | 0.1174 | 0.057 | 0.234 |
| slow-push | 0-2-0 | 0.000 | -3.000 | 0.1633 | 0.055 | 0.234 |
| spell-control | 2-0-0 | 1.000 | +0.500 | 0.0361 | 0.059 | 0.005 |
| reactive-defense | 0-2-0 | 0.000 | -1.000 | 0.1315 | 0.057 | 0.234 |
| split-lane | 1-1-0 | 0.500 | +0.000 | 0.0931 | 0.059 | 0.059 |
| balanced | 0-2-0 | 0.000 | -2.500 | 0.1329 | 0.062 | 0.234 |

Mean score: **0.250**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
