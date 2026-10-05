# Strategy benchmark: update 14

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_u46x2_reactive_slow_spatial_seed1154001/candidate.pt`

Protocol: 4 paired-seat games per opponent, seed 1155002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 1-3-0 | 0.250 | -1.000 | 0.1846 | 0.070 | 0.205 |
| slow-push | 1-3-0 | 0.250 | -0.750 | 0.1708 | 0.071 | 0.205 |
| spell-control | 2-2-0 | 0.500 | +0.000 | 0.0847 | 0.073 | 0.091 |
| reactive-defense | 1-3-0 | 0.250 | -0.500 | 0.0823 | 0.074 | 0.205 |
| split-lane | 2-2-0 | 0.500 | +0.250 | 0.1191 | 0.073 | 0.091 |
| balanced | 1-3-0 | 0.250 | -0.750 | 0.0710 | 0.070 | 0.205 |

Mean score: **0.333**. Worst matchup: **bridge-pressure** at **0.250**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
