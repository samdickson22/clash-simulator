# Rejected: conditional object-phase position quantization

Date: 2026-08-12

The candidate guarded the object-phase native-grid publication with an exact
x/y change check. This was intended to skip rounding after character object
ticks that update deployment/status clocks while preserving publication for
all moving projectile, effect, and character hooks. Twenty-eight focused
tests passed and all oracle traces remained exact.

The matched oracle screen used seed 9071, planner seed 2071, two states, depth
6, 32 simulations, 64 action samples, 8-tick steps, 11 alternating pairs, one
CPU process/thread, and `nice -n 10`.

- per-entity publication: 1.095651 seconds, 1.82540 labels/s
- conditional publication: 1.094528 seconds, 1.82727 labels/s
- ratio-of-medians: +0.103%
- paired median: +0.276%; 9/11 positive
- bootstrap mean 95% CI: -0.141% to +0.598%
- exact digest:
  `3d50f3eff3e4798f77c6b9b72b15339a08c1866aa1a5efc050e7238ea7408255`

The confidence interval crossed zero and the ratio gain was below useful
end-to-end attribution. No rollout screen was run. All source and driver
hunks were removed and no commit was created.
