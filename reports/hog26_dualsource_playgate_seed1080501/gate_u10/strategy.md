# Strategy benchmark: update 10

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_dualsource_playgate_seed1080501/train/policy_v2_update_000010.pt`

Protocol: 2 paired-seat games per opponent, seed 1080602, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -0.500 | 0.1007 | 0.131 | 0.267 |
| slow-push | 1-1-0 | 0.500 | -0.500 | 0.0776 | 0.136 | 0.067 |
| spell-control | 0-2-0 | 0.000 | -1.500 | 0.0568 | 0.115 | 0.267 |
| reactive-defense | 1-1-0 | 0.500 | +0.000 | 0.0185 | 0.162 | 0.067 |
| split-lane | 1-1-0 | 0.500 | -0.500 | 0.0372 | 0.119 | 0.067 |
| balanced | 0-2-0 | 0.000 | -1.500 | 0.0720 | 0.118 | 0.267 |

Mean score: **0.250**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
