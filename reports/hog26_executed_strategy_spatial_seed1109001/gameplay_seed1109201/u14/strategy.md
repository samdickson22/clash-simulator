# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_executed_strategy_hazard_seed1108001/policy_v2_update_000014.pt`

Protocol: 4 paired-seat games per opponent, seed 1109202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.750 | 0.1943 | 0.071 | 0.167 |
| slow-push | 0-4-0 | 0.000 | -2.000 | 0.1291 | 0.073 | 0.167 |
| spell-control | 0-4-0 | 0.000 | -2.000 | 0.1113 | 0.068 | 0.167 |
| reactive-defense | 0-4-0 | 0.000 | -1.250 | 0.0689 | 0.073 | 0.167 |
| split-lane | 0-4-0 | 0.000 | -2.250 | 0.1345 | 0.071 | 0.167 |
| balanced | 0-4-0 | 0.000 | -2.000 | 0.0775 | 0.070 | 0.167 |

Mean score: **0.000**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
