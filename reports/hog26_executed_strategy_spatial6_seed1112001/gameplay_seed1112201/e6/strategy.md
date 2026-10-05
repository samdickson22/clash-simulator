# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_executed_strategy_spatial6_seed1112001/candidate.pt`

Protocol: 4 paired-seat games per opponent, seed 1112202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 2-2-0 | 0.500 | -0.500 | 0.1571 | 0.068 | 0.075 |
| slow-push | 0-4-0 | 0.000 | -2.000 | 0.1652 | 0.072 | 0.302 |
| spell-control | 2-2-0 | 0.500 | +0.000 | 0.0644 | 0.069 | 0.075 |
| reactive-defense | 1-3-0 | 0.250 | -1.250 | 0.0929 | 0.071 | 0.170 |
| split-lane | 2-2-0 | 0.500 | +0.250 | 0.0611 | 0.074 | 0.075 |
| balanced | 0-4-0 | 0.000 | -1.250 | 0.1011 | 0.072 | 0.302 |

Mean score: **0.292**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
