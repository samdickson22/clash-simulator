# Strategy benchmark: update 23

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_f3_hazard_mixed_league_seed1068701/policy_v2_update_000023.pt`

Protocol: 4 paired-seat games per opponent, seed 1069801, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -1.750 | 0.1373 | 0.049 | 0.302 |
| slow-push | 0-4-0 | 0.000 | -2.000 | 0.1327 | 0.043 | 0.302 |
| spell-control | 2-2-0 | 0.500 | -0.500 | 0.0777 | 0.047 | 0.075 |
| reactive-defense | 2-2-0 | 0.500 | -0.500 | 0.0514 | 0.058 | 0.075 |
| split-lane | 2-2-0 | 0.500 | -0.500 | 0.0976 | 0.042 | 0.075 |
| balanced | 1-3-0 | 0.250 | +0.000 | 0.0808 | 0.045 | 0.170 |

Mean score: **0.292**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
