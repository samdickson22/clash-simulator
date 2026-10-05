# Strategy benchmark: update 30

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_f3_hazard_mixed_league_seed1068701/policy_v2_update_000030.pt`

Protocol: 4 paired-seat games per opponent, seed 1068901, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 2-2-0 | 0.500 | -0.500 | 0.0825 | 0.052 | 0.154 |
| slow-push | 2-2-0 | 0.500 | +0.000 | 0.0693 | 0.053 | 0.154 |
| spell-control | 2-2-0 | 0.500 | -0.250 | 0.0444 | 0.051 | 0.154 |
| reactive-defense | 3-1-0 | 0.750 | +0.500 | 0.0267 | 0.054 | 0.038 |
| split-lane | 2-2-0 | 0.500 | -0.500 | 0.0845 | 0.052 | 0.154 |
| balanced | 1-3-0 | 0.250 | -0.500 | 0.0676 | 0.057 | 0.346 |

Mean score: **0.500**. Worst matchup: **balanced** at **0.250**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
