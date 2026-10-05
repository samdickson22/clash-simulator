# Strategy benchmark: update 40

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_u20_strategy_hazard_adapter_seed1082001/gain_sweep/policy_v2_update_000040_gain_0p2000.pt`

Protocol: 2 paired-seat games per opponent, seed 1082502, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -3.000 | 0.1477 | 0.054 | 0.167 |
| slow-push | 0-2-0 | 0.000 | -1.000 | 0.1161 | 0.059 | 0.167 |
| spell-control | 0-2-0 | 0.000 | -2.500 | 0.0859 | 0.049 | 0.167 |
| reactive-defense | 0-2-0 | 0.000 | -1.000 | 0.0580 | 0.061 | 0.167 |
| split-lane | 0-2-0 | 0.000 | -2.000 | 0.0752 | 0.055 | 0.167 |
| balanced | 0-2-0 | 0.000 | -2.000 | 0.0811 | 0.051 | 0.167 |

Mean score: **0.000**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
