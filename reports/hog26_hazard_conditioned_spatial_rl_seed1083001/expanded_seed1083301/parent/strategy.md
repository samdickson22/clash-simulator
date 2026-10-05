# Strategy benchmark: update 46

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000046.pt`

Protocol: 2 paired-seat games per opponent, seed 1083302, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -2.000 | 0.1440 | 0.060 | 0.190 |
| slow-push | 0-2-0 | 0.000 | -2.000 | 0.1458 | 0.061 | 0.190 |
| spell-control | 0-2-0 | 0.000 | -1.500 | 0.0628 | 0.055 | 0.190 |
| reactive-defense | 0-2-0 | 0.000 | -1.000 | 0.0577 | 0.053 | 0.190 |
| split-lane | 1-1-0 | 0.500 | +1.000 | 0.0710 | 0.062 | 0.048 |
| balanced | 0-2-0 | 0.000 | -1.500 | 0.0774 | 0.056 | 0.190 |

Mean score: **0.083**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
