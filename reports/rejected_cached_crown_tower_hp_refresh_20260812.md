# Rejected: cached Crown Tower HP refresh (2026-08-12)

The candidate retained exact references to the six arena Crown Tower objects
and iterated them during `_update_tower_hp`, avoiding the all-entity scan in
every tick's win check. Dead/removed towers remained referenced so terminal
zero HP stayed observable. Clone tests proved each cloned reference pointed to
the clone's own isolated tower object.

The fixed exact-oracle screen used seed 9083, planner seed 2083, two snapshots,
depth 6, 32 simulations, 64 action samples, 8-tick steps, 11 alternating warm
pairs, one process/thread, and `nice -n 15` on Apple M4 Pro.

| variant | seconds | labels/s |
| --- | ---: | ---: |
| all-entity scan | 0.738924 | 2.706638 |
| cached six towers | 0.739469 | 2.704642 |

The candidate measured +0.137% paired median, 7/11 positive, with bootstrap
mean 95% confidence interval -0.189% to +0.627%; ratio of medians was -0.074%.
Every row produced exact action/state/planner-RNG digest
`57c9dd3cc9124a83076f4c2b71b4c6e585c3f6cb7a047f11ce09c4bdbab2265c`.
Fourteen clone/idle/fixed-seed focused tests passed before timing.

The evidence does not establish end-to-end value. Candidate source, tests, and
benchmark-driver hunks were removed; no commit was created.
