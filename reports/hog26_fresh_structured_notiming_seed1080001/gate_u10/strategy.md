# Strategy benchmark: update 10

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_fresh_structured_notiming_seed1080001/train/policy_v2_update_000010.pt`

Protocol: 2 paired-seat games per opponent, seed 1080102, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -2.500 | 0.1644 | 0.042 | 0.190 |
| slow-push | 0-2-0 | 0.000 | -2.000 | 0.1263 | 0.043 | 0.190 |
| spell-control | 0-2-0 | 0.000 | -2.000 | 0.1447 | 0.041 | 0.190 |
| reactive-defense | 1-1-0 | 0.500 | +0.000 | 0.0384 | 0.044 | 0.048 |
| split-lane | 0-2-0 | 0.000 | -2.000 | 0.1759 | 0.043 | 0.190 |
| balanced | 0-2-0 | 0.000 | -1.500 | 0.1134 | 0.046 | 0.190 |

Mean score: **0.083**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
