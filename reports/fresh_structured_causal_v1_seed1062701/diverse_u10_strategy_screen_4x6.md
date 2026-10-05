# Strategy benchmark: update 10

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_structured_causal_v1_seed1062701/diverse_league_u20/policy_v2_update_000010.pt`

Protocol: 4 paired-seat games per opponent, seed 1063001, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 2-2-0 | 0.500 | -0.250 | 0.1246 | 0.070 | 0.117 |
| slow-push | 0-4-0 | 0.000 | -2.000 | 0.1675 | 0.077 | 0.466 |
| spell-control | 3-1-0 | 0.750 | +1.000 | 0.0430 | 0.081 | 0.029 |
| reactive-defense | 1-3-0 | 0.250 | -1.000 | 0.0578 | 0.073 | 0.262 |
| split-lane | 2-2-0 | 0.500 | +0.250 | 0.0617 | 0.057 | 0.117 |
| balanced | 4-0-0 | 1.000 | +1.250 | 0.0454 | 0.110 | 0.009 |

Mean score: **0.500**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
