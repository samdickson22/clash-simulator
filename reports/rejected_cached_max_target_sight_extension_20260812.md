# Rejected: cached maximum target sight extension

Date: 2026-08-12

The candidate cached the process-immutable maximum building/Crown sight
extension used to bound scalar target bucket queries. Twenty-one exact bound,
sight, and planner tests passed and every oracle trace matched.

The matched oracle screen used seed 9119, planner seed 2119, two states, depth
6, 32 simulations, 64 action samples, 8-tick steps, 11 alternating pairs, one
CPU process/thread, and `nice -n 10`.

- recomputed: 0.782241 seconds, 2.55676 labels/s
- cached: 0.776572 seconds, 2.57542 labels/s
- ratio-of-medians: +0.730%
- paired median: -0.162%; only 5/11 positive
- bootstrap mean 95% CI: -1.094% to +2.235%
- exact digest:
  `27166a64c73c1348a5f53aced46a6cece95dc0f80e9f013466fcedab70b520c6`

The paired screen did not establish a gain, so no rollout timing was run. All
source and driver hunks were removed and no commit was created.
