# Strategy benchmark: update 20

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/mechanics_slot_probe/accepted6m_zero_seed1056701/zero_adapter.pt`

Protocol: 6 paired-seat games per opponent, seed 1056201, reward profile `defense-v2`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 4-2-0 | 0.667 | +0.667 | 0.1572 | 0.044 | 0.226 |
| slow-push | 4-2-0 | 0.667 | +1.000 | 0.1118 | 0.064 | 0.226 |
| spell-control | 4-2-0 | 0.667 | +1.000 | 0.0512 | 0.062 | 0.226 |
| reactive-defense | 5-1-0 | 0.833 | +1.000 | 0.0375 | 0.073 | 0.056 |
| split-lane | 6-0-0 | 1.000 | +2.500 | 0.0605 | 0.052 | 0.041 |
| balanced | 4-2-0 | 0.667 | +1.167 | 0.0426 | 0.053 | 0.226 |

Mean score: **0.750**. Worst matchup: **bridge-pressure** at **0.667**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
