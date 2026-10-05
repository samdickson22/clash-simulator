# Strategy benchmark: update 0

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_structured_causal_v1_seed1062701/lstm_causal_frame_e3.pt`

Protocol: 4 paired-seat games per opponent, seed 1063001, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.000 | 0.1185 | 0.089 | 0.190 |
| slow-push | 0-4-0 | 0.000 | -2.750 | 0.2363 | 0.002 | 0.190 |
| spell-control | 0-4-0 | 0.000 | -2.500 | 0.1414 | 0.002 | 0.190 |
| reactive-defense | 0-4-0 | 0.000 | -3.000 | 0.1687 | 0.001 | 0.190 |
| split-lane | 2-2-0 | 0.500 | -0.500 | 0.0778 | 0.016 | 0.048 |
| balanced | 0-4-0 | 0.000 | -3.000 | 0.1221 | 0.001 | 0.190 |

Mean score: **0.083**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
