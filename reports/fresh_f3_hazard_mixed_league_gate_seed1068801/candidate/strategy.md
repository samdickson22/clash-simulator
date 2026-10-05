# Strategy benchmark: update 30

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_f3_hazard_mixed_league_seed1068701/policy_v2_update_000030.pt`

Protocol: 6 paired-seat games per opponent, seed 1068601, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-5-0 | 0.167 | -1.167 | 0.1152 | 0.054 | 0.170 |
| slow-push | 0-6-0 | 0.000 | -2.333 | 0.1322 | 0.051 | 0.245 |
| spell-control | 0-6-0 | 0.000 | -1.500 | 0.0697 | 0.064 | 0.245 |
| reactive-defense | 1-5-0 | 0.167 | -1.000 | 0.0839 | 0.054 | 0.170 |
| split-lane | 3-3-0 | 0.500 | +0.333 | 0.0695 | 0.053 | 0.061 |
| balanced | 2-4-0 | 0.333 | -1.000 | 0.0723 | 0.051 | 0.109 |

Mean score: **0.194**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
