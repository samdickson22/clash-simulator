# C56 v3b Linux fleet results

Blocked as of 2026-10-07T23:28:13.625612+00:00. 127x02 SSH timed out both directly from the Mac and through 127x01 over campus LAN. The compute nodes remain reachable. No fresh extraction had started at the 23:27Z check.

- Finished base: 811/1,767 units, 38,134 perspectives, zero recorded failures. Remaining: 956 units. New Linux units: 0.
- Integrity: all 1,622 NPZ/sidecar files and 454 frozen inputs match the Mac by SHA256. The hub has no extra production units.
- QA: all 30,483,676 base rows passed the existing validators, with zero illegal labels. Wall time 368.63 s; CPU time 2,874.65 s.
- Equivalence: three existing NPZ archives reserialize byte-for-byte on Linux. Fresh simulation replay remains pending, so Linux extraction equivalence is not yet established.
- Retention and extraction timing: final full-corpus retention, wall time and CPU time are unavailable; fresh extraction did not start.

The frozen Python runtime and original extractor are unchanged. Fleet wrappers were prepared for 64 nice-10 workers per idle node, one-thread BLAS, deterministic partitioning, the existing quality/error gates, disk guards, checksum collection and full row QA. Verification modes passed; extraction modes remain unexecuted.

Outputs last verified at `127x02:/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/c56/data/recon/engine-v3`. Evidence is under `c56/data/qa/fleet-v3b/`. Detached supervisor `c56-v3b-fleet-20261007-supervise-r2` may still be running and can continue when prerequisites pass. Inspect its log, lock and explicit completion receipts before relaunching. Coordinator copy processes were left untouched.

Hub access must be restored before completion can be verified. Final reports are saved on the Mac; mirroring these final updates to the hub is blocked. No commits, no NPZ copy back to the Mac, and no private-server APK use.


<!-- C56-PRODUCTION-STATUS -->
2026-10-08T01:44:19.363687+00:00: RUNNING; fleet 1359/1767 units; hub row-validated 1359 units / 63,562 perspectives / 50,847,344 rows; errors 0, illegal labels 0; available-corpus retention 84.4417%.

- 127x01: 185 assigned units done, 44 workers, driver 3342515, wall 1707.5s / CPU 75183.5s; 390.0 units/hour; ETA 0.29 hours.
- 127x03: 266 assigned units done, 64 workers, driver 3366753, wall 1710.0s / CPU 109601.8s; 560.0 units/hour; ETA 0.31 hours.
- 127x04: 97 assigned units done, 32 workers, driver 2224842, wall 1714.7s / CPU 54999.4s; 203.6 units/hour; ETA 0.60 hours.

Status and resume receipts: `qa/fleet-v3b/production-20261008/`; detached labels `c56-v3b-production-20261008-extract` (each node) and the hub supervisor recorded in `supervisor.json`. Full retention/final QA remains pending unless COMPLETE.
<!-- /C56-PRODUCTION-STATUS -->


### Wrapper-overwrite recovery
{"utc": "2026-10-08T01:43:02.053159+00:00", "incident": "fleet_v3b.py externally replaced on 127x01 and 127x04 with original ccab87bb...; collector r3 exit 1 at 01:42:02Z; pools retained their loaded code and continued; all 137 original NPZs remain on each node", "recovery": "unique fleet_v3b_production_worker_20261008.py with same d1f47d39... production wrapper bytes; collector r4 resumes immutable partition and cached hashes; no extraction signalled", "source_wrapper_sha256": "d1f47d39da8a6bce523117c8a6f5d7148efba337d0052bdcfdc18d230938d2f4"}
