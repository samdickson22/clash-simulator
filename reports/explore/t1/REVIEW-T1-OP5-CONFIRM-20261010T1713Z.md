# T1 OP-5 fast confirmation: a697647b (seed b2f9e25e)

**Verdict: CONFIRM**

- **Reviewer:** independent T1 reviewer, reporting to coordinator 0523ae6f.
- **Where:** 127x05 only, using git, the job packet and the local job tree; no ssh to 01, 03, 04 or 08.
- **Candidate:** `a697647b6c607bc46428f6e014ff5c5cdb4fae45` on top of `a6f145ac`. The source receipt is committed separately as `b2f9e25e`; its blob SHA is `167cbe71…8838`.

## 1. The receipt is genuine: PASS

`receipts/op5-parent-source-127x03.json` restates evidence that was committed before OP-5 existed. I found nothing that was fabricated afterwards.

- **Source file:** the receipt cites `smoke-after-op3-r4/diagnosis/diagnostic-ssh-127x03.json` with SHA `d9cbd2b9…f057`.
  - That SHA was already pinned in `receipts/excluded-smoke-op3-r4.json`, committed in d831f234 at 09:31 PDT, which is before the OP-5 commits at 10:06 and 10:09.
  - The copy on 05 still hashes to `d9cbd2b9…` and has mtime 09:19 PDT. Its `utc` field is 16:19:11Z, the same as the receipt's `captured_at_utc`.
- **Sample contents:** in sample `records[0]`, row 0 (the sshd parent) and row 1 (the reader child, pid 16002) equal the receipt's `parent_snapshot` and `child_snapshot` field for field. The only difference is the omitted `affinity` list.
  - The child carries `ssh_parent_snapshot=[776414,137136686,3822945,4c329d01…]` and `SSH_CONNECTION=129.65.221.14 35798 129.65.221.13 22`. That is the authenticated child-to-parent binding that seeds the source.
- **Earlier evidence agrees:**
  - `OP2-T1.md`, committed in 78c9bd5b at 08:37, already names parent 776414, start 137136686, UID 3822945 and the same connection string.
  - All 21 children in `foreign-ssh-776414-children.json` show `ppid=776414` and that same connection, including the same source port, 35798.
- **The parent at r5 is the same generation:** the r5 03 `stop-reason-127x03.json` `foreign_active` row (childless, `ssh_connection_snapshot=null`) has the same PID, start ticks, UID, cmdline SHA (`4c329d01…`) and PPID/PGID (776335/776335). Its CPU ticks grew from 242323 to 251715, which is consistent with one long-lived process.
- **Pinning:** the blob in b2f9e25e, the HEAD file and the `FROZEN-T1.json` `files` entry and `parent_source_seeds` binding all hash to `167cbe71…`.

## 2. The seed applies only on an exact generation match: PASS

`parent_source_seed.admit` is called once, from `host_audit.admission`, before the first census, and only when no console user is present.

- **Pinning checks.** Each binding must:
  - have a relative path under `reports/explore/t1/receipts/`;
  - be a 40-hex commit with a 64-hex SHA;
  - be pinned by the job manifest's `files`;
  - match the on-disk SHA;
  - be byte-identical to `git show <commit>:<path>`.
- **Field checks.** `matching` requires:
  - the v1 schema;
  - host 127x03, which must equal the current hostname;
  - source `129.65.221.14`, with a 4-field connection to port 22;
  - an `authenticated()` sshd row (`sshd: sdicks02@notty`, the current UID), and UID 3822945;
  - equality on all six of pid, start_ticks, uid, cmdline_sha256, ppid and pgid.
- **Conflicts:** an existing different or `None` (conflict) source for the key is never overwritten.
- **Persistence:** `supervise.py` runs admission and census in the same process, so the in-memory seed reaches the run. `Families.apply` prunes it as soon as that parent generation disappears. A reused PID with a new start time does not match.
- **My probes,** run outside the tests from the detached worktree:
  - The real receipt against the real r5 row gives `True`. Changing any one of the six fields, or `cmd`, gives `False`.
  - Seed, then a child with a conflicting `SSH_CONNECTION`: the source becomes `None` and the child gets no budget, so it falls back to identity.
  - A seed on a childless apply survives; once the parent is gone it is pruned.
- **Observation (fail-closed, not a defect):** if any integrity check fails (pin, SHA, committed bytes, or a missing commit in the fallback repo `/mpac/sdicks02/repos/clasher` when the job repo has no `.git`), admission raises rather than continuing without a seed.
  - That is stricter than "no seed, normal capture". It can only abort the job, never widen the allowlist.
  - Operationally, 03's live repo must contain b2f9e25e unless the job repo is a git checkout.

## 3. The OP-4 meter, caps and descendants are unchanged: PASS

- `git diff a6f145ac a697647b` is empty for `ssh_budget.py`, `ssh_transport.py`, `supervise.py`, `perception_confirmation.py` and `idle_services.py`.
- The only change to `host_audit.py` is the 3-line admission hook.
- A seeded source enters the same `Families.sources` map that OP-4 already uses. Budgets, `record`, `sample` and `finish` are untouched.
- `test_seeded_non_reader_child_is_budgeted_and_over_budget_stops` confirms that a non-reader child under the seeded parent is metered, flagged as interference and stopped when over the cap.
- The seed code contains no kill, signal or connection handling, so the 04 owner's connection is unaffected.

## 4. Scope is guard code, data, tests and the manifest: PASS

- b2f9e25e adds 1 file, the receipt.
- a697647b changes 9 files, all under `reports/explore/t1/`: `parent_source_seed.py`, `host_audit.py` (the hook), `qualify.sh` (adds `test_op5.py`), `test_op5.py`, `FROZEN-T1.json`, `OP5-T1.md`, `PROGRESS-T1.md`, and the receipts `op5-unit-tests.json` and `excluded-smoke-op4-r5.json`.
- In `FROZEN-T1.json`, only two pinned entries change SHA (`host_audit.py`, `qualify.sh`) and six are added. All 118 pinned SHAs verify against the a697647b tree.
- No scientific or pinned non-guard file changed.
- The other non-T1 paths in `a6f145ac..a697647b` come from other threads' intervening commits (24bfa017 E4, 127a77e9 coordinator), not from OP-5.

## 5. Tests: PASS

- I ran `test_op1.py` through `test_op5.py` from a detached worktree at a697647b with `/mpac/sdicks02/venvs/t1-verifier` (CPython 3.12.12) under nice 10.
- Result: **58 passed** in 3.7 s, matching the claimed 58/58. `test_op5.py` alone: 12 passed.
- The tests cover:
  - an exact match seeding;
  - each of the six fields, mismatched, giving no seed;
  - a wrong source IP or connection;
  - the wrong host;
  - uncommitted bytes being denied;
  - a conflict not being overwritten;
  - a seeded non-reader child being budgeted, then stopped when over budget.

## Residuals (non-blocking)

- R1: integrity failures abort admission rather than falling back to normal capture. This is fail-closed (see §2).
- R2: the seed is hard-scoped to 127x03, `129.65.221.14` and UID 3822945. A new generation of the 04 connection, after a reconnect, needs a new committed receipt.
- R1 through R3 of the OP-4 re-confirmation are still disclosed and unchanged.

No reporting outcomes were read.
