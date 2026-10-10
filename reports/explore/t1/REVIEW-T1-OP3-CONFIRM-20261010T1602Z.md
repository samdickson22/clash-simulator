# T1 OP-3 fast confirmation (9cd518d3)

- **Reviewer:** independent T1 reviewer, on 127x05. I used git and 05-local files only, with no ssh to 01, 03 or 08.
- **Candidate:** `9cd518d3426fb47ce9b61dacabd5dce1ee94e284`.
- **Base:** OP-2 `78c9bd5b`, which was confirmed in 00e3d6d3.
- **Packet:** `/mpac/sdicks02/jobs/clasher/t1-20261010-r1/review/9cd518d3…/` on 05.
- **UTC:** 2026-10-10T16:02Z.

## Verdict: **CONFIRM** (ownership safety; OK to stage for qualification and fresh smoke)

One operational defect, B1 below, will make the **reporting and replacement launches abort** if they reuse the smoke job directory. It fails closed and cannot admit anything foreign, but it needs a further small delta before reporting can start. I recommend folding that delta in now, before qualification, so the hosts aren't qualified twice.

## 1. Scope: only guard ownership, tests and receipts change

From `git diff --name-only 78c9bd5b 9cd518d3`:

- **Code:** only `host_audit.py` (`own_process`, +4/−1), the new `owned_supervisor.py` (60 lines), `supervise.py` (+3: `pin_supervisor` before admission and `add_worker` after each `Popen`), `qualify.sh` (adds `test_op3.py` to the test list) and the new `test_op3.py`.
- **Everything else:** docs (OP3-T1.md, PROGRESS-T1.md), receipts, the OP-2 review file, a COORDINATOR.md line, and FROZEN-T1.json. The FROZEN-T1.json change comes from 07b964fe (OP-2 manifest admission); 9cd518d3 itself doesn't touch it.
- **Nothing scientific changes:** no runner, reducer, plan, decks, seeds, schedule, barrier or health files differ.
- **OP-2 is byte-identical to 78c9bd5b:** `perception_confirmation.py`, `ssh_transport.py`, `idle_services.py`, `system_bus.py`, `test_op1.py`, `test_op2.py`, `OP2-T1.md` and `op2-unit-tests.json` show no diff.
- **16a168c2 is absent:** its `perception_confirmation.py` and `test_op2.py` edits aren't in the candidate. Its 20-test receipt is kept only as `op2-unadmitted-16a168c2-unit-tests.json`.
- **Receipt hashes match git:** the `op3-unit-tests.json` source hashes match the git blobs for host_audit a7de6c3b, owned_supervisor fcd7aac9, supervise f1da5079, qualify.sh 7406bbe8 and test_op3 27a6d351.

## 2. The fast path cannot admit the forbidden cases

`own_process` now returns True early only when `str(j) in cmd` **and** `owned_supervisor.member(j,row)` holds. `member` checks the following, in order:

- **Gate 1:** the receipt exists and its `job` equals `j`.
- **Gate 2:** the row UID equals the root UID.
- **Gate 3:** the live root matches the recorded **pid, pgid, start_ticks, uid, cmdline SHA and exe**. If the root has died, been reused or changed in any way, every row fails.
- **Branches after the gates:**
  - **The root's own row** must match exactly.
  - **Any other row** is admitted if its pgid is the root's pgid or its ppid is the root's pid. Both are sound: the root has stayed alive and identical since admission, so it held that PID and PGID when the row was captured.
  - **Registered worker groups:**
    - If the leader is still alive, its identity must equal the recorded pid, pgid, start and uid.
    - If the leader has exited, only the leader's own captured row passes, and only when pid, pgid, start_ticks and uid all match.

| Case | Result | Evidence |
|---|---|---|
| Same-UID process with spoofed exact CMD, foreign parent and PGID (exited) | Denied | test_op3 #3; **live e2e on 05** (double-forked stranger, ppid 1, own PGID): `own_process=False`, `member=False`, listed by `foreign_compute` |
| Real owned worker that exits before the cwd read | Admitted | **live e2e on 05**: real `pin`, `add_worker` and a `start_new_session` child; `own_process=True` after exit; not in `foreign_compute` |
| Root PID reused or root generation changed (start, exe, cmdline) | Denied | test_op3 #5; probes `root_dead`, `root_exe_changed`, `root_cmd_changed`, `root_row_wrong_generation` |
| Worker leader PID reused (exited, start differs) | Denied | probe `leader_pid_reuse_exited`; e2e `worker_reused_start` (foreign ppid) = False |
| Worker leader still live but reused (start differs) | Denied | test_op3 #6; probe `leader_reused_live` |
| Non-leader in a worker PGID after the leader exited | Denied (falls to strict cwd) | probes `leader_gone_nonleader_member`, `leader_gone_child_of_leader`; e2e `stranger_in_worker_pgid_leader_gone` = False |
| Other UID, receipt for another job, no receipt | Denied | probes `uid_mismatch`, `receipt_job_mismatch`, `no_receipt`; e2e `worker_other_uid` |
| In-tree process whose CMD doesn't match | Denied | probe `unmatched_cmd_in_tree` (condition (a) is still required) |

- **No CMD-only exit exception exists.** The cwd fallback now uses `resolve(strict=True)`, so a missing or `(deleted)` cwd returns False. Before, a non-strict resolve could quietly reach the CMD clause. This change is strictly narrower.
- **`pin` refuses to overwrite an existing receipt.** `add_worker` requires the child to be its own PGID leader, a direct child of the verified root, with the same UID.
- **The observed failure fits the fast path:** on 01, PID/PGID 293675 had ppid 293613. `taskset` and `runtime.sh` exec in place, so the Popen PID is the run.py PID, which is the ppid==root branch.

## 3. Tests run on 05

I ran the candidate tree from `git archive 9cd518d3` with uv CPython 3.12.12, under nice 10:

- **`test_op1.py`, `test_op2.py`, `test_op3.py`:** **26 passed**, which matches the packet's 26/26.
- **Reviewer probes:** **13/13 pass**. They're in `/tmp/op3probe/test_probe.py` on 05 and are not committed.
- **Live end-to-end:** `/tmp/op3probe/e2e.py` ran as a real setsid root against real `/proc`. Every result is as expected, as shown in the table.

## Findings

- **B1 (blocks reporting; fails closed).** `pin` asserts that `j/owned-supervisor-admission.json` doesn't exist yet. But `supervise.py` runs smoke, then reporting, then replacement with the same `--job j`: reporting needs `j/SMOKE-PASS`, and `launch.sh` passes the same `$job`.
  - **What happens:** the reporting supervisor raises `AssertionError` at `pin`, before admission and before any block starts.
  - **Confirmed live:** a second `pin` in the same job gave `REFUSED: supervisor admission cannot be silently refreshed`.
  - **Suggested fix:** key the receipt by namespace (phase, plus attempt for replacement), e.g. `owned-supervisor-admission-{namespace}.json`, and have `member` read only the running supervisor's namespace. Keep the no-overwrite rule within each namespace. The change touches `pin`, `add_worker` and `member`, needs a test, and is reviewable in minutes.
  - **What not to do:** don't delete or rename the receipt by hand to work around it.
- **N1 (staging step, not a defect).** FROZEN-T1.json at 9cd518d3 still pins the 78c9bd5b bytes of `host_audit.py`, `qualify.sh` and `supervise.py`, and it doesn't list `owned_supervisor.py`, `test_op3.py` or `OP3-T1.md`.
  - The manifest must be re-pinned to the confirmed bytes, plus this review, before staging.
  - `owned_supervisor.py` is already covered by the qualification inventory glob (`t1/*.py`).
- **N2 (inherited; not tightened by OP-3).** A **live** process with a readable cwd and `str(j)` in its CMD is still admitted with no tree check. That is the unchanged OP-1 rule, and it's limited to the same UID because other UIDs' cwd is EACCES. The coordinator's tree requirement covers only exited or cwd-unreadable processes, which this candidate fully enforces.
- **N3 (trust model).** The admission receipt is trusted on filesystem permissions, the same as every other T1 receipt. A same-UID process that can write `j/` could forge a receipt naming itself as root. This is outside the threat model and not new.
- **N4 (fail-closed).** Grandchildren in a worker PGID whose leader has exited fall back to the strict cwd path. That can only cause a false-foreign stop, never a false admission.

Reporting remains 0/SEALED; this review starts nothing.
