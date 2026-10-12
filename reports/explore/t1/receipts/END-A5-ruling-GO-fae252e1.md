
## 2026-10-12 10:29Z: A4 Mac inputs DELIVERED (73d9ac68); T1 GO for R5 seal, registration, R6

The builder finished Phase 3 on 05, using A5 bytes.
- **Selection:**
  - pool of 4,242 rows;
  - packets from 9 games, round-robin;
  - agreement of 1,931 rows plus a 69-row fill;
  - one D7/D8 pass takes about 24 min.
- **Fixture:** 2,125 rows, fingerprint `0de69958…`; conversion PASS.
- **Independent reproduction:** a separate Haiku worker using its own code got identical packets, schedule, agreement, ids, 800 digests and fingerprint.
- **Student reference:** `7a90fa7a…`. The B.6 cross-check against the A5 pooled S forwards (`fe534ec0`) gives 300/300 bit-exact.
- **Mac memory:** 2.88 GiB conservative against the 6 GiB cap.
- **B.7 seal:** `f3b87ce5`.
- **Disclosed:** a wait loop hung for about 1 h of wall time. Results are unaffected.

**GO for T1:**
1. Seal R5 (at fc0d74a6, binding cf3be4dd/041de810 and canonical `<R>` at 1cb46a13) and seal registration with the A4 inputs (73d9ac68, B.7 f3b87ce5).
2. Run the R6 release barrier from `<R>` under e4v3-venv 3.12.12, recording `sys.executable`. It includes the reducer aebb2017 check: the emitted sensitivity ledger must equal the PC4 sidecar except for `utc`.
3. Commit everything, then stop. Open no outcome.

The coordinator then commissions R7, production-packet review r2. Release happens only after R7 clears and the coordinator authorizes it.
