# Strategy benchmark: update 20

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_fresh_structured_dagger_seed1079501/hazard_compositions/u20_body_u15_hazard.pt`

Protocol: 2 paired-seat games per opponent, seed 1079802, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -2.500 | 0.1213 | 0.098 | 0.190 |
| slow-push | 0-2-0 | 0.000 | -1.500 | 0.1010 | 0.107 | 0.190 |
| spell-control | 0-2-0 | 0.000 | -0.500 | 0.0961 | 0.135 | 0.190 |
| reactive-defense | 0-2-0 | 0.000 | -1.000 | 0.0498 | 0.106 | 0.190 |
| split-lane | 0-2-0 | 0.000 | -1.000 | 0.1462 | 0.124 | 0.190 |
| balanced | 1-1-0 | 0.500 | -0.500 | 0.0630 | 0.154 | 0.048 |

Mean score: **0.083**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
