# Strategy benchmark: update 20

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_f3_random_outcome_seed1067701/policy_v2_update_000020.pt`

Protocol: 6 paired-seat games per opponent, seed 1067801, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-5-0 | 0.167 | -1.500 | 0.1090 | 0.073 | 0.198 |
| slow-push | 0-6-0 | 0.000 | -2.167 | 0.1120 | 0.072 | 0.286 |
| spell-control | 2-4-0 | 0.333 | +0.000 | 0.0522 | 0.105 | 0.127 |
| reactive-defense | 3-3-0 | 0.500 | -0.333 | 0.0601 | 0.079 | 0.071 |
| split-lane | 4-2-0 | 0.667 | -0.167 | 0.1086 | 0.085 | 0.032 |
| balanced | 0-6-0 | 0.000 | -0.833 | 0.0596 | 0.093 | 0.286 |

Mean score: **0.278**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
