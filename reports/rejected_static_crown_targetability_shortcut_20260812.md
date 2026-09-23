# Rejected: static Crown targetability shortcut (2026-08-12)

The candidate recognized data-driven native Crown Towers by their shared
`_crown_tower_slot` contract and bypassed their inactive dynamic targetability
checks. Alive/enemy/kind, pending-projectile reservation, attacker mechanics,
and air/ground gates remained exact; hidden/mechanic/stealth/nonstandard towers
fell back to the full validator.

Thirty focused Crown fallback, hidden-building, fixed-seed, and direct-selector
tests passed. The exact oracle screen used seed 9087, planner seed 2087, two
snapshots, depth 6, 32 simulations, 64 action samples, 11 alternating pairs,
one process/thread, and `nice -n 15` on Apple M4 Pro.

| variant | seconds | labels/s |
| --- | ---: | ---: |
| dynamic validator | 0.803812 | 2.488144 |
| static-Crown branch | 0.819867 | 2.439419 |

The candidate regressed 1.958% by ratio of medians. Every row produced exact
action/state/planner-RNG digest
`f542ffd41680ffc84cdf6352cd86abb6519d8909cd41ea08ce9cce2dcf301c14`.
The branch's classification cost applies to every scalar target validation and
overwhelms the saved work on Crown targets. All candidate source, test, and
benchmark hunks were removed; no commit was created.
