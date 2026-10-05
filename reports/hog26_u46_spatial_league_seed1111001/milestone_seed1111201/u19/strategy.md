# Strategy benchmark: update 19

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_u46_spatial_league_seed1111001/policy_v2_update_000019.pt`

Protocol: 2 paired-seat games per opponent, seed 1111202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -2.500 | 0.1888 | 0.067 | 0.267 |
| slow-push | 0-2-0 | 0.000 | -1.000 | 0.1501 | 0.071 | 0.267 |
| spell-control | 1-1-0 | 0.500 | -0.500 | 0.0590 | 0.072 | 0.067 |
| reactive-defense | 1-1-0 | 0.500 | +0.000 | 0.0477 | 0.067 | 0.067 |
| split-lane | 1-1-0 | 0.500 | +0.000 | 0.0597 | 0.066 | 0.067 |
| balanced | 0-2-0 | 0.000 | -1.000 | 0.0811 | 0.068 | 0.267 |

Mean score: **0.250**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
