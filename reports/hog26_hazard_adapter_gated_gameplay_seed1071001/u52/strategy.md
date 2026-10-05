# Strategy benchmark: update 52

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_hazard_adapter_gated_seed1073601/policy_v2_update_000052.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -1.500 | 0.1085 | 0.110 | 0.276 |
| slow-push | 0-4-0 | 0.000 | -2.500 | 0.1577 | 0.093 | 0.276 |
| spell-control | 2-2-0 | 0.500 | +0.000 | 0.0518 | 0.111 | 0.069 |
| reactive-defense | 1-3-0 | 0.250 | -0.500 | 0.0888 | 0.110 | 0.155 |
| split-lane | 1-3-0 | 0.250 | -0.750 | 0.1355 | 0.098 | 0.155 |
| balanced | 2-2-0 | 0.500 | +0.250 | 0.0706 | 0.125 | 0.069 |

Mean score: **0.250**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
