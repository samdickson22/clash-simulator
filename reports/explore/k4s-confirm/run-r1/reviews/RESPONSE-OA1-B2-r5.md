# Author response to SOL-REVIEW-OA1-B2-r5 (REJECT on MAJOR 11): narrow round 6 authorized by the coordinator (2026-10-11T19:32Z)

Scope, per the coordinator: only the finish() change and its fault-injection tests. Nothing else changes.

Change (mirror_k4s.py r5 -> r6; full diff in reviews/r5-to-r6.diff):
- finish(p) now runs `drain(p.pid)` then `p.wait(timeout=5)` inside one guard.
  - A LifecycleError is re-raised as is. Any other exception (killpg OSError such as EPERM, /proc enumeration
    OSError, a reap timeout) becomes `LifecycleError('transport group <pg> cleanup failed: …')` with `from e`, so
    the cause is preserved.
  - `PENDING.discard(p.pid)` runs only after both the drain and the reap have completed. On any failure the group
    stays PENDING, and own_transports_gone() / revoke(me) refuse while it lives.
- main() health on a revocation failure that follows a lifecycle error now keeps both messages and sets
  revoked=false. Before, the second message overwrote the first.
Unchanged:
- run(): waitid(WNOWAIT), the guard after Popen, PENDING.add inside the try.
- drain(): kills only the group this root started.
- one_pass(): ERRORS doesn't include LifecycleError, so it propagates.
- Everything else, including the manifest (416f6e51), the builder and k4s_health.py.
New tests (47 pass), using real local process groups and fault injection:
- test_killpg_error_is_lifecycle_and_keeps_pending: killpg EPERM on the run's own group through the real run().
  It raises LifecycleError with a PermissionError cause; the group stays alive and in PENDING; own_transports_gone() refuses.
- test_proc_enumeration_error_is_lifecycle: group_members raises OSError, so the real run() raises LifecycleError
  and the group stays PENDING.
- test_cleanup_failure_stops_the_pass_before_any_next_transport: real one_pass() with two blocks, where block 1's
  transport hits killpg EPERM. LifecycleError propagates and block 2's transport is never started.
- test_cleanup_failure_exits_3_with_lifecycle_health_and_no_false_revocation: real main() whose listing transport
  hits killpg EPERM. It exits 3. Health lifecycle_error contains the cleanup failure and the refused revocation
  ("own transport groups still alive"), with revoked=false. The source receipt stays active (not claimed revoked).
