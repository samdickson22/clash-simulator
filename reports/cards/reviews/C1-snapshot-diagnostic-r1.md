# Bounded C1 snapshot diagnostic — 2026-10-16

Independent GPT-6-Astra high, read-only; task `node:delegated-task:command%3Amcp%3A6341b5cc-7a1e-4e02-83d8-7f564834b4a7%3Adelegate-task%3Acards-c1-snapshot-diagnostic-astra-20261016-r1`.
Evidence is copied partial output of the inherited old-native run, not final acceptance evidence. No engine execution, build, remote command or file change by diagnostic worker.

Sent diagnosis directly to CARD LEAD. Both evidence hashes match; no files changed or engine/build commands run.

First two AxeMan records: **alone t112/id11** and **knight t29/id9** both show Python `pp_t=0` versus native omission, and Python `aim=None` versus native coordinates.

- **(a) `pp_t`: zero/omission is representation-only.** [lib.rs:422](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/src/lib.rs:422) omits zero during serialization and defaults missing values to zero during construction. Safely compare missing native `pp_t` as zero for `PingpongProjectile`. Preserve nonzero values: they control movement, lifetime, and return-leg hit-history clearing.
- **(a) `hit_ids`: order-only normalization is safe for the recorded permutation.** Python export sorts IDs; native appends IDs and tests membership in [projectiles.rs:31](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/src/projectiles.rs:31). Compare sorted lists only for `PingpongProjectile`, preserving identity and multiplicity. Never discard hit history or change damage-processing order. Log/Bandit remains B2-owned.
- **(c) `aim`: native-side redundancy established; complete proof unresolved.** Native derives `pp_origin`/`pp_apex` at creation and subsequently moves using those fields and `pp_t`. However, the approved Python file contains only `ProjectileLaunch`, not pingpong mechanics. Smallest follow-up: C1 owner inspect `entities.py`’s pingpong creation/update and the base exporter, then verify one exact birth-state continuation through return/expiry before excluding `aim`.
- **(c) `mk_target_dies.projectile_origin`: case unresolved; (b) meaningful risk exists.** Neither copied report contains this case. Native uses `aim − projectile_origin` to determine child-projectile direction in [projectiles.rs:207](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/src/projectiles.rs:207). Constructor import preserves it. Retain comparison; obtain the first mismatch and child-projectile stats. If that reader is reachable, test the exact pre-impact continuation for child directions, positions, and damage.

The probe compares exports directly; it does **not** round-trip each compared state through the constructor. Digest equality provides no continuation proof. Final-native C56/integration gates remain pending, with **B2 → C1** unchanged.
