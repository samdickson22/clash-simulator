
## 2026-10-12 16:32Z: T1 release sequence stopped at BC1_before (harmless cause); one fresh attempt authorized with release file

**What stopped.** T1's release script stopped at its first pre-check (`BC1_before`, AssertionError) and did not retry, as instructed. Nothing ran after that check: the builder never ran, no ref was created and no checkout was switched. STOP receipt: T1 4925002b.

**Cause (coordinator read-only replay).** T1's script requires the tool directory in its own worker checkout (`t1-health-stop-reconcile-20261010/reports/explore/t1`) to contain exactly the tracked files. That directory held an ignored `__pycache__/` with 4 stale `.pyc` files from earlier test runs (one is cpython-38). Every other check passed on replay:
- both tool SHAs (dd644cdc, 9ffbd2e1) match;
- canonical R is clean with `--ignored`;
- R HEAD and the protection ref are both 9bb349b1;
- e4v3 is mode 555;
- target ref `refs/private/t1-mac-release-20261012-r1` is unused (symbolic-ref exits 1, for-each-ref is empty for the ref and its prefix).

**Ruling RS-2 (one fresh attempt).**
1. T1 **moves** (does not delete) that `__pycache__/` to `BASE/END-release-sequence-20261012-r1/quarantine-pycache/` and records the 4 names and SHAs.
2. T1 then reruns the same reviewed sequence exactly **once**, with a new state directory `BASE/END-release-sequence-20261012-r2/`. The pins, the target ref (BC1 re-verifies it is unused) and the order stay the same: BC1-before → builder dd644cdc → BC1-after → BC2 switch/post-checks → driver 9ffbd2e1.
3. Any failure at any stage is a STOP with no retry and goes back to the coordinator. `A3PRequiresRuling` is returned for a selection ruling. There is still no 14-day route.

**Release file (coordinator-supplied, per runbook step 1).**
- Path: `/mpac/sdicks02/jobs/clasher/t1-20261010-r1/coordinator-release-r1/release-mac-summary-r1.json` (mode 0444).
- SHA-256: `6a767ffb26c50a629049dc6b2b708a7d23395f74e60f7401a6ccf31c25bc8eaa`.
- It binds:
  - reason `committed_mac_summary`;
  - commit 67b05a50;
  - summary 6b0324e0, A3-P 29f86b81 and seal f411b9b4, each as full `{path, commit, sha256}` under `reports/explore/mac-e4-session/tiers-session-r1/`;
  - `amendment_1_prerelease` copied byte-for-byte from sealed R5 3b7d2295;
  - `authorization_message_id` = COORDINATOR 446e9901.
- The coordinator checked every Mac SHA against `git show 67b05a50:<path>`, and checked that the A3-P `receipt_manifest_sha256` and the seal's `tiers-summary.json` entry are consistent. `release_reference.prerequisites()` passes against canonical R (read-only).
- Driver arguments: `--release <path above> --release-sha256 <SHA above> --r5 <canonical R>/reports/explore/t1/receipts/END-A5-R5-sealed-prerelease-evidence.json`.
