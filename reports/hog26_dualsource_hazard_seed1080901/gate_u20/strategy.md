# Strategy benchmark: update 20

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_dualsource_hazard_seed1080901/train/policy_v2_update_000020.pt`

Protocol: 2 paired-seat games per opponent, seed 1081102, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -3.000 | 0.1309 | 0.017 | 0.167 |
| slow-push | 0-2-0 | 0.000 | -3.000 | 0.2414 | 0.018 | 0.167 |
| spell-control | 0-2-0 | 0.000 | -3.000 | 0.0777 | 0.014 | 0.167 |
| reactive-defense | 0-2-0 | 0.000 | -3.000 | 0.1627 | 0.023 | 0.167 |
| split-lane | 0-2-0 | 0.000 | -3.000 | 0.1162 | 0.021 | 0.167 |
| balanced | 0-2-0 | 0.000 | -3.000 | 0.1700 | 0.017 | 0.167 |

Mean score: **0.000**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
