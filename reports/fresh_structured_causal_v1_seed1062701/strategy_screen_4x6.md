# Strategy benchmark: update 0

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/fresh_structured_causal_v1_seed1062701/structured_e3.pt`

Protocol: 4 paired-seat games per opponent, seed 1063001, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 3-1-0 | 0.750 | +1.000 | 0.1135 | 0.066 | 0.031 |
| slow-push | 0-4-0 | 0.000 | -2.000 | 0.1889 | 0.071 | 0.500 |
| spell-control | 3-1-0 | 0.750 | +1.000 | 0.0484 | 0.081 | 0.031 |
| reactive-defense | 1-3-0 | 0.250 | -1.500 | 0.0784 | 0.041 | 0.281 |
| split-lane | 2-2-0 | 0.500 | +0.250 | 0.0599 | 0.060 | 0.125 |
| balanced | 3-1-0 | 0.750 | +0.000 | 0.0713 | 0.075 | 0.031 |

Mean score: **0.500**. Worst matchup: **slow-push** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
