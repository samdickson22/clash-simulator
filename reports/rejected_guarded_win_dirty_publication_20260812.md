# Rejected: guarded Crown dirty publication (2026-08-12)

The follow-up to `53f988f` checked the shared `_crown_tower_slot` mechanic
before resolving and calling the win-refresh publisher after damage, healing,
or intrinsic lifetime decay. It retained the full shared helper for Crown
candidates and contained no card-name or deck special cases. A focused gate
of 158 win-rule, determinism, and enabled-spell tests passed after correcting
non-Crown building-death cache invalidation scope.

The bounded exact stable-root oracle used seed 9097, planner seed 2097, two
states, depth 6, 32 simulations, 64 action samples, 11 alternating pairs, one
CPU process/thread at `nice -n 10`, and no MPS/GPU. Another low-CPU Clasher
process remained resident.

| variant | median seconds | labels/s |
| --- | ---: | ---: |
| unconditional publisher | 0.434516 | 4.6028 |
| guarded publisher | 0.435266 | 4.5949 |

The guard regressed **-0.172%** by ratio of medians and **-0.159%** paired
median; only 4/11 pairs improved and the bootstrap mean 95% CI was -0.370% to
+0.125%. Both variants produced exact action/state/battle-RNG/planner-RNG
digest `5db565999411db7928e73805370026fcb8e04910d06670357ea3df67ad945308`.

The extra slot predicate cost more than the avoided helper lookup. The
candidate was rejected before rollout timing, all source/driver hunks were
removed, and no commit was created.
