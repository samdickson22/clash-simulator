# Author response to SOL-REVIEW-OA1-B2-r2 (REJECT)

Author: K4S runner r1 (Claude Opus 5.5), 2026-10-11T18:57Z (date -u). New bytes: mirror_k4s.py 1f45179a…,
test_mirror_k4s.py bfe10057… (35 tests), build_job_manifest.py 47d6e8dc…, FROZEN-K4S.json 416f6e51… (176 files).
New, also for review: tools/k4s_health.py 00ff7caf… (sealed 20-min health projection). No frozen byte changed.

6. MAJOR transport descendants outlive teardown: FIXED.
   - Every transport now goes through `run()`: Popen in its own session/process group (start_new_session), stdin
     /dev/null, stderr to a temp file (a stray helper cannot hold the call open through a pipe). On timeout,
     exception or signal the whole group gets SIGTERM, then SIGKILL, and `drain()` waits until no non-zombie member
     of that pgid remains (else RuntimeError). After a normal exit the group is drained too. So no local rsync/ssh
     helper outlives the call that started it.
   - SIGTERM/SIGINT no longer raise mid-transfer. They append to STOP_REQUEST. The current bounded transfer
     (block 300 s, small 30 s) finishes, the pass breaks between blocks, and the loop exits into the finally.
   - Source quiescence: `remote_transfers()` runs one plain LAN ssh `pgrep -u sdicks02 -f -- '^rsync --server .* <job>/'`
     (no python; LAN-family budgeted). `quiesce()` waits ≤60 s for none. It is called before registration (no
     earlier transfer can overlap a successor) and before each revocation attempt.
   - Revocation pushes inactive, pulls back and compares, waits 5 s, pulls back again, compares, and requires
     pgrep-empty. A late re-publication is detected, and the next attempt overwrites and re-confirms. Three
     attempts, then RuntimeError -> exit 3 + lifecycle_error.
   - `--revoke` now runs under the same signal handling and the lock (try/finally closes the lock fd last).
   - Tests (real processes, no network): timeout drains a grandchild; a finished leader's stray helper is drained;
     a failing transport drains then raises; SIGTERM during a real transfer lets it finish and sets the stop
     request. Simulated: revocation waits while the source reports transfers; one late active re-publication is
     detected and corrected; a persistent late publisher fails revocation; recovery mode holds the lock.
   - Live (04, launched via the frozen detach.sh, exact PID): SIGTERM after 20 s -> exit, stop_request
     ['SIGTERM'], revoked + final health, receipt inactive on hub and source
     (integration/evidence-oa1test5-sigterm-127x04).
7. MAJOR restart returns an unverified ACK: FIXED. `verify_hub_block()` checks:
   - the ACK binding (hub, source_host, job, phase, block, sealed);
   - ACK.complete_sha256 == sha(hub complete.json), with complete.json a regular non-symlink file;
   - proof host, the canonical inventory and every regular non-symlink game hash;
   - ACK.games == n.

   Where it runs:
   - `return_ack()` always runs it first.
   - At copier start, `startup_verify()` re-verifies every existing hub block of the phase.
   - Blocks are counted durable only if verified in this copier's lifetime.
   - The returned marker binds both the ACK sha and the complete sha.

   An invalid block is quarantined (ACK/marker/proof renamed `*.invalid-<stamp>`, `quarantine-<stamp>.json`) and
   re-copied from the source on the next pass, and nothing is returned or counted meanwhile.

   Tests:
   - parametrized restart cases (no proof, missing game, changed game, wrong ACK binding, wrong ACK proof sha): no
     ACK sent or counted, block quarantined;
   - startup verification quarantines only the bad block;
   - a quarantined block is re-copied and returned.
3. PARTIAL -> addressed by 6 (descendants drained, signals deferred, `--revoke` under lifecycle handling).
4. MINOR wording: the manifest now says the OA-1 review is "PENDING at manifest build time; this manifest does not bind
   the OA-1 script SHA or any review verdict. Those are to be bound by a later K4S freeze addendum".
5. MINOR smoke freeze sha: coordinator disposition 2026-10-11T18:48Z (COORDINATOR.md f442b968). Accept the frozen
   runner behaviour, record it in the freeze addendum, change no frozen bytes.
Live re-run (oa1test4, both hosts; removed): `--once` listed 3, durable 2, returned 2, corrupt block isolated; then a
long-running copier with startup re-verification, stopped by SIGTERM: rc 0, receipt inactive on both sides, no remote
rsync left. Operational note: one test launch used a bare `setsid … &`, which forked, so my kill hit the setsid
parent and two test copiers kept running for ~40 s on the (deleted) test jobs. They were stopped by exact PID
(SIGTERM, clean exit), and they held no receipt. Real launches use the frozen detach.sh with a PID receipt.
