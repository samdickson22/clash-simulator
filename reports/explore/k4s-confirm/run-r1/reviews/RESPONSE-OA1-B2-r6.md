# Author response to SOL-REVIEW-OA1-B2-r6 (REJECT on MAJOR 12): S1 "no separate recovery mode", approved 2026-10-11T19:40Z

Coordinator ruling: delete `--revoke` and `revoke(me=None)` entirely, not patch them. After a crash, SIGKILL or power
loss, recovery is simply a normal copier start:
- it waits ≤10 min on the inherited job lock (timeout means K4S stops for manual handling);
- then register() (dead prior receipt plus source quiescence);
- then startup_verify() over every hub block;
- all inside the single main() path with the exit-3 lifecycle boundary.
r7 covers the deletion, a real-process SIGKILL→restart test, and a check that no code path references the
revocation mode. If r7 raises any new MAJOR, stop.

Change r6 → r7 (reviews/r6-to-r7.diff):
- `revoke(j, host, me)`: `me` is required. The recovery branch is gone.
- main(): `--phase` is required, and there is no `--revoke` argument or branch. The lock wait (LOCK_WAIT=600) applies
  to every start.
- main(): any non-lifecycle fatal exception (e.g. a failed registration push or startup verification I/O) now gives
  exit 2 with `fatal_error` in health, instead of a traceback. Revocation of its own receipt is still attempted in
  the finally. A lifecycle failure stays exit 3; a revocation failure is exit 3 with both messages.
- Docstrings updated. Nothing else changed: finish/drain/PENDING/run/verify/quarantine/ACK return are byte-identical
  in logic.
Tests (47 pass; the r6 recovery-mode tests were removed):
- test_normal_restart_after_root_sigkill_waits_reregisters_and_never_signals:
  - a real child root holds the lock, starts a real transport, and is SIGKILLed while the transport is in flight;
  - an unflocked lock-file opener and a bystander group are also present;
  - a normal `main --phase smoke --once` waits until the orphan exits by itself (≥3.5 s), re-registers over the
    dead receipt, and exits 0;
  - the source receipt is inactive with the new identity;
  - os.kill is forbidden, and os.killpg is allowed only for the restart's own PENDING groups; nothing was signalled;
  - the opener and bystander are untouched.
- test_lock_timeout_is_a_stop_not_a_kill: a held lock gives SystemExit "… nothing was signalled".
- test_fatal_non_lifecycle_error_exits_2_with_health: a registration push failure gives exit 2 (or 3 if revocation
  also fails), with fatal_error in health and revoked=false.
- test_no_code_path_references_a_revocation_mode: no `--revoke`, no `revoke(me=None)`, `me` is required, and argparse
  rejects `--revoke`.
