# Strategy benchmark: update 56

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_strategy_pfsp_seed1071101/policy_v2_update_000056.pt`

Protocol: 2 paired-seat games per opponent, seed 1071202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -3.000 | 0.1249 | 0.051 | 0.190 |
| slow-push | 0-2-0 | 0.000 | -3.000 | 0.1672 | 0.056 | 0.190 |
| spell-control | 1-1-0 | 0.500 | -0.500 | 0.0474 | 0.059 | 0.048 |
| reactive-defense | 0-2-0 | 0.000 | -1.500 | 0.0974 | 0.054 | 0.190 |
| split-lane | 0-2-0 | 0.000 | -1.000 | 0.1129 | 0.063 | 0.190 |
| balanced | 0-2-0 | 0.000 | -2.000 | 0.1396 | 0.060 | 0.190 |

Mean score: **0.083**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
