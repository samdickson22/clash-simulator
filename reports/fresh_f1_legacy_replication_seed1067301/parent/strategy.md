# Strategy benchmark: update 0

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/tv_royale_youtube_causal_seed1067001/oracle_gate_f1_clock1500.pt`

Protocol: 6 paired-seat games per opponent, seed 1067401, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 2-4-0 | 0.333 | -0.667 | 0.1290 | 0.065 | 0.216 |
| slow-push | 2-4-0 | 0.333 | -1.500 | 0.1093 | 0.081 | 0.216 |
| spell-control | 4-2-0 | 0.667 | -0.167 | 0.0479 | 0.081 | 0.054 |
| reactive-defense | 1-5-0 | 0.167 | -1.000 | 0.1048 | 0.097 | 0.338 |
| split-lane | 4-2-0 | 0.667 | +0.667 | 0.0767 | 0.082 | 0.054 |
| balanced | 3-3-0 | 0.500 | -1.000 | 0.0702 | 0.083 | 0.122 |

Mean score: **0.444**. Worst matchup: **reactive-defense** at **0.167**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
