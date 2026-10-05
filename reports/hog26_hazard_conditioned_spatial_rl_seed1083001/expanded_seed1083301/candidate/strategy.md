# Strategy benchmark: update 56

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/hog26_hazard_conditioned_spatial_rl_seed1083001/policy_v2_update_000056.pt`

Protocol: 2 paired-seat games per opponent, seed 1083302, reward profile `objective-v1`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 0-2-0 | 0.000 | -2.000 | 0.1392 | 0.063 | 0.190 |
| slow-push | 0-2-0 | 0.000 | -2.000 | 0.1464 | 0.062 | 0.190 |
| spell-control | 0-2-0 | 0.000 | -1.500 | 0.0677 | 0.050 | 0.190 |
| reactive-defense | 0-2-0 | 0.000 | -1.000 | 0.0756 | 0.060 | 0.190 |
| split-lane | 1-1-0 | 0.500 | +0.000 | 0.0677 | 0.064 | 0.048 |
| balanced | 0-2-0 | 0.000 | -2.500 | 0.1018 | 0.057 | 0.190 |

Mean score: **0.083**. Worst matchup: **bridge-pressure** at **0.000**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
