# Strategy benchmark: update 23

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_f3_hazard_mixed_league_seed1068701/policy_v2_update_000023.pt`

Protocol: 4 paired-seat games per opponent, seed 1070002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-3-0 | 0.250 | -1.000 | 0.1502 | 0.050 | 0.164 |
| slow-push | 0-4-0 | 0.000 | -2.500 | 0.1865 | 0.045 | 0.291 |
| spell-control | 0-4-0 | 0.000 | -1.750 | 0.0931 | 0.049 | 0.291 |
| reactive-defense | 1-3-0 | 0.250 | -1.000 | 0.0695 | 0.050 | 0.164 |
| split-lane | 3-1-0 | 0.750 | +1.250 | 0.0554 | 0.055 | 0.018 |
| balanced | 2-2-0 | 0.500 | +0.500 | 0.0901 | 0.047 | 0.073 |

Mean score: **0.292**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
