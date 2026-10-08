# C56 v3b Linux fleet results

Status: **HALTED — fresh raw-archive byte-equivalence gate failed** on 127x01 at 2026-10-08T01:03:50Z. The 956-unit remainder was not launched. No completion claim or full-corpus receipt is made.

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
