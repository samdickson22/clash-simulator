# C56 v3b Linux fleet results

Current v3b status: **COMPLETE** at 2026-10-08T02:14:11.960555+00:00: 1,767 units, 82,231 perspectives, 64,140,802 rows, 0 errors, retention 83.3255%; full checksum backup verified on 127x04.

## Production completion — 2026-10-08T02:14:11.960555+00:00

**COMPLETE: 1,767/1,767 units; 82,231 successful perspectives / 82,231 attempted; 64,140,802 persisted rows; 0 errors; 0 illegal labels.** Every persisted row passed the existing validators. Full-corpus retention **83.3255%**; placement acceptance **99.7213%**. Opponent-cut retention loss **0.1220 points**, within the 3-point rule. Runtime, extractor, recipe and frozen inputs remain pinned; no BC training or commits.

Published NPZ/sidecar pairs: **5,933,175,007 bytes**. The 811-unit base is included exactly once; 956 new units were extracted. All 1,767 expected unit keys and 82,231 perspective attempts are covered. Both phase-specific placement/retention gates passed.

- s117: 1334 units, 62,766 successful perspectives, 0 errors; retention 84.6415%; placement 99.7560%.
- s122: 433 units, 19,465 successful perspectives, 0 errors; retention 78.8310%; placement 99.5829%.

Production extraction (new units only; QA/collection overhead separate):

- 127x01: 300 units, 13,736 perspectives, 10,512,763 rows, 0 errors; wall 2557.960 s, CPU 105860.721 s, 422.21 units/hour; 964,036,631 bytes.
- 127x03: 437 units, 20,122 perspectives, 15,334,952 rows, 0 errors; wall 2582.370 s, CPU 154062.440 s, 609.21 units/hour; 1,406,301,362 bytes.
- 127x04: 219 units, 10,239 perspectives, 7,809,411 rows, 0 errors; wall 2838.238 s, CPU 84718.970 s, 277.78 units/hour; 716,435,910 bytes.

**127x04 complete-copy PASS** at 2026-10-08T02:13:43.597743+00:00: 3,547 files / 5,933,346,583 bytes, zero checksum differences, complete_corpus=true. The full `recon/engine-v3` output is at the same absolute path on 01 and 04.

**V2 preservation PASS:** all 137 original archives plus sidecars on every node remain checksum-identical to their preservation copies, 415,341,863 bytes per node. Required copies are at `127x01` and `127x04:/mpac/sdicks02/repos/clasher-local-data/c56-v2-archive-preserve/`; an additional verified copy is on 03. See v2-preservation-<host>.json and v2-final-verification-<host>.json.

Receipts: `qa/fleet-v3b/production-20261008/{completion-summary,production-completion,final-qa,mirror-127x04}.json`; corpus index/completion: `recon/engine-v3/{fleet-index,completion}.json`. Collector label `c56-v3b-production-20261008-supervise-r5`; extraction label `c56-v3b-production-20261008-extract` on each node. Retain all logs, exits and earlier interrupted/failed supervisor receipts.

No resume is needed after successful completion. For recovery or a repeat integrity audit, use `resume.txt` / `run-production.sh` after inspecting PID, lock and exit receipts. Exact collector command (fresh label; existing completed workers are reused):
```sh
ssh 127x01 'bash /mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/c56/data/qa/fleet-v3b/production-20261008/run-production.sh supervise c56-v3b-production-20261008-supervise-r6'
```

Overwrite audit PASS on 01/04: all 454 frozen inputs and 1,622 base files match pins, input ctimes predate the overwrite window, zero units invalidated. Collector r5 recomputed all 956 new-unit row audits under the explicitly verified frozen runtime after r4 caught its launcher binding error; earlier QA caches remain preserved and superseded. Root reports and small receipts are mirrored to 127x05; no NPZs are copied to the command center. Intermediate raw-equivalence and external-wrapper-overwrite incidents are retained below. The production wrapper is isolated under `scripts/fleet_v3b_production_worker_20261008.py`; original extractor SHA remains 8e95786c… and runtime SHA 1ec2c60c….


## Coordinator overwrite incident — audit completed 2026-10-08T01:53Z

Coordinator confirmed an unrequested Mac→fleet `rsync -a` overwrite at 01:39–01:45 UTC, affecting 01/04, not 03. Our collector detected the reverted fleet wrapper at 01:42:02Z; the running extraction pools retained their already-loaded production code. Production now uses the isolated `fleet_v3b_production_worker_20261008.py`. All original v2 archives remained intact.

Fresh audit on BOTH 01 and 04: all **1,622 base files** match mac-base.json by size and SHA256; all **454 frozen/extractor/runtime inputs** match expected pins, and **every checked input ctime predates 01:38:30Z**. Extractor 8e95786c…, runtime 1ec2c60c…, partition c365c45a… and isolated wrapper d1f47d39… all match. Therefore no extraction worker used changed input bytes; **zero units invalidated and zero reruns required**. No outputs deleted. Full per-file ctime-window inventories distinguish legitimate new production outputs/audit receipts from overwritten files; see `incident-input-audit-{127x01,127x04}.json`.

Immutable recovery receipts/helper were reconciled against the exact 127x05 git objects from **61892cc**, which includes the **61e0f8e** decision/docs. They already matched on the hub; per-node committed comparisons are in `incident-committed-check-<host>.json`. Root reports now retain the full committed historical record and the newer production addendum/live checkpoint. The received stale report versions and pre-reconciliation production copies are preserved under the production QA directory. No git commit was made by this worker. Coordinator has asked the Mac thread to stop pushing.


## Recovered-hub gates and production decision — restored after external stale copy

The 2026-10-08 recovery on 127x01 independently verified 1,622 Mac-base files and 454 frozen inputs; extractor SHA256 `8e95786c1dede45e9fd8d02f8c85cd86331667d3dbc5c8a6713808f0520ac9c7`, frozen runtime `1ec2c60c254fd9cc5579b163ef994a0e233a942bd97acda864d31d91442d3493`, Python 3.12.13 / NumPy 2.3.5. Fresh base QA: 811 units, 38,134 perspectives, 30,483,676 rows, zero errors/illegal labels (159.430 s wall / 1,265.876 s CPU). Three NPZ round-trips passed. Evidence: `qa/fleet-v3b/recovery-127x01-20261008/`.

Fresh simulation raw-byte gate initially stopped at 01:03:50Z: 0/3 raw NPZ matches. All logical arrays and normalized archives matched 3/3 (144 perspectives, 117,776 validated rows, zero errors; 338.024 s wall / 973.133 s CPU). Differences were only reuse-provenance headers and C/F order of flat_entity_features. Original failed strict-equivalence.json is preserved.

**Gate PASSED under the final coordinator decision: COORDINATOR.md, 2026-10-08 01:15 UTC.** Every array equals in dtype, shape and C-order values; header equals except v2 reuse provenance. Production authorized. Decision and accepted-gate receipts: `qa/fleet-v3b/production-20261008/{coordinator-decision.txt,equivalence.json}`. The old raw-byte stop below is historical and superseded.

Before any production launch, all 137 v2 archives plus 137 sidecars (415,341,863 bytes) were copied to `/mpac/sdicks02/repos/clasher-local-data/c56-v2-archive-preserve/` on EACH of 127x01/03/04. All three preservation manifests equal and every checksum verified; originals retained. Receipts: `v2-preservation-<host>.json`. The unchanged extractor's legacy deletion is suppressed only for v2 NPZs through a Path retention guard; reuse, recipe, engine and extractor source SHA unchanged. Do not run extract_v3.py directly.

All nodes passed fresh pins/base checks and empty who before launch. Deterministic weighted partition recorded BEFORE launch: 01=300 units / 44 extraction workers, 03=437 / 64, 04=219 / 32; four hub validation workers keep total C56 workers <=48 on 01. Console cap 16. Launch 2026-10-08T01:14:36Z. Drivers: 01=3342515, 03=3366753, 04=2224842. Worker niceness is 19 on 01 (nested local launcher), 10 on 03/04; BLAS threads=1. 12 GiB free / 7.5 GiB hard data guards; 0.5% failure limit. No training, commits, forbidden hosts or archive deletion.

Extraction label on each node: `c56-v3b-production-20261008-extract`. Collector r1 exited before dispatch due SSH-to-self authentication; fixed with local hub commands. Collector r2 was deliberately SIGTERM'd after verifying its collector-only group to add collection disk guards; extraction untouched. Collector r3 exited 1 at 01:42:02Z because an external bulk rsync restored old fleet_v3b.py and old root reports on 01/04 (old wrapper ccab87bb..., production wrapper d1f47d39...). All extraction pools kept their loaded production code; 137 original v2 archives remained on each node. No external rsync was stopped. Evidence: collector-restart-r3.json and wrapper-overwrite-recovery.json.

Current collector: **c56-v3b-production-20261008-supervise-r4**, launcher **3368041** (Python PID in supervisor.json). Its production wrapper is isolated as `scripts/fleet_v3b_production_worker_20261008.py`, with the same d1f47d39... bytes. Collection resumes existing immutable assignments, hashes and row-validation caches. It performs continuous checksum rsync and all-row validation, full-corpus QA/retention, final preservation checks and explicit checksum backup to 04. No extraction restarted.

Exact restart/collection instructions: `qa/fleet-v3b/production-20261008/resume.txt` and `run-production.sh`. If the collector alone is inactive, resume with:
```sh
ssh 127x01 'bash /mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/c56/data/qa/fleet-v3b/production-20261008/run-production.sh supervise c56-v3b-production-20261008-supervise-r5'
```
Verify PID/lock/exit first. Failed worker relaunches require a fresh per-host label in launch-labels.json and verified inactive old process trees; preserve outputs and reuse. A missing exit is never success. Full completion requires production-completion.json, final-qa.json, recon/engine-v3/completion.json and mirror-127x04.json with complete_corpus=true / zero checksum differences.

Only root reports, scripts and small receipts are mirrored to 127x05; no NPZ. Current output and QA live on 127x01. 127x04 receives periodic copies plus explicit checksums. The latest partial mirror at 01:35:33Z verified 2,341 files / 4,106,228,190 bytes with zero differences; full-corpus copy remains pending.




<!-- C56-PRODUCTION-STATUS -->
2026-10-08T02:13:48.040428+00:00: COMPLETE; fleet 1767/1767 units; hub row-validated 1767 units / 82,231 perspectives / 64,140,802 rows; errors 0, illegal labels 0; available-corpus retention 83.3255%.

- 127x01: 300 assigned units done, 44 workers, driver 3342515, wall 2558.0s / CPU 105860.7s; 422.2 units/hour; ETA 0.00 hours.
- 127x03: 437 assigned units done, 64 workers, driver 3366753, wall 2582.4s / CPU 154062.4s; 609.2 units/hour; ETA 0.00 hours.
- 127x04: 219 assigned units done, 32 workers, driver 2224842, wall 2838.2s / CPU 84719.0s; 277.8 units/hour; ETA 0.00 hours.

Status and resume receipts: `qa/fleet-v3b/production-20261008/`; detached labels `c56-v3b-production-20261008-extract` (each node) and the hub supervisor recorded in `supervisor.json`. Full retention/final QA remains pending unless COMPLETE.
<!-- /C56-PRODUCTION-STATUS -->

## Committed historical record (61892cc / 61e0f8e)

## Re-verification on the recovered hub

Hub readiness was observed at 00:55:10Z (marker dated 00:54:44.911798Z); no C56 fleet writes preceded it. All **1,622 base files**, **454 frozen inputs**, and the exact **811-unit** production inventory passed verification, both before and after fresh replay. These new receipts replace historical 127x02 evidence for this hub.

- Original extractor SHA256: `8e95786c1dede45e9fd8d02f8c85cd86331667d3dbc5c8a6713808f0520ac9c7`.
- Frozen runtime SHA256: `1ec2c60c254fd9cc5579b163ef994a0e233a942bd97acda864d31d91442d3493`.
- Gamedata SHA256: `3d99987c19cb94a0c8a6795e943829771078e564859e34c1411e221e5d57486a`.
- Fresh base row QA: **38,134 perspectives / 30,483,676 rows**, zero extraction errors and illegal labels; eight validators, **159.430 s wall / 1,265.876 s CPU**.
- All three NPZ serialization round-trips matched their Mac archives byte-for-byte; **1.301 s wall / 1.299 s CPU**.

## Fresh simulation incident

Re-simulated `s117/shard-011-part-04/05/06` with the unchanged extractor/runtime: **144 perspectives, 117,776 validated rows, zero errors, zero illegal labels**. No v2 archive was available for reuse for these comparison units.

**Raw archive SHA256 matches: 0/3.** All non-header arrays match dtype, shape and logical bytes, and the header comparison differs only in `extra`. Historical archives record 10/11/12 reused-v2 episode IDs and their old v2 archive hashes; fresh replay records no reuse and a null v2 hash. `flat_entity_features` also has different C/F storage order. The existing diagnostic comparison restores the historical header and storage order in separate `.normalized.npz` files; those match the Mac archives exactly (3/3). This normalization is **diagnostic only and was not accepted as satisfying the requested raw-byte gate**. No simulation-row mismatch was found; no recipe or engine change was attempted.

Equivalence stage: **338.024 s wall / 973.133 s CPU**. Per-unit replay wall: part 04 **332.63 s**, part 05 **309.05 s**, part 06 **315.93 s** (parallel, not additive wall time). Exact original/raw/normalized hashes and metadata differences are in `strict-equivalence.json`.

## Corpus and retention

Production remains **811/1,767 units**, **38,134 perspectives**, **30,483,676 rows**, **0 errors**; **956 units remain**, **0 new production units**. The comparison units duplicate existing base perspectives and are excluded from production totals.

**Base-only retention: 84.7863%** (30,430,122 supervised rows / 35,890,374 possible decisions), measured with the existing aggregate function over the independently audited base summaries. Base placement acceptance: **99.7561%**. **Full-corpus retention and final QA are unavailable**, because the remaining units were not extracted.

## Timing, storage and lifecycle

- **127x01:** gate job **504.25 s wall / 2,245.80 s CPU** total (includes Python startup and all gate stages); initial hash verification **2.016 s wall / 2.015 s CPU**. Three fresh replay workers; eight earlier audit workers; all nice 10, one-thread BLAS. No production extraction.
- **127x03:** no C56 extraction launched; extraction wall/CPU **0/0 s**.
- **127x04:** no C56 extraction launched; extraction wall/CPU **0/0 s**. Backup verification is separate from extraction.
- Production NPZ/sidecar pairs: **2,846,401,104 bytes** (2.651 GiB).
- Fresh comparison raw NPZs: **11,097,355 bytes**; including their sidecars: **11,189,720 bytes**. Round-trip and normalized diagnostic archives remain separate under QA.
- Post-gate C56 data: **3,999,658,586 bytes**; /mpac free: **1,793,815,760,896 bytes**. The 12 GiB free / 7.5 GiB hard guard was not approached.
- Hub output: `127x01:/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/c56/data/recon/engine-v3`.
- Evidence: `127x01:/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/c56/data/qa/fleet-v3b/recovery-127x01-20261008/`.
- Backup: corresponding paths on **127x04**, independently verified at **01:06:35Z**: all 1,622 base files / 454 frozen inputs match; all **843 recovery-QA files / 136,839,463 bytes** copied with zero checksum differences (scope before the mirror receipt itself). Receipt: `mirror-127x04.json`.
- Coordinator mirror: PROGRESS/FLEET-RESULTS, helper and small receipts only on **127x05**; no NPZ transfer to the command center.

Detached label `c56-v3b-recovery-127x01-20261008-gates`, launcher PID **3325932**, Python PID **3325945**. The job finished with explicit **exit 1**, enforcing the equivalence stop. Logs/lock/PID/exit are under `/mpac/sdicks02/jobs/clasher/`. No extraction supervisor was launched. Inspect with:
```sh
ssh 127x01 'cat /mpac/sdicks02/jobs/clasher/c56-v3b-recovery-127x01-20261008-gates.exit; tail -30 /mpac/sdicks02/jobs/clasher/c56-v3b-recovery-127x01-20261008-gates.log'
```
Do not resume production under the failed strict gate. A new comparison attempt requires a fresh QA namespace and label; existing archives/receipts must be preserved.

The new helper wraps the unchanged extractor and existing validators. Original fleet scripts, frozen runtime and recipe are unchanged. Retained 137 v2 archives were not deleted; any eventual production orchestration must preserve them because the original extractor deletes reused v2 NPZs. No data deletion, BC training, git commit, forbidden-host access, or unrelated process signal occurred.

All owned gate PIDs were verified absent after exit 1. No C56 job remains active.


## Final collector runtime binding correction
{"utc": "2026-10-08T02:05:23.286637+00:00", "issue": "fleet_run resets CLASHER_ROOT/PYTHONPATH; run-production.sh r3/r4 exported them before launcher without post-launch env override. Remote extraction commands always had explicit env and correct verified frozen runtime. Hub collector row QA r3/r4 used workspace imports; final bind_runtime gate correctly stopped completion.", "fix": "run-production.sh now puts explicit env after fleet_run; supervisor asserts bind_runtime and frozen SHA at startup; preserve all previous collector QA caches and recompute all 956 new-unit audits under frozen runtime; reuse only 811 independently verified frozen-runtime recovery base audits, recheck every final corpus hash.", "extraction_outputs_invalidated": 0, "extraction_reruns": 0, "preserved_cache": "reports/strategy_council_20260928/c56/data/qa/fleet-v3b/production-20261008/unit-audits-before-runtime-binding-fix", "new_supervisor_label": "c56-v3b-production-20261008-supervise-r5"}
