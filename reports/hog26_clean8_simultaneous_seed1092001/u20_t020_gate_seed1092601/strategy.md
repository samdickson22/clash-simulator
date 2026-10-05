# Strategy benchmark: update 20

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_clean8_simultaneous_seed1092001/threshold_sweep/policy_v2_update_000020_threshold_0p2000.pt`

Protocol: 2 paired-seat games per opponent, seed 1092602, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -2.500 | 0.2414 | 0.055 | 0.167 |
| slow-push | 0-2-0 | 0.000 | -3.000 | 0.2187 | 0.055 | 0.167 |
| spell-control | 0-2-0 | 0.000 | -2.000 | 0.1929 | 0.054 | 0.167 |
| reactive-defense | 0-2-0 | 0.000 | -2.000 | 0.0818 | 0.054 | 0.167 |
| split-lane | 0-2-0 | 0.000 | -2.500 | 0.2277 | 0.054 | 0.167 |
| balanced | 0-2-0 | 0.000 | -2.500 | 0.1161 | 0.056 | 0.167 |

Mean score: **0.000**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
