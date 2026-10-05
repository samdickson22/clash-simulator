# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_executed_strategy_hazard_seed1108001/policy_v2_update_000014.pt`

Protocol: 4 paired-seat games per opponent, seed 1108202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-3-0 | 0.250 | -1.500 | 0.1077 | 0.070 | 0.129 |
| slow-push | 1-3-0 | 0.250 | -1.500 | 0.1100 | 0.072 | 0.129 |
| spell-control | 0-4-0 | 0.000 | -1.000 | 0.0582 | 0.072 | 0.229 |
| reactive-defense | 0-4-0 | 0.000 | -1.000 | 0.0687 | 0.073 | 0.229 |
| split-lane | 2-2-0 | 0.500 | -0.500 | 0.0943 | 0.069 | 0.057 |
| balanced | 0-4-0 | 0.000 | -1.750 | 0.0597 | 0.070 | 0.229 |

Mean score: **0.167**. Worst matchup: **spell-control** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
