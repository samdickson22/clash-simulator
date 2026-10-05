# Strategy benchmark: update 52

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_strategy_pfsp_seed1071101/policy_v2_update_000052.pt`

Protocol: 2 paired-seat games per opponent, seed 1071202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -2.500 | 0.1204 | 0.055 | 0.199 |
| slow-push | 0-2-0 | 0.000 | -2.500 | 0.1847 | 0.056 | 0.199 |
| spell-control | 2-0-0 | 1.000 | +0.500 | 0.0325 | 0.059 | 0.004 |
| reactive-defense | 0-2-0 | 0.000 | -2.500 | 0.1465 | 0.059 | 0.199 |
| split-lane | 0-2-0 | 0.000 | -1.000 | 0.1235 | 0.058 | 0.199 |
| balanced | 0-2-0 | 0.000 | -2.000 | 0.1214 | 0.058 | 0.199 |

Mean score: **0.167**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
