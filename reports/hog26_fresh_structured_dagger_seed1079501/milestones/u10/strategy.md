# Strategy benchmark: update 10

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_fresh_structured_dagger_seed1079501/train/policy_v2_update_000010.pt`

Protocol: 2 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -2.000 | 0.1168 | 0.085 | 0.167 |
| slow-push | 0-2-0 | 0.000 | -3.000 | 0.1606 | 0.084 | 0.167 |
| spell-control | 0-2-0 | 0.000 | -1.000 | 0.0374 | 0.077 | 0.167 |
| reactive-defense | 0-2-0 | 0.000 | -1.500 | 0.0823 | 0.085 | 0.167 |
| split-lane | 0-2-0 | 0.000 | -1.500 | 0.1571 | 0.087 | 0.167 |
| balanced | 0-2-0 | 0.000 | -1.000 | 0.0373 | 0.089 | 0.167 |

Mean score: **0.000**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
