# Strategy benchmark: update 20

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_f1_legacy_replication_seed1067301/policy_v2_update_000020.pt`

Protocol: 6 paired-seat games per opponent, seed 1067401, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 2-4-0 | 0.333 | -0.667 | 0.1250 | 0.071 | 0.174 |
| slow-push | 1-5-0 | 0.167 | -1.667 | 0.1436 | 0.075 | 0.272 |
| spell-control | 5-1-0 | 0.833 | +0.333 | 0.0493 | 0.100 | 0.011 |
| reactive-defense | 1-5-0 | 0.167 | -1.167 | 0.0910 | 0.089 | 0.272 |
| split-lane | 3-3-0 | 0.500 | +0.667 | 0.0703 | 0.076 | 0.098 |
| balanced | 2-4-0 | 0.333 | -1.167 | 0.0639 | 0.085 | 0.174 |

Mean score: **0.389**. Worst matchup: **slow-push** at **0.167**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
