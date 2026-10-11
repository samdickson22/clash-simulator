# Author response to SOL-REVIEW-OA1-B2-r3 (REJECT) — round 4 authorized by the coordinator

Coordinator 2026-10-11T19:07Z: r4 authorized with fixes (a)–(d) exactly as proposed. If r4 raises a new MAJOR, stop.
Only mirror_k4s.py and its tests changed. build_job_manifest.py, FROZEN-K4S.json (416f6e51…) and tools/k4s_health.py
are unchanged since r3. No frozen byte changed.

6 (and 3), root SIGKILL leaves transports alive and the lock released: fixed by (a) + (b).
(a) Lock-holding transports.
  - Every transport runs as `bash -c '"$@"; rc=$?; exit $rc' k4s-oa1-holder <cmd…>` in its own session, with
    `pass_fds=(job-lock fd,)`. The holder bash, and the rsync it forks, inherit the open file description of the job
    flock. The flock therefore stays held while any transport process of a dead root lives. A successor `lock()`
    fails ("another OA-1 copier (or an orphaned transport of one) holds the job lock").
  - Crash-safe ledger: `<job>/oa1-transports.jsonl` gets a `start` record (pgid, leader start_ticks, root pid, cmd
    head; append + fsync) and a `done` record after drain.
  - The pgid is only known after Popen, so a root killed between Popen and the ledger write leaves an unledgered
    holder. `lock_holders()` closes that window: it scans `/proc/*/fd` (own uid) for processes holding the job-lock
    file.
  - `recover_transports()` drains the union of live ledger groups and lock-holder groups. It refuses
    (AssertionError) if a live `mirror_k4s.py` root holds the lock, and raises LifecycleError if anything survives.
  - `--revoke`: if the receipt's root is dead, it recovers first (orphans would otherwise block the lock), then
    takes the lock and revokes, and `revoke(me=None)` recovers again under the lock.
  - `register()` refuses while ledger orphans or foreign lock holders exist.
  - `rsync --timeout=120` also bounds an orphaned transfer's I/O stall.
(b) `drain()` failure raises `LifecycleError`. This is not caught as a block or listing error. It propagates out of
    the pass, sets status 3 with `lifecycle_error` in health, and the copier still attempts ownership-checked
    verified revocation.
(c) MINOR 8: every block pull uses `BLOCK_PULL=['--no-links','--ignore-times']`.
(d) Tests (43 pass; real processes, no network):
  - root SIGKILL during an in-flight `run(['sleep','60'])`: the orphan is in the ledger and the successor `lock()`
    fails; `recover_transports()` drains it; the lock is then available and no holder remains;
  - kill between Popen and the ledger write (holder spawned via pass_fds and never ledgered): found through the lock
    fd and drained;
  - recovery refuses while a live copier root holds the lock;
  - register refuses with orphans;
  - LifecycleError from listing gives exit 3, lifecycle_error recorded, and the receipt still revoked and verified;
  - LifecycleError inside a block propagates out of one_pass;
  - real local rsync repair: same size and mtime, different bytes. The control without --ignore-times skips it;
    BLOCK_PULL repairs it;
  - a transport runs under the lock-holding holder, with ledger start/done.
Live regression (oa1test6, both hosts, removed afterwards): `--once` gave listed 3, durable 2, returned 2, corrupt
block isolated, revoked. A detached long copier got SIGTERM: stop_request, revoked, final. Ledger 33 start / 33 done,
receipt inactive on the source, no remote rsync left, no local leftovers. Evidence: `integration/evidence-oa1test6-*`.
