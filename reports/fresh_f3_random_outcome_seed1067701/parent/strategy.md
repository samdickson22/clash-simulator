# Strategy benchmark: update 0

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_f3_outcome_lineage_seed1067501/control.pt`

Protocol: 6 paired-seat games per opponent, seed 1067801, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-5-0 | 0.167 | -2.167 | 0.1329 | 0.021 | 0.122 |
| slow-push | 0-6-0 | 0.000 | -3.000 | 0.1664 | 0.009 | 0.176 |
| spell-control | 0-6-0 | 0.000 | -2.500 | 0.1145 | 0.010 | 0.176 |
| reactive-defense | 0-6-0 | 0.000 | -2.333 | 0.1557 | 0.018 | 0.176 |
| split-lane | 0-6-0 | 0.000 | -2.667 | 0.1798 | 0.020 | 0.176 |
| balanced | 0-6-0 | 0.000 | -2.333 | 0.1149 | 0.041 | 0.176 |

Mean score: **0.028**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
