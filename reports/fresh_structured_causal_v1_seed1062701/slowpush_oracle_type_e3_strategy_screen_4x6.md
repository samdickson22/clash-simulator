# Strategy benchmark: update 0

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_structured_causal_v1_seed1062701/slowpush_oracle_type_seed1063206/type_e3.pt`

Protocol: 4 paired-seat games per opponent, seed 1063001, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 2-2-0 | 0.500 | -0.250 | 0.1327 | 0.070 | 0.146 |
| slow-push | 1-3-0 | 0.250 | -0.750 | 0.1650 | 0.077 | 0.329 |
| spell-control | 4-0-0 | 1.000 | +2.000 | 0.0316 | 0.123 | 0.012 |
| reactive-defense | 1-3-0 | 0.250 | -1.000 | 0.0577 | 0.069 | 0.329 |
| split-lane | 2-2-0 | 0.500 | +0.250 | 0.0559 | 0.063 | 0.146 |
| balanced | 3-1-0 | 0.750 | +0.500 | 0.0489 | 0.087 | 0.037 |

Mean score: **0.542**. Worst matchup: **slow-push** at **0.250**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
