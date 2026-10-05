# Strategy benchmark: update 18

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_clean8_aligned_outcome_seed1096001/policy_v2_update_000018.pt`

Protocol: 2 paired-seat games per opponent, seed 1096202, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -2.500 | 0.1572 | 0.057 | 0.190 |
| slow-push | 0-2-0 | 0.000 | -2.000 | 0.1313 | 0.059 | 0.190 |
| spell-control | 0-2-0 | 0.000 | -1.500 | 0.0823 | 0.053 | 0.190 |
| reactive-defense | 1-1-0 | 0.500 | -0.500 | 0.0576 | 0.053 | 0.048 |
| split-lane | 0-2-0 | 0.000 | -1.500 | 0.0985 | 0.054 | 0.190 |
| balanced | 0-2-0 | 0.000 | -2.000 | 0.0907 | 0.061 | 0.190 |

Mean score: **0.083**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
