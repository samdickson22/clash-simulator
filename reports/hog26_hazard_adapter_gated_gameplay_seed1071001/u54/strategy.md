# Strategy benchmark: update 54

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_hazard_adapter_gated_seed1073601/policy_v2_update_000054.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -1.250 | 0.1062 | 0.110 | 0.195 |
| slow-push | 0-4-0 | 0.000 | -2.500 | 0.1578 | 0.094 | 0.195 |
| spell-control | 1-3-0 | 0.250 | -0.500 | 0.0580 | 0.107 | 0.110 |
| reactive-defense | 0-4-0 | 0.000 | -0.750 | 0.0981 | 0.107 | 0.195 |
| split-lane | 1-3-0 | 0.250 | -0.500 | 0.1359 | 0.099 | 0.110 |
| balanced | 0-4-0 | 0.000 | -0.750 | 0.0756 | 0.114 | 0.195 |

Mean score: **0.083**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
