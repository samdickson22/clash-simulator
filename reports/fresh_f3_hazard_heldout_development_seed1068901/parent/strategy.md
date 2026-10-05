# Strategy benchmark: update 20

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_f3_hazard_fullweight_outcome_seed1068401/policy_v2_update_000020.pt`

Protocol: 4 paired-seat games per opponent, seed 1068901, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 2-2-0 | 0.500 | +0.000 | 0.0775 | 0.050 | 0.087 |
| slow-push | 1-3-0 | 0.250 | -1.250 | 0.0770 | 0.050 | 0.196 |
| spell-control | 0-4-0 | 0.000 | -1.000 | 0.0500 | 0.046 | 0.348 |
| reactive-defense | 2-2-0 | 0.500 | +0.000 | 0.0357 | 0.050 | 0.087 |
| split-lane | 2-2-0 | 0.500 | +0.000 | 0.0775 | 0.047 | 0.087 |
| balanced | 1-3-0 | 0.250 | -0.750 | 0.0734 | 0.049 | 0.196 |

Mean score: **0.333**. Worst matchup: **spell-control** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
