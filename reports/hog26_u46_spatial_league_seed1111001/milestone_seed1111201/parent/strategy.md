# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_executed_strategy_spatial_seed1109001/candidate.pt`

Protocol: 2 paired-seat games per opponent, seed 1111202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -3.000 | 0.1568 | 0.069 | 0.361 |
| slow-push | 1-1-0 | 0.500 | +0.000 | 0.1180 | 0.075 | 0.090 |
| spell-control | 1-1-0 | 0.500 | -0.500 | 0.0597 | 0.074 | 0.090 |
| reactive-defense | 2-0-0 | 1.000 | +1.000 | 0.0262 | 0.065 | 0.007 |
| split-lane | 1-1-0 | 0.500 | -0.500 | 0.0810 | 0.067 | 0.090 |
| balanced | 0-2-0 | 0.000 | -1.000 | 0.0801 | 0.070 | 0.361 |

Mean score: **0.417**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
