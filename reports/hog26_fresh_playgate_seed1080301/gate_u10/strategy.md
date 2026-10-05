# Strategy benchmark: update 10

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_fresh_playgate_seed1080301/train/policy_v2_update_000010.pt`

Protocol: 2 paired-seat games per opponent, seed 1080402, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -3.000 | 0.1608 | 0.099 | 0.190 |
| slow-push | 0-2-0 | 0.000 | -2.000 | 0.2055 | 0.104 | 0.190 |
| spell-control | 0-2-0 | 0.000 | -1.000 | 0.1124 | 0.107 | 0.190 |
| reactive-defense | 1-1-0 | 0.500 | -0.500 | 0.0344 | 0.146 | 0.048 |
| split-lane | 0-2-0 | 0.000 | -1.000 | 0.0925 | 0.108 | 0.190 |
| balanced | 0-2-0 | 0.000 | -2.000 | 0.0811 | 0.102 | 0.190 |

Mean score: **0.083**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
