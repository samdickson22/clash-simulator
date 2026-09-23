# Rejected reused scalar target sight distance

The post-`9736a32` profile showed 25,719 scalar sight checks immediately after
the same target distance had already been computed. A candidate passed that
exact float into `is_within_sight` while preserving the public recomputing
default.

The candidate passed 48 sight-range, fast-target, target-switching, and fixed
off/shadow/on trace tests. Its fixed strategy rollout hash matched the
reference:

`d8652cd9a634639486e9f3d28ae4960335a801c5dc8d7fc8af15805586be841c`

Bounded matched timing used seed 2301, balanced strategy, 1 env x 256 steps,
11 alternating pairs, and `nice -n 15`:

- recomputed median: 1.881031 s, 136.096 decisions/s
- reused median: 1.897255 s, 134.932 decisions/s
- ratio of medians: -0.86%
- paired median: -0.23%; 5/11 pairs positive

The optional argument and hot-loop branch cost outweighed the duplicate scalar
distance calculation. Source, tests, and the benchmark toggle were removed;
this candidate is not part of the optimizer stack.
