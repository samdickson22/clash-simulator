# Strategy benchmark: update 24

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_f3_hazard_mixed_league_seed1068701/policy_v2_update_000024.pt`

Protocol: 4 paired-seat games per opponent, seed 1069801, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-3-0 | 0.250 | -1.500 | 0.1408 | 0.050 | 0.205 |
| slow-push | 1-3-0 | 0.250 | -1.000 | 0.1204 | 0.046 | 0.205 |
| spell-control | 1-3-0 | 0.250 | -1.250 | 0.0899 | 0.047 | 0.205 |
| reactive-defense | 2-2-0 | 0.500 | -0.750 | 0.0635 | 0.053 | 0.091 |
| split-lane | 2-2-0 | 0.500 | +0.000 | 0.0958 | 0.040 | 0.091 |
| balanced | 1-3-0 | 0.250 | +0.000 | 0.0807 | 0.046 | 0.205 |

Mean score: **0.333**. Worst matchup: **bridge-pressure** at **0.250**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
