# K4S END plan: draft for review (offline; nothing launched)

- **Recorded:** 2026-10-12T15:07:07Z (`date -u`). Requested by the coordinator after reporting completed (COORDINATOR 50b519e6). It is a plan only: no END, pool, Mac or release step has been run or staged.
- **Main document:** `K4S-END-PLAN-DRAFT-research.md` (sha256 `67ea1070…`). It was written read-only by a delegated Opus 5.5 researcher at high effort, who used a read-only native Explore agent at default effort for the T1 sweep. Citations are path:line and commit.

## My verification of its three blockers

- **B1 (counted-inventory envelope): CONFIRMED.**
  - The frozen `end_evidence.counting` refuses the committed v1 inventory `f10ab943` and accepts the re-enveloped candidate `completion-v2/` (inventory `22c41cb7`, completion `3794d953`, rows identical): 3,900 blocks, 99 losses, all 10 host phases. See `completion-v2/VALIDATION.txt` and `ERRATUM.md` (commit 23604d1c).
  - The coordinator rules which completion is of record before the END-JOB.
- **B2 (per-phase `mhz.jsonl` and `census.jsonl` are not committed): CONFIRMED from code.**
  - `supervise.py` (391d2006) l.111-116 appends both to `<job>/<phase>/` only.
  - That they exist on the hosts is **not yet checked**; it needs a name listing over SSH.
  - The copy must fetch exactly those two paths, never a glob. The phase directories also hold block folders.
- **B3 (the guard needs a T1-shaped freeze, and no fleet-reference bundle assembler exists): CONFIRMED from code.**
  - `e4v3/fleet_validity.py` ReportingGuard requires `operational_delta_op5`, `operational_delta_op5_08` and `operational_delta_op6` to be CONFIRM, and requires the guard modules to be pinned under `reports/explore/t1/`.
  - The draft's claim about `prepare_bundle.py` profiles is not independently re-checked.

## R4 (04 bus baseline)

`end-gate/04-dbus-baseline-r1/` is finishing at about 15:15Z. Interim over 1,266 s: whole window 0.036% of one core, max 30-s window 0.10%, and no window at or above 0.7%.

## For review

Sections 1-8 of the draft: bytes and pins, wrapper and verifier, attempt roots, launch conditions (the C5 no-SSH rule, pre-exec gates, quiet-read v3), schedule, the DBus branch (a)/(b)/(c), ordering (END → pool → K4S Mac phase C after the TIERS Mac session → release), and open questions.
