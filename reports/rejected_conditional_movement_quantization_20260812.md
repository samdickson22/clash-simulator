# Rejected: conditional movement position quantization

Date: 2026-08-12

Line profiling attributed 23.3 ms in one exact oracle label to movement-phase
position quantization across 17,248 troop/building component calls. The
candidate applied the exact coordinate-change guard accepted for combat
components, retaining native-grid publication whenever movement changed x or
y. Twenty-eight focused targeting, planner, and combat-guard tests passed.

The matched oracle screen used seed 9067, planner seed 2067, two states, depth
6, 32 simulations, 64 action samples, 8-tick steps, 11 alternating pairs, one
CPU process/thread, and `nice -n 10`.

- per-entity publication: 1.064133 seconds, 1.87946 labels/s
- conditional publication: 1.063423 seconds, 1.88072 labels/s
- ratio-of-medians: +0.067%
- paired median: +0.155%; 7/11 positive
- bootstrap mean 95% CI: -0.262% to +0.546%
- exact digest in every row:
  `8ddb12ddfb270c2696476d79980ae42112709128b7adf7689e8225e1479eb029`

The two coordinate snapshots and comparisons offset nearly all avoided
rounding work. The candidate failed the oracle attribution gate, so no rollout
timing was run. All source and benchmark-driver hunks were removed and no
commit was created.
