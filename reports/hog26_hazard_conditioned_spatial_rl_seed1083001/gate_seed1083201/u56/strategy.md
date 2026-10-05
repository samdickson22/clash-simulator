# Strategy benchmark: update 56

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_hazard_conditioned_spatial_rl_seed1083001/policy_v2_update_000056.pt`

Protocol: 2 paired-seat games per opponent, seed 1083202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -3.000 | 0.1757 | 0.058 | 0.222 |
| slow-push | 0-2-0 | 0.000 | -2.500 | 0.1758 | 0.056 | 0.222 |
| spell-control | 1-1-0 | 0.500 | +0.000 | 0.0581 | 0.063 | 0.056 |
| reactive-defense | 0-2-0 | 0.000 | -2.500 | 0.1078 | 0.057 | 0.222 |
| split-lane | 1-1-0 | 0.500 | -0.500 | 0.1225 | 0.055 | 0.056 |
| balanced | 0-2-0 | 0.000 | -3.000 | 0.1537 | 0.054 | 0.222 |

Mean score: **0.167**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
