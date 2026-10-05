# Strategy benchmark: update 10

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_clean8_aligned_seed1095001/calibrated/policy_v2_update_000010_threshold_0p2000.pt`

Protocol: 4 paired-seat games per opponent, seed 1108202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-3-0 | 0.250 | -1.500 | 0.1136 | 0.055 | 0.134 |
| slow-push | 0-4-0 | 0.000 | -2.500 | 0.1487 | 0.059 | 0.239 |
| spell-control | 1-3-0 | 0.250 | -0.750 | 0.0796 | 0.056 | 0.134 |
| reactive-defense | 0-4-0 | 0.000 | -2.000 | 0.0947 | 0.058 | 0.239 |
| split-lane | 3-1-0 | 0.750 | +0.250 | 0.0809 | 0.057 | 0.015 |
| balanced | 0-4-0 | 0.000 | -1.500 | 0.0741 | 0.058 | 0.239 |

Mean score: **0.208**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
