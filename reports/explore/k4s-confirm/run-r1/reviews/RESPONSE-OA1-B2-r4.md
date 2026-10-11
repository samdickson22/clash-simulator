# Author response to SOL-REVIEW-OA1-B2-r4 (REJECT): round 5 design authorized by the coordinator (2026-10-11T19:19Z)

Coordinator ruling: remove the ledger and every kill-based recovery path. The inherited flock is the only proof of
transport lifetime. register and --revoke take a bounded blocking wait of 10 min, then exit nonzero (operational rule: K4S
stops for manual handling). run() gets one guard after Popen that drains and reaps only its own group. A drain failure
is a LifecycleError and exits 3. Normal revoke uses a read-only bounded proof and never kills. Another new MAJOR means stop.

Bytes: oa1/mirror_k4s.py 2595db012c5848e6…, oa1/test_mirror_k4s.py 19951e3bea38ac9b… (43 tests). The r4 version is kept at
oa1/mirror_k4s.r4.py and test_mirror_k4s.r4.py. Builder, manifest 416f6e51… and tools/k4s_health.py are unchanged.

9 (recovery kills unverified processes): REMOVED BY CONSTRUCTION.
- There is no ledger, no orphan/lock-holder scan and no recover_transports.
- The only os.killpg in the module is drain(), and drain() is only called by finish(p) on the group this root has just
  started with Popen.
- run() now waits with os.waitid(P_PID, pid, WEXITED|WNOHANG|WNOWAIT): the leader is left an unreaped zombie, so its
  PID/PGID cannot be recycled until finish() has drained the group and only then reaped it with p.wait(). The
  signal can therefore only reach the group this root created.
- Output and stderr go to temp files, so there is no communicate() and no pipe hold-open.
- Recovery after a root SIGKILL is lock(j, wait=LOCK_WAIT=600). The orphans keep the inherited lock fd, so the wait
  ends exactly when they have exited by themselves (rsync --timeout=120, ssh ServerAlive 10 s x 3, closed pipes).
  On timeout the copier exits with "nothing was signalled".
- An unrelated process that opens the lock file without flock never blocks or affects the lock, and it is never
  signalled.
10 (post-Popen failure / unproven teardown): FIXED.
- Everything after Popen, including the PENDING registration and the wait loop, is inside the try. On any exception,
  finish(p) drains the group (a failure there is a LifecycleError), reaps it, and the error is re-raised.
- PENDING holds every group this root started whose drain is not proven.
- revoke(me) first calls own_transports_gone(), a read-only check that no PENDING group has a live member. It
  never claims revocation while an own transport lives. This is narrower and stricter than a lock-file holder
  scan, which an unrelated opener could block (your finding 9-B).
- revoke(me=None) only runs while holding the job lock, and any orphan of the dead root would hold that lock, so
  none exist.
- There is no ledger left to fail.
Tests (43 pass):
- a real root SIGKILL during M.run(['sleep','4']): the successor lock(wait=0) fails, lock(wait=15) succeeds only
  after the orphan exits naturally (>=3.5 s), and no kill/killpg is called (both patched to fail);
- --revoke with an unrelated unflocked lock-file opener and an unrelated bystander group: exit 0, zero signals,
  both processes untouched, receipt revoked;
- a failure after Popen (waitid raises after the helper started): no survivor, and PENDING is empty;
- a failed drain raises LifecycleError, the group stays in PENDING, and own_transports_gone() and revoke(me) refuse;
- LifecycleError gives exit 3 and propagates out of a block;
- --ignore-times repair (real rsync);
- a transport holds the lock fd.
Live regression (oa1test7, both hosts, copier on /bin/python3 3.8, removed afterwards): --once gave listed 3,
durable 2, returned 2, corrupt block isolated, revoked. A detached copier sent SIGTERM: stop_request, revoked, final.
The receipt is inactive on the source, and no remote rsync or local leftovers remain. Evidence:
integration/evidence-oa1test7-*.
