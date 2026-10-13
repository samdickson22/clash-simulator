# FSC progress (U3/U4, exploration, NEVER ADOPTABLE)

Resume from here after any session restart. Hosts: 127x03 (`fsc-03-20261013`) and 127x04 (`fsc-04-20261013`).
Mirror on 05: `/mpac/sdicks02/jobs/clasher/fsc-mirror-20261013/`.

## State
- [x] Offline preparation on 05: harness diff, configs, worklists, seed pick and audit (origin/main export), reducer,
      host session, LAN copy, tests.
- [ ] Coordinator relays the K4S runner's answer and gives GO. **No contact with 03/04 before GO.**
- [ ] 03 launch session (smoke, STOP test, reporting).
- [ ] 04 launch session (LAN copy from 03, smoke, STOP test, reporting). Only while 03 is still in contact.
- [ ] STOP sessions (03, 04), then no contact.
- [ ] Reduce on 05 and write RESULTS.md.

## Log
- 2026-10-13T01:33Z: prep committed **9f69df0b9** (pushed via temp index; secret scan clean). Bundle built at
  /mpac/sdicks02/scratch/fsc-bundle-9f69df0b9 (MANIFEST sha256 1f2778f04d353abc…, 36 files). Seed audit PASS on
  export of origin/main ffc01179c (seed-audit.json 470de7ba…). Checklist sent to the coordinator; holding for the K4S
  answer + GO. No host contact.
- 2026-10-13T01:48Z: Sol r1 on the host scripts: REQUEST_CHANGES (eaf0e6be). The coordinator authorized the 05 mirror (F6) and accepted the
  supervisor's own-PGID signals (F8). r2 fixes F1–F5, F7, F9 and F10 (REVIEW-RESPONSE-r1.md); offline tests and shellcheck
  pass. Committed for Sol r2. No host contact.
- 2026-10-13T01:54Z: the K4S runner cleared U3/U4 with seven binding conditions; all are built into r2 (prefix moved to
  /mpac/sdicks02/jobs-fsc, top-ups dropped, STOP_AT ≤ 04:50Z, memory guards, STOP proof, stop_runner on 05). Tests and
  shellcheck pass. Committing the final r2 for Sol (PR-1 last round). No host contact.
- 2026-10-13T02:19Z: the coordinator raised the STOP_AT cap to 07:30Z (K4S A1 never before STOP + 1 h). Committed **d59cce54a**: DEADLINE
  04:50Z → 07:30Z in host_session.sh, session.sh and stop_runner.sh; the test's over-cap example moved to 08:30Z. Bundle
  MANIFEST 661fcb92…. Primary-only worklists kept. Holding for Sol r2 (report: coordinator-notes/SOL-REVIEW-FSC-HOST-SCRIPTS-r2.md) and GO.
- 2026-10-13T02:30Z: Sol r2 (31097eec) REQUEST_CHANGES on R2-1 (stop-history reads), R2-2 (console false zero) and R2-3 (cap on every
  phase), plus a single cap constant. All fixed (single cap in fsc/DEADLINE = 07:30Z). The coordinator verifies the diff
  against 3dc9ab25 directly (PR-1 final round). No host contact.
- 2026-10-13T02:51:46Z: GO (COORDINATOR 19047ce7). Stop runner armed on 05: PID 2050067 (own session; sleep child 2050100),
  AT 07:30:00Z for 127x03 and 127x04 (receipt fsc-sessions/stop-runner.receipt.json).
- 2026-10-13T02:52:03Z: 03 launch session (05 wrapper PID 2082227). The bootstrap created /mpac/sdicks02/jobs-fsc and
  fsc-03-20261013/bundle (manifest verified). The console check was clean (0). **Preflight FAILED at 02:52:20Z, __RC=91:**
  a persistent foreign sdicks02 process, the v4 validation cache service (fleet_run.sh PGID 2180934, python
  v4-cache-renewal-r2/validation_cache_service_renewal_v4.py, taskset 48-63,112-127). Nothing was staged or started on 03;
  the prefix holds only bundle/. 04 was not launched (the GO sequence needs 03 at __RC=0). Halted; reported to the
  coordinator; no relaunch without approval.
- 2026-10-13T03:12Z: GO 5f1a28be (commit c7df6fac, MANIFEST 2f16b70d). The attempt-1 logs moved to fsc-sessions/attempt1-0252Z/.
  Old runner 2050067 (identity checked) killed by exact PID, then its sleep child 2050100; `ps -p` showed none left.
  New runner: PID 239670 (sleep child 239707), started 03:12:30Z, AT 07:30:00Z, hosts 03 and 04 (fsc-sessions/stop-runner.receipt.json).
- 2026-10-13T03:16:18Z: **127x03 reporting launched** (__RC=0), prefix /mpac/sdicks02/jobs-fsc/fsc-03-20261013b.
  - FSC-1 exempt (resident ticks 7603 → 7603).
  - Staged 424 MB, all pins verified.
  - Smoke passed: 8 blocks / 16 games in 101 s.
  - STOP test passed: owned_STOP, exit 1.8 s after STOP, 4 blocks interrupted, 0 left alive.
  - rep03: supervisor PID/PGID 3244110, child PGID 3244144 (13 processes), workers 12, stop-at 07:30:00Z.
  - Guards: 14 processes at oom_score_adj 1000 / RLIMIT_AS 8 GiB.
- 2026-10-13T03:20:16Z: **127x04 reporting launched** (__RC=0), prefix /mpac/sdicks02/jobs-fsc/fsc-04-20261013.
  - Console users 0, no foreign processes (no resident service found on 04).
  - LAN copy: 2,019 files, 0 deletions; native (458 files) and inputs equal at 03 and 04.
  - Smoke passed: 16 games in 101 s.
  - STOP test passed: 1.8 s, 4 blocks interrupted, 0 left alive.
  - rep04: supervisor PID/PGID 2301414, child PGID 2301450 (13 processes), workers 12, stop-at 07:30:00Z.
  - Guards: 14 processes OK.
- 2026-10-13T05:21Z: progress check (one session per host).
  - 03 rep03: 1,225 blocks / 2,451 games, 12 workers live, PSS 3.5 GiB, MemAvailable 119 GiB, console users 0.
  - 04 rep04: 1,158 blocks / 2,322 games, 12 workers live, PSS 3.8 GiB, console users 0.
  - Projection: 04 finishes wl-04 around 06:00Z, and 03 finishes wl-03 around 07:15–07:30Z.
- 2026-10-13T05:25Z: epoch-2 extension proposal committed **9aa1cce6** (MANIFEST c6574764…), not GO.
  - Prepared in an isolated scratch copy; the live worktree stays at c7df6fac bytes for the armed 07:30Z runner.
  - The run dir for epoch 2 is /mpac/sdicks02/scratch/fsc-e2-run-9aa1cce6d.
