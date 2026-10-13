# INTEGRATION-AUDIT-r1 PROGRESS (127x05)
2026-10-13T05:09:51Z START audit; scratch /dev/shm/ia-r1
2026-10-13T05:16:10Z SHA256SUMS OK for all 6 approved dirs; scratch copies in /dev/shm/ia-r1/code; AUDIT-ONLY patch IA-P1 (S4 dict files) at /dev/shm/ia-r1/code/b3-r5 (diff /dev/shm/ia-r1/AUDIT-PATCH-IA-P1.diff)
2026-10-13T05:16:10Z S4(IA-P1) dry-run: all 6 requests rc=0 (03 67 files, 04 66). Real 03-pf00 assembly started -> tempdir in /dev/shm/ia-r1/BUNDLE_TMP
2026-10-13T05:16:10Z NEW candidate: runtime lacks reports/explore/k4s-confirm/DELTA-MANIFEST.json, read by frozen end_reference.py:127 (k4s_pins)
2026-10-13T05:19:25Z S4(IA-P1) real 03-pf00 -> /tmp/ia-r1-bundles-DQ3CBz (manifest ca4ce6ef, receipt 15126b74447d6a2fcfdad29d79f02c82bff7bd8c4465ae6567605e7f4034533c); S10 Run A to fake 127x03 starting
2026-10-13T05:23:07Z S10 Run A fake 127x03 OK (record deb837a0...); runtime at <base>/runtime/runtime-98566c032d0b (B2 reproduced). S9 equivalence X_ok rc0, X_rc6 rc2 (diff must be END-JOB only). Frozen end_evidence/end_job/producer_claim OK on scratch clone at X_ok
2026-10-13T05:32:22Z S5 on fake 03: v1 fails pre_import_pins (B2), v2 (B2 sim) fails SD1 missing (B3), v3 (B2+B3/B5 sim) passes all S5 checks to frozen_identity (stops on stub native). Wrapper+push+verify-received OK. S7 preflight+END gates: only env artifacts (no launch).
2026-10-13T05:36:11Z runlog copied to /mpac/sdicks02/k4s-runner/run-r1/end-staging/INTEGRATION-AUDIT-r1/runlog
2026-10-13T05:38:44Z cleanup: removed /tmp/ia-r1-bundles-*, /tmp/ia-r1-hosts-*, /tmp/ia-r1-rec-*, /dev/shm/ia-r1 (records copied to runlog/s10-records)
2026-10-13T05:38:56Z DONE. approved dirs re-verified OK; no new files in runtime/repo-full; REPORT.md sha256 0d709b5becc8cc99ccffed08ad9532d05979b4461ea29e530aa557ef6deab6f6
