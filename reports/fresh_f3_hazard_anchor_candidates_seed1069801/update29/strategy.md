# Strategy benchmark: update 29

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_f3_hazard_mixed_league_seed1068701/policy_v2_update_000029.pt`

Protocol: 4 paired-seat games per opponent, seed 1069801, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.000 | 0.1424 | 0.051 | 0.333 |
| slow-push | 1-3-0 | 0.250 | -1.250 | 0.1110 | 0.045 | 0.188 |
| spell-control | 1-3-0 | 0.250 | -1.000 | 0.0818 | 0.053 | 0.188 |
| reactive-defense | 2-2-0 | 0.500 | -0.750 | 0.0605 | 0.058 | 0.083 |
| split-lane | 3-1-0 | 0.750 | +1.250 | 0.0873 | 0.046 | 0.021 |
| balanced | 1-3-0 | 0.250 | -0.250 | 0.0845 | 0.050 | 0.188 |

Mean score: **0.333**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
