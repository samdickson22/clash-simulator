# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_executed_strategy_spatial_seed1109001/candidate.pt`

Protocol: 4 paired-seat games per opponent, seed 1124202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.000 | 0.1304 | 0.069 | 0.261 |
| slow-push | 0-4-0 | 0.000 | -2.250 | 0.1337 | 0.073 | 0.261 |
| spell-control | 1-3-0 | 0.250 | -0.750 | 0.0776 | 0.072 | 0.147 |
| reactive-defense | 0-4-0 | 0.000 | -1.500 | 0.0783 | 0.074 | 0.261 |
| split-lane | 4-0-0 | 1.000 | +1.250 | 0.0447 | 0.074 | 0.005 |
| balanced | 2-2-0 | 0.500 | -0.250 | 0.0615 | 0.069 | 0.065 |

Mean score: **0.292**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
