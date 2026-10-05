# Strategy benchmark: update 0

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/tv_royale_youtube_causal_seed1067001/oracle_gate_f1_clock1500.pt`

Protocol: 6 paired-seat games per opponent, seed 1067201, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 2-4-0 | 0.333 | -0.667 | 0.0862 | 0.074 | 0.186 |
| slow-push | 1-5-0 | 0.167 | -1.333 | 0.1373 | 0.068 | 0.291 |
| spell-control | 4-2-0 | 0.667 | +0.667 | 0.0577 | 0.073 | 0.047 |
| reactive-defense | 2-4-0 | 0.333 | -0.167 | 0.0464 | 0.100 | 0.186 |
| split-lane | 3-3-0 | 0.500 | +0.000 | 0.0803 | 0.082 | 0.105 |
| balanced | 2-4-0 | 0.333 | -1.000 | 0.0847 | 0.058 | 0.186 |

Mean score: **0.389**. Worst matchup: **slow-push** at **0.167**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
