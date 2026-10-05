# Strategy benchmark: update 20

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_fresh_structured_dagger_seed1079501/hazard_compositions/u20_body_u10_hazard.pt`

Protocol: 2 paired-seat games per opponent, seed 1079802, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -2.500 | 0.1280 | 0.087 | 0.190 |
| slow-push | 0-2-0 | 0.000 | -1.500 | 0.0853 | 0.093 | 0.190 |
| spell-control | 1-1-0 | 0.500 | -0.500 | 0.0710 | 0.092 | 0.048 |
| reactive-defense | 0-2-0 | 0.000 | -1.000 | 0.0476 | 0.088 | 0.190 |
| split-lane | 0-2-0 | 0.000 | -2.000 | 0.1447 | 0.089 | 0.190 |
| balanced | 0-2-0 | 0.000 | -0.500 | 0.0555 | 0.094 | 0.190 |

Mean score: **0.083**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
