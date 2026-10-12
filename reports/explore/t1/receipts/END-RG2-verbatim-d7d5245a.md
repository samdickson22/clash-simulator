## 2026-10-12 04:03Z: 08 r3 failed with the same race signature; ruling RG2: go to the Amendment 5 path

**What happened.** 08 r3 launched at 03:56:55Z and exited at 04:02:43Z with code 1. The failure is `FleetTechnicalError validity_census` at the first sample after admission, with `foreign_compute` = 1 E4 spawn worker (ppid = the E4 python 1323459, pgid = the wrapper 1323452). That is the same signature as r2. My check was read-only, on the 05 receiver.

**Consequence.** 08 has used both counted attempts (r2, r3). `fleet_pool` therefore blocks the END pool until an outcome-blind amendment is in place.

**Separately, 01 r1** exited 0 at 03:52:14Z. It is still unverified, and its C-d is at 04:13:54Z.

**RG2 ruling:**
1. **T1:** STOP launches.
   - After each C-d, run the approved 753 verifier and apply C8.
   - Assemble 08 r3 under L1 as a counted failed attempt.
   - Verify 01 r1 as planned and keep it as received. Under Amendment 5 it becomes an old-code attempt that is disclosed and never pooled. Don't pool anything.
2. **Amendment 5 path (RG1 step 3) is now active:**
   - Sol code review r1 of `fleet_validity` eae5db3f is running.
   - An independent Opus science/procedure review of `PREREG-SEARCH-TIERS-AMENDMENT-5-DRAFT` and the impact inventory is routed now.
   - Adoption needs both approvals. After that:
     - merge to main;
     - re-pin the END-A3 bundles and runtime with six code SHAs;
     - commit a new release-side roots declaration before the first fixed-code launch;
     - fresh C3 preflights;
     - a fresh reference series on both hosts in the next clean windows (c6387611): 01 after its 06:17:43Z apt-daily, and 08 by its 08:49:07Z apt-daily window or after it.
3. **Every old-code END attempt is disclosed and never pooled:** A6, 01 r1, 08 r1 (exempt under RF1), 08 r2 and 08 r3. This was decided before anyone has seen any reference timing.
4. **K4S END and the Mac/A4 re-staging** wait on the same adoption.
