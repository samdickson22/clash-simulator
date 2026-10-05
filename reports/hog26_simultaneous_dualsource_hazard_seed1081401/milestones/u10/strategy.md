# Strategy benchmark: update 10

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_simultaneous_dualsource_hazard_seed1081401/train/policy_v2_update_000010.pt`

Protocol: 2 paired-seat games per opponent, seed 1081602, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -3.000 | 0.1931 | 0.018 | 0.167 |
| slow-push | 0-2-0 | 0.000 | -3.000 | 0.2130 | 0.011 | 0.167 |
| spell-control | 0-2-0 | 0.000 | -2.000 | 0.1187 | 0.013 | 0.167 |
| reactive-defense | 0-2-0 | 0.000 | -3.000 | 0.0813 | 0.012 | 0.167 |
| split-lane | 0-2-0 | 0.000 | -2.000 | 0.0975 | 0.019 | 0.167 |
| balanced | 0-2-0 | 0.000 | -3.000 | 0.1364 | 0.013 | 0.167 |

Mean score: **0.000**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
