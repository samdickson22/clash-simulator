# Strategy benchmark: update 0

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_clean8_terminal_hazard_scaled_seed1106001/gain_16.pt`

Protocol: 4 paired-seat games per opponent, seed 1106302, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -1.250 | 0.1321 | 0.061 | 0.216 |
| slow-push | 0-4-0 | 0.000 | -2.750 | 0.2034 | 0.057 | 0.216 |
| spell-control | 1-3-0 | 0.250 | -1.250 | 0.0769 | 0.056 | 0.122 |
| reactive-defense | 0-4-0 | 0.000 | -1.750 | 0.1089 | 0.058 | 0.216 |
| split-lane | 3-1-0 | 0.750 | +0.500 | 0.0861 | 0.059 | 0.014 |
| balanced | 0-4-0 | 0.000 | -1.250 | 0.0980 | 0.060 | 0.216 |

Mean score: **0.167**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
