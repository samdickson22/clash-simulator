# Strategy benchmark: update 66

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_strategy_majority_seed1075001/policy_v2_update_000066.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -1.750 | 0.1396 | 0.060 | 0.195 |
| slow-push | 0-4-0 | 0.000 | -2.500 | 0.1701 | 0.050 | 0.195 |
| spell-control | 1-3-0 | 0.250 | -0.750 | 0.0564 | 0.066 | 0.110 |
| reactive-defense | 0-4-0 | 0.000 | -1.500 | 0.0902 | 0.060 | 0.195 |
| split-lane | 1-3-0 | 0.250 | -0.750 | 0.1552 | 0.060 | 0.110 |
| balanced | 0-4-0 | 0.000 | -1.000 | 0.0781 | 0.058 | 0.195 |

Mean score: **0.083**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
