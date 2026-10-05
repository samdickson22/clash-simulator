# Strategy benchmark: update 10

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_clean8_aligned_seed1095001/calibrated/policy_v2_update_000010_threshold_0p2000.pt`

Protocol: 4 paired-seat games per opponent, seed 1106302, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-3-0 | 0.250 | -0.750 | 0.1247 | 0.059 | 0.145 |
| slow-push | 0-4-0 | 0.000 | -2.500 | 0.1754 | 0.055 | 0.258 |
| spell-control | 2-2-0 | 0.500 | -0.500 | 0.0725 | 0.055 | 0.065 |
| reactive-defense | 0-4-0 | 0.000 | -1.750 | 0.1039 | 0.053 | 0.258 |
| split-lane | 3-1-0 | 0.750 | +0.500 | 0.0815 | 0.055 | 0.016 |
| balanced | 0-4-0 | 0.000 | -1.000 | 0.0917 | 0.055 | 0.258 |

Mean score: **0.250**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
