# Strategy benchmark: update 20

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_structured_causal_v1_seed1062701/diverse_league_u20/policy_v2_update_000020.pt`

Protocol: 4 paired-seat games per opponent, seed 1063001, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-3-0 | 0.250 | -0.250 | 0.1322 | 0.069 | 0.231 |
| slow-push | 1-3-0 | 0.250 | -1.000 | 0.1356 | 0.099 | 0.231 |
| spell-control | 2-2-0 | 0.500 | +0.750 | 0.0535 | 0.094 | 0.103 |
| reactive-defense | 1-3-0 | 0.250 | -0.750 | 0.0653 | 0.078 | 0.231 |
| split-lane | 2-2-0 | 0.500 | +0.500 | 0.0611 | 0.055 | 0.103 |
| balanced | 2-2-0 | 0.500 | +0.000 | 0.0571 | 0.093 | 0.103 |

Mean score: **0.375**. Worst matchup: **bridge-pressure** at **0.250**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
