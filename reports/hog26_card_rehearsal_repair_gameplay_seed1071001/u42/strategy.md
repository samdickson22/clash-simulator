# Strategy benchmark: update 42

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_card_rehearsal_repair_seed1070801/policy_v2_update_000042.pt`

Protocol: 4 paired-seat games per opponent, seed 1071002, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-4-0 | 0.000 | -2.000 | 0.1506 | 0.057 | 0.213 |
| slow-push | 0-4-0 | 0.000 | -2.250 | 0.1719 | 0.053 | 0.213 |
| spell-control | 1-3-0 | 0.250 | -1.000 | 0.0562 | 0.061 | 0.120 |
| reactive-defense | 0-4-0 | 0.000 | -1.500 | 0.0884 | 0.059 | 0.213 |
| split-lane | 1-3-0 | 0.250 | -1.000 | 0.1616 | 0.058 | 0.120 |
| balanced | 1-3-0 | 0.250 | -1.000 | 0.0871 | 0.058 | 0.120 |

Mean score: **0.125**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
