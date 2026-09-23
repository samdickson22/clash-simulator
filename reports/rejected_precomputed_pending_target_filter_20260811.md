# Rejected precomputed pending-projectile target filter

The fixed post-`9736a32` profile showed 77,907 calls to
`ignores_targets_with_pending_projectile_damage` across 12,919 scalar target
queries. A candidate computed that attacker-owned capability once per query and
passed it through the existing target validator.

The candidate passed 36 pending-projectile, fast-target, target-switching, and
coalesced-target tests. Its fixed strategy rollout hash matched the reference:

`d8652cd9a634639486e9f3d28ae4960335a801c5dc8d7fc8af15805586be841c`

Bounded matched timing used one process at `nice -n 15` while RoadForge occupied
one CPU core:

- seed 2301, balanced strategy, 1 env x 256 steps, 11 alternating pairs
- reference median: 2.077176 s, 123.244 decisions/s
- candidate median: 2.057513 s, 124.422 decisions/s
- ratio of medians: +0.96%
- paired median: +0.30%; 7/11 pairs positive

The paired results ranged from -6.58% to +24.66% and did not establish a stable
end-to-end gain. The source, tests, and benchmark toggle were removed; this
candidate is not part of the optimizer stack.
