# Strategy benchmark: update 12

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_clean8_aligned_outcome_seed1096001/policy_v2_update_000012.pt`

Protocol: 2 paired-seat games per opponent, seed 1096202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -2.000 | 0.1482 | 0.056 | 0.167 |
| slow-push | 0-2-0 | 0.000 | -2.500 | 0.1218 | 0.054 | 0.167 |
| spell-control | 0-2-0 | 0.000 | -1.500 | 0.0766 | 0.052 | 0.167 |
| reactive-defense | 0-2-0 | 0.000 | -1.000 | 0.0654 | 0.058 | 0.167 |
| split-lane | 0-2-0 | 0.000 | -2.000 | 0.1412 | 0.058 | 0.167 |
| balanced | 0-2-0 | 0.000 | -2.000 | 0.1091 | 0.052 | 0.167 |

Mean score: **0.000**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
