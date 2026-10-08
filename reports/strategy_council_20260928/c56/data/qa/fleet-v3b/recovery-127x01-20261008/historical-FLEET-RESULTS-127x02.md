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
