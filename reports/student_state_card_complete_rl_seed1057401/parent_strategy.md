# Strategy benchmark: update 20

Checkpoint: `/Users/sam/Desktop/code/clasher/checkpoints/student_state_symmetry_dagger_seed1056901/iteration2.pt`

Protocol: 4 paired-seat games per opponent, seed 1057401, reward profile `defense-v2`. Opponents use public information only.

| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |
|---|---:|---:|---:|---:|---:|---:|
| bridge-pressure | 3-1-0 | 0.750 | +1.000 | 0.1219 | 0.057 | 0.071 |
| slow-push | 3-1-0 | 0.750 | +1.250 | 0.1196 | 0.037 | 0.071 |
| spell-control | 3-1-0 | 0.750 | +1.750 | 0.0600 | 0.064 | 0.071 |
| reactive-defense | 3-1-0 | 0.750 | +0.250 | 0.0860 | 0.062 | 0.071 |
| split-lane | 3-1-0 | 0.750 | +1.000 | 0.0767 | 0.052 | 0.071 |
| balanced | 1-3-0 | 0.250 | -0.750 | 0.1027 | 0.061 | 0.643 |

Mean score: **0.667**. Worst matchup: **balanced** at **0.250**.

The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.
