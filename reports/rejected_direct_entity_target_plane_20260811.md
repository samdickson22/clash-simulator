# Rejected direct Entity target-plane reads

Date: 2026-08-11

The candidate replaced the defensive `getattr(entity, "is_air_unit", False)`
inside `is_airborne_target` with a direct required `Entity.is_air_unit` read.
It was exact for ground, air, and dynamic river-jump states, but a bounded
production-shaped oracle screen did not establish a reliable throughput gain.

Configuration: Apple M4 Pro; seed 2301; planner seed 901; three fixed battle
snapshots; depth 6; 32 simulations; 64 sampled actions; 8-tick planner steps;
seven alternating matched pairs; exact fast path; one process at `nice -n 10`.
RoadForge occupied one CPU core and a Clasher MPS fit was active.

Defensive median was 1.148982 seconds (2.611007 labels/s); direct median was
1.145266 seconds (2.619478 labels/s), a +0.32% ratio-of-medians result. The
within-pair gains were +1.04%, +1.16%, -1.05%, -1.89%, +0.11%, +0.37%, and
-0.04%: paired median +0.11%, mean -0.04%, sample standard deviation 1.10
percentage points. Four of seven pairs were non-positive.

Every row produced exact digest
`9579e60e44e50afa3ff70d2bb2d251a9888dbacd5b6dd854d2e37488522b7de6`.
Forty-three focused target-plane/collision/targeting tests passed, including
fixed off/shadow/on traces with zero shadow mismatches.

The evidence is below the acceptance threshold. All candidate source, test,
and benchmark-driver changes were removed; this uncommitted report is retained
only as an audit artifact.
