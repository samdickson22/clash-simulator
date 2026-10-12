
## 2026-10-12 16:35Z: RS-2 stopped at driver preflight (coordinator path error); RS-3 driver launch once with corrected R5 path

**What stopped.** RS-2 got further this time. The cache was moved and preserved, and the builder ran once, creating private descendant **2473c0a9** (parents 9bb349b1 and 67b05a50, 16 Mac paths). BC1 and BC2 passed, and canonical R is now at 2473c0a9 and clean. The driver preflight then stopped with FileNotFoundError, before it created `release-private/` and before the driver launched (T1 receipt `END-release-sequence-STOP-2510ff14-r2.json`).

**Cause: the coordinator's mistake.** RS-2 (2510ff14) gave the `--r5` path as `<canonical R>/reports/explore/t1/receipts/END-A5-R5-sealed-prerelease-evidence.json`. That file is not in canonical R. The sealed R5 is committed in the public tree at bbff541c and lives in T1's worker checkout: `/mpac/sdicks02/jobs/clasher/t1-health-stop-reconcile-20261010/reports/explore/t1/receipts/END-A5-R5-sealed-prerelease-evidence.json`, SHA-256 **3b7d2295…a5f9**, which equals origin/main. The driver pins only the R5 SHA, not its path. The release file is unchanged (6a767ffb).

**Ruling RS-3.** T1 runs the driver launch preflight and launch **exactly once**:
- with `--r5` set to the worker-checkout path above;
- with every other argument as in RS-2: release 6a767ffb, copy receipt d433dd54, private name `mac-summary-20261012-r2` (still unused), and `release-private/` created fresh as 0700.

Do not repeat the cache move, builder or switch; they are done. Any failure is a STOP with no retry. `A3PRequiresRuling` comes back to the coordinator. There is still no 14-day route.
