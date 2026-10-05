# Strategy benchmark: update 30

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_f3_hazard_mixed_league_seed1068701/policy_v2_update_000030.pt`

Protocol: 4 paired-seat games per opponent, seed 1069801, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-3-0 | 0.250 | -1.250 | 0.1433 | 0.058 | 0.188 |
| slow-push | 0-4-0 | 0.000 | -1.500 | 0.1111 | 0.051 | 0.333 |
| spell-control | 1-3-0 | 0.250 | -0.750 | 0.0862 | 0.057 | 0.188 |
| reactive-defense | 2-2-0 | 0.500 | -0.500 | 0.0617 | 0.067 | 0.083 |
| split-lane | 3-1-0 | 0.750 | +0.000 | 0.0758 | 0.054 | 0.021 |
| balanced | 1-3-0 | 0.250 | -0.500 | 0.0788 | 0.054 | 0.188 |

Mean score: **0.333**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
