# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_executed_strategy_hazard_seed1108001/policy_v2_update_000014.pt`

Protocol: 8 paired-seat games per opponent, seed 1109302, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 2-6-0 | 0.250 | -1.500 | 0.1160 | 0.071 | 0.133 |
| slow-push | 1-7-0 | 0.125 | -1.750 | 0.1279 | 0.070 | 0.181 |
| spell-control | 1-7-0 | 0.125 | -1.000 | 0.0842 | 0.071 | 0.181 |
| reactive-defense | 0-8-0 | 0.000 | -1.000 | 0.0815 | 0.071 | 0.236 |
| split-lane | 5-3-0 | 0.625 | +0.125 | 0.0731 | 0.069 | 0.033 |
| balanced | 0-8-0 | 0.000 | -1.375 | 0.0891 | 0.074 | 0.236 |

Mean score: **0.188**. Worst matchup: **reactive-defense** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
