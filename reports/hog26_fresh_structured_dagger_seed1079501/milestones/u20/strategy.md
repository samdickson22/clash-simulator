# Strategy benchmark: update 20

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_fresh_structured_dagger_seed1079501/train/policy_v2_update_000020.pt`

Protocol: 2 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -1.500 | 0.1315 | 0.129 | 0.167 |
| slow-push | 0-2-0 | 0.000 | -3.000 | 0.1593 | 0.094 | 0.167 |
| spell-control | 0-2-0 | 0.000 | -0.500 | 0.0583 | 0.144 | 0.167 |
| reactive-defense | 0-2-0 | 0.000 | -1.000 | 0.0915 | 0.114 | 0.167 |
| split-lane | 0-2-0 | 0.000 | -1.000 | 0.1716 | 0.124 | 0.167 |
| balanced | 0-2-0 | 0.000 | -1.000 | 0.0394 | 0.107 | 0.167 |

Mean score: **0.000**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
