# s1s2-r6 — S1 fix for the A1 refusal (2026-10-13T04:19:16Z)

Written 2026-10-13T04:30:54Z by the K4S runner. Copy of s1s2-r5 (Sol full r2 APPROVE) with ONE production change in S1. S2, safe_input and the bootstrap are byte-identical to r5.

## What happened

A1 (GO ea3f7686) ran S1 (`s1_copy_end_sources.py` b987ab9756dd05439f79bd924a0ce31df3c31b24b125a25d8d9cbba31d0fdc65, the approved b987ab97 bytes). The first login (P, 127x03, read-only inspect) returned rc -9 after about 1 s with empty stderr. S1 refused; nothing was copied, the destination was never created, and A1b was not run. Receipt: `end-prep/s1-refusals/S1-REFUSAL-20261013T041916Z-3820611-a2d9b471.json`.

## Cause

`Session._finish` (r5 lines 476–480) ran right after the caller read stdout to EOF:

    if proc.poll() is None:
        proc.kill()
    rc = proc.wait()

OpenSSH closes its stdout when the remote channel closes and only then exits, so on a real login the process is usually still alive at that instant: S1 SIGKILLed it and recorded rc -9. The fake ssh used by the tests kept stdout open until it exited, so the race never showed. Reproduced offline with a fake ssh that closes stdout and then exits (even with no delay): r5 refuses rc -9 every time.

## Fix (S1 only; `S1-r6.diff`)

`_finish` now waits for the login's own exit for at most `EXIT_GRACE = 30` s and kills only if it has not exited by then (the kill then yields rc -9, which still refuses). The hard per-login timeouts (900 s inspect, 3600 s stream) are unchanged; they cover everything up to EOF. Both `run` (logins P, V) and `stream` (login C) go through `_finish`. The remote program, operands, ssh options, gates, size/SHA/inode checks and receipts are unchanged.

New S1 sha256: `16cbbf57f9a9b3cd505ff3ef51d207bac81d0f2c32ddc00d04a5e5f4b030deae`.

## Tests (`tests/test_s1.py`, fake ssh `tests/conftest.py`; `tests-conftest-r6.diff`)

- The fake ssh accepts `FAKE_SSH_LINGER`: it dup2s /dev/null onto fd 1 (so the reader sees EOF), then sleeps before exiting, as OpenSSH does.
- `test_r6_ssh_exiting_after_stdout_eof_is_awaited_six_logins`: a full six-login run with every login lingering 0.5 s after EOF succeeds (20 files, manifest copied).
- `test_r6_exit_within_grace_is_success_unit`: a shell ssh that closes stdout and exits after 0 s or 0.3 s returns rc 0.
- `test_r6_exit_beyond_grace_is_killed_and_refused_unit`: with EXIT_GRACE patched to 0.2 s, a login lingering 5 s is killed and refuses with rc -9.
- Kill check: all three fail against the r5 S1 bytes.

Runner verification (pristine /dev/shm copy with bootstrap-r1 beside it, umask 022): 334 passed (331 + 3) on 3.12 normal and -O, 3.8 normal and -O.

## Scope check

Only S1 manages its own subprocess. Every other component (S1b, S2, S3, S4, S5–S7, S9, S10) runs subprocesses through `safe_input.run_checked`, which waits for the child's exit first and only then joins the output readers, so it does not have this race. A1b (S1b) is therefore unaffected.
