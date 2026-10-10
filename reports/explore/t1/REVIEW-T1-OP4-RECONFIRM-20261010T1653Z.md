# T1 OP-4 re-confirmation: 26151cc6

**Verdict: CONFIRM.** B1 is fixed, N2 is implemented as directed, and N5 is re-pinned. Nothing blocks. Two new residual escape patterns, R1 and R2, plus one over-count, R3, are disclosed below. The coordinator may want to harden R1 later, but none of them gates this candidate.

- Reviewer: independent T1 reviewer, running on 127x05 with git and local files only. I made no ssh connection to 01, 03, 04 or 08.
- Candidate: `26151cc69ac7d85448e421d51d82d2542d87e153`.
- Prior round: `REVIEW-T1-OP4-CONFIRM-20261010T1642Z.md` (9ea3138b), NOT_CONFIRMED on cb1b9f12.
- Reporting games: 0. Outcomes stay sealed.

## 1. B1 (reaped-child CPU): FIXED

**Code.**
- `host_audit.processes()` now records `child_cpu_ticks = cutime + cstime` (stat fields 16–17).
- `ssh_budget.total_ticks` = self + reaped. It is used for the baselines in `sample`, `begin` and `update`, and for the per-generation increment.
- Every `ssh_budget`-tagged row is charged its combined delta. That covers the authenticated sshd root and every descendant.
- Block receipts and `ssh-family-occurrences.jsonl` report the self and reaped counters separately.

**My live probe, re-run on 05.**
- The probe is the same as last round: real `host_audit.processes()` and real `ssh_budget` on real `/proc`, with a synthetic LAN `sshd: sdicks02@notty` root.
- It ran on one pinned core, nice 19, with a 62-iteration block (~73 s) and the sample cap evaluated every census.
- The script is `/mpac/sdicks02/tmp/op4rc/probe.py`. It is not committed.

| Workload (each child ~47 ms of `sh` busy loop) | True core use (`/proc/stat` cpuN) | Metered | Flag | Stop |
|---|---|---|---|---|
| bash loop that waits on its children (the B1 case) | 0.999 | **0.946** (6922 ticks; ~110 per 1 s sample) | yes | **sample cap at 1.2 s** |
| cb1b9f12, same probe, last round | 0.46 | 0.0007 | no | no |

The B1 escape is closed. Constant parent utime with rising cutime is now charged on both the sample path and the block path, and that triggers the flag and the stop.

**The double-count can only over-meter (fail-safe): CONFIRMED.**
- utime, stime, cutime and cstime are all monotonic for a fixed generation, and `increment` clamps at `max(0, ·)`. The new meter therefore equals the old meter plus a non-negative term, for every row and every census.
- A repeated census with unchanged counters charges 0 (tested).
- No path subtracts or offsets CPU.
- The one magnitude caveat is R3.

## 2. N2 (average-stop floor): CORRECT

- `finish()` gives `stop = elapsed >= 60 and ticks*50 > hz*T`. Exactly 2% at 60 s passes, and 59.999 s never stops (tested).
- The `interfered` flag (`ticks*200 > hz*T`) is still computed from block start against the actual elapsed time, with no floor.
- `sample()`'s 25% cap is untouched and runs on every census, whatever the block age. `stop_reason` order is unchanged: console, foreign, foreign_active, sample, average.
- The live probe stopped on the sample cap at 1.2 s.
- Load between 2% and 25% of a core is never hidden. Before 60 s it is flagged; from 60 s on it is flagged and stopped. In blocks shorter than 60 s it is flagged only, which is the directed design.

## 3. Scope: PASS

- `git diff 9ea3138b 26151cc6` touches only these files:
  - code: `host_audit.py` (one field), `ssh_budget.py`;
  - tests: `test_op4.py`, which adds 4 tests;
  - manifest: `FROZEN-T1.json`;
  - docs and receipts: `OP4-T1.md`, `PROGRESS-T1.md`, `receipts/op4-unit-tests.json`.
- `cb1b9f12..26151cc6` additionally contains only 3d6e2a56, which adds one doc (`END-CONTRACT-COMPATIBILITY-20261010.md`), and my 9ea3138b review.
- These are all byte-unchanged: the runner, reducer, seeds, decks, `perception_confirmation.py` (OP-2), `owned_supervisor.py` (OP-3), `supervise.py` and `ssh_transport.py` since cb1b, and `test_op1`/`test_op2`/`test_op3`.

**N5 re-pin: PASS.**
- All 111 `FROZEN-T1.json` hashes match the bytes at 26151cc6 (0 mismatches).
- The manifest adds `ssh_budget.py`, `test_op4.py`, `OP4-T1.md`, the op4 receipt and the prior review.
- `operational_delta_op4.verdict` is `AWAITING_RECONFIRMATION`, so the candidate does not admit itself.

## 4. Tests: PASS

I ran `test_op1.py test_op2.py test_op3.py test_op4.py` from a detached worktree at 26151cc6 with `/mpac/sdicks02/venvs/t1-verifier` (CPython 3.12.12) under nice 10: **46 passed** in 3.2 s, which matches the claimed 46/46. That count includes the author's real-/proc short-child test.

## Residual disclosures (non-blocking)

**R1. Auto-reaped children are unmetered.**
- If a budgeted parent sets `SIGCHLD` to `SIG_IGN` or `SA_NOCLDWAIT`, the kernel reaps its children without `wait`, so their CPU never reaches the parent's cutime.
- Live probe: a Python parent with `SIG_IGN` forking ~47 ms `sh` children used **0.69 core true, metered 0.002**, with no flag and no stop.
- Before OP-4, the same parent (`python` under sshd) would have hit `foreign_compute`, so OP-4 opens this.
- It is non-blocking because it needs a deliberately unusual parent. Common patterns all `wait` and are now metered: shell loops, make, xargs, Python `subprocess`.
- Suggested hardening, not required: a host-level check of unattributed CPU, comparing `/proc/stat` busy time on non-slot cores with the sum of attributed deltas.

**R2. Orphaned short-lived children are unmetered.**
- Children reparented to init (for example `( cmd & )` in a loop) lose the tag. Their CPU goes to init's cutime.
- They also miss the identity rules unless they are listed compilers or interpreters, or are seen alive at 2 censuses using more than 0.1 s.
- Live probe: 0.64 core true, metered 0.024. That was flagged, and stopped at 60 s only because of the parent's own fork overhead.
- It is non-blocking for the same reason as R1: the pattern is rare. The same hardening would close it.

**R3. The over-count includes CPU from before the block.**
- When a tagged child that has lived a long time is reaped mid-block, its parent's cutime jumps by the child's whole lifetime CPU, including CPU used before the block.
- Synthetic check: a child with 300 pre-block ticks exits, and the block is charged 300 ticks, so the sample cap stops at once.
- In practice, a LAN session child that used more than 0.25 s of CPU in its lifetime (for example `rsync --server`) and is reaped by a tagged parent that is still visible at the next census will stop the host.
- This fails closed, and the race is narrow because sshd usually exits right after its child. Still, `OP4-T1.md` says only "observed alive and subsequently reaped may be charged again", and it should say that the charge can include pre-block lifetime CPU.
- Optional refinement: subtract the last-seen total of each disappeared child from its reaper's cutime delta, with a floor of 0.

The earlier N1, N3, N4 and N6 stand as disclosed in `OP4-T1.md`.

## Items for staging

None block. Before staging, the coordinator should note R1–R3 and flip `operational_delta_op4.verdict` at admission.
