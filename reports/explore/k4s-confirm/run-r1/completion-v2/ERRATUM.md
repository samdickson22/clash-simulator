# K4S run r1: completion receipt erratum (counted-inventory envelope)

- **Recorded:** 2026-10-12T15:06:16Z (`date -u`). Found by the offline END-plan research draft (blocker 1) and confirmed by me.
- **The defect:** `completion/counted-inventory.json` (v1, `f10ab943…`) was written by `tools/final_pass.py` with the envelope `{schema: "clasher.k4s.counted-inventory.v1", study, sealed, outcomes_read, blocks}`. The frozen `end_evidence.counting` (end_evidence.py:80-86) requires exactly `{schema: "clasher.t1.counted-blocks.v1", outcomes_sealed: true, blocks}`. Every END reference, background slot and pool would therefore refuse.
- **Who caused it:** my 14:08Z plan said "frozen end_evidence format", and I checked only the row shape, not the envelope.
- **The candidate fix:** `completion-v2/`.
  - `counted-inventory.json` (`22c41cb7…`) has the frozen envelope with **byte-identical rows** (3,900).
  - `REPORTING-COMPLETION.json` (`3794d953…`) is v1 with `counted_inventory_sha256` updated and a `revision` block recording the v1 SHAs it supersedes.
  - `completed_at_utc` is unchanged (2026-10-12T14:45:34Z). Nothing else changes.
- **Validation:** `VALIDATION.txt`. The frozen `counting()` refuses v1 and accepts v2 (3,900 blocks, 99 losses, all 10 host phases).
- **Not changed by this:** the DBus disclosure and recount were computed over the same rows, so their numbers stand. They cite the v1 inventory SHA; the rows are identical.
- **Status:** v2 is a **candidate**. v1 stays committed, unchanged. The coordinator rules which completion receipt is of record before any END-JOB declaration.
