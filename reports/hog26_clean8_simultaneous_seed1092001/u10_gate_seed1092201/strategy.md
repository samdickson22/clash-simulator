# Strategy benchmark: update 10

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_clean8_simultaneous_seed1092001/train/policy_v2_update_000010.pt`

Protocol: 2 paired-seat games per opponent, seed 1092202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -2.500 | 0.1637 | 0.016 | 0.167 |
| slow-push | 0-2-0 | 0.000 | -3.000 | 0.1590 | 0.020 | 0.167 |
| spell-control | 0-2-0 | 0.000 | -3.000 | 0.1305 | 0.015 | 0.167 |
| reactive-defense | 0-2-0 | 0.000 | -1.500 | 0.1373 | 0.015 | 0.167 |
| split-lane | 0-2-0 | 0.000 | -2.000 | 0.1480 | 0.017 | 0.167 |
| balanced | 0-2-0 | 0.000 | -3.000 | 0.1265 | 0.018 | 0.167 |

Mean score: **0.000**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
