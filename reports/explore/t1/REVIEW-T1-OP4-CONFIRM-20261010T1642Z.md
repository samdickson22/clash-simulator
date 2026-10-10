# T1 OP-4 fast confirmation: cb1b9f12

**Verdict: NOT_CONFIRMED.** One blocking finding (B1), which is narrow and quick to fix. Everything else checks out.

- Reviewer: independent T1 reviewer, running on 127x05 with git and local files only. I made no ssh connection to 01, 03, 04 or 08.
- Candidate: `cb1b9f128d0dc9aeda2f357c425e71ba9c0e7980` (d831f234 plus the source-conflict tightening).
- Base: `9cd518d3` (OP-3 confirmed in 85c4eb30).
- Packet: `/mpac/sdicks02/jobs/clasher/t1-20261010-r1/review/cb1b9f12…/`.
- Reporting games: 0. Outcomes stay sealed.

## 1. Scope: PASS

`git diff 9cd518d3 cb1b9f12` touches only the files below, plus 2 lines in COORDINATOR.md (intervening coordinator commits 32b3bb26, d9747760 and 71f05e55).

| Kind | Files |
|---|---|
| Guard and meter code | `host_audit.py`, `supervise.py`, `ssh_transport.py` (the copier snapshot attribution only), `health.py` (one added counter), new `ssh_budget.py` |
| Tests | new `test_op4.py`; `qualify.sh` adds it to the pytest list |
| Docs, receipts, manifest | `OP4-T1.md`, `PROGRESS-T1.md`, the OP-3 review, the receipts, and the 71f05e55 OP-3 admission block in `FROZEN-T1.json` |

Every other tracked file under `reports/explore/t1/` is byte-identical to 9cd518d3. That covers the runner, reducer, seeds, decks, `perception_confirmation.py` (OP-2), `owned_supervisor.py` (OP-3) and `test_op1`/`test_op2`/`test_op3`. Nothing outside `reports/explore/t1/` changes except COORDINATOR.md.

## 2. Budget rule: PASS, except B1

**Comparisons are exact and inclusive.** All three caps use `Fraction` arithmetic, and elapsed time goes through `Fraction(str(elapsed))`.

| Path | Test | Effect |
|---|---|---|
| Flag | `ticks*200 > hz*T` | Exactly 0.5% passes; anything above it flags. |
| Stop on block average | `ticks*50 > hz*T` | Exactly 2% passes; anything above it stops. |
| Stop on one sample | `ticks*4 > hz*dt` | Exactly 25% passes; anything above it stops. |

**Stop paths.** `stop_reason` checks, in order: console user, then non-ssh foreign, then foreign_active, then the sample cap, then the running block average. The supervisor writes `ssh_family_sample` into `stop-reason.json`. A flagged block sets `interference.ssh_family.interfered` and ORs it into `interfered`, and `health.py` counts these blocks.

**Binding to the parent generation.**
- The source cache is keyed by `(job, pid, start_ticks, uid, cmdline_sha256)` of the authenticated `sshd: sdicks02@notty` parent with UID 3822945.
- A child is accepted only if `ssh_family_parent_snapshot` matches that key. The snapshot is taken at /proc read time, and the read is checked for start-tick stability.
- Cache entries are dropped once their generation is gone. A reused PID gets no proof (tested).
- A conflict sets the cached source to None for the life of that generation and can't be undone by a later LAN child (tested in cb1b).

**Descendants are included.** `ancestor()` walks up to 64 ppid hops to the authenticated root, so arbitrary descendants are tagged even if they have no SSH_CONNECTION of their own. The parent itself is metered too.

**Fallback to identity rules.** A non-LAN source (`129.65.221.0/24`, port 22), an unknown one (no captured child source) or a conflicting one leaves rows untagged. They then go to `CONFIRMATION` and `foreign_compute`, which are unchanged (tested). See N1 for one transitional case.

**Every ssh-family process is recorded.**
- At each census, `ssh-family-occurrences.jsonl` gets a row for each family process: pid, start_ticks, cmd hash, ticks, captured source, parent identity and children.
- Each block's meter keeps per-process records and child commands.

## 3. Non-ssh foreign processes still stop: PASS. Compute hiding under sshd: FAIL (B1)

**What passes:**
- Only LAN-family descendants and approved idle services ever receive `allowlist_kind='ssh_family_budget'`. Any process without an authenticated LAN root keeps the prior rules, so a stray `python` stops with `foreign_compute` (tested, and confirmed by reading the code).
- A console user stops unconditionally.
- Admission now also denies on console (`not c['positive']`).

**B1 (blocking): CPU from reaped short-lived descendants is never metered.**

- **Cause.** `cpu_ticks` is `utime+stime`, stat fields 14–15, of processes alive at a census (`host_audit.py:66`). The meter (`ssh_budget.update`/`sample`) only sees processes that are present at the ~1 s census.
  - A tagged shell that forks short children has every child's CPU land in its `cutime`/`cstime` (fields 16–17) when it reaps them. That is never read.
- **Why OP-4 opens this.** Under OP-1/2/3 the persistent shell under sshd was an unapproved child, so the host stopped. Under OP-4 that shell is budgeted with near-zero CPU of its own.
- **Live probe on 05.** I used the real `host_audit.processes()` and the real `ssh_budget` code on real `/proc`, with a synthetic LAN `sshd: sdicks02@notty` row above a real bash loop (self-ssh is refused on 05). The loop was pinned to one CPU, nice 19, for 14 s. The probe is `/mpac/sdicks02/tmp/op4probe/live_reaped.py` and is not committed.

  | Child lifetime | True CPU incl. reaped | Metered | Result |
  |---|---|---|---|
  | ~47 ms (`sh` busy loop) | 0.46 core (654 ticks) | **0.07% (1 tick)**; children visible in 0/13 censuses | **no flag, no stop** |
  | ~0.4 s | 0.50 core | 18.5% | flag + 2% stop (correct) |

  So a make/xargs/script-style workload of short processes can use about a core per loop under a LAN session and still read as clean. That defeats "descendants are metered" and both the 2% and 25% caps.
- **Fix.** Add the `cutime+cstime` delta of every tagged row to its tick increment, in both `update` and `sample`.
  - This double-counts at most once a child that was seen alive and later reaped by a tagged parent, which errs toward flagging.
  - Children reparented outside the family already lose their tag and fall to the identity rules.
  - Add one test with constant utime and rising cutime.
  - The change is a few lines and can be re-checked in minutes.

## 4. Tests on 05: PASS

From a detached worktree at cb1b9f12 I ran `test_op1.py test_op2.py test_op3.py test_op4.py` with `/mpac/sdicks02/venvs/t1-verifier` (CPython 3.12.12) under nice 10: **42 passed**, which matches the packet's 42/42.

## Non-blocking disclosures

- **N1. One census can be stricter than the identity rules.**
  - In that census, the first `FAMILIES.apply` tags a row, `identity_collect` then finds a conflict, and the second apply untags it.
  - That row skipped `CONFIRMATION`, and any original kind (perception reader, idle cache, copier) was overwritten and then popped. The row is therefore judged by the bare `foreign_compute`.
  - The error fails closed. The next census applies the proper identity rules.
- **N2. Stopping on the running average can fire in a block's first seconds.**
  - `finish(meter, elapsed)` runs on every loop iteration from block start, so 3 ticks (30 ms) in the first ~1.2 s exceeds 2% and stops the host.
  - Our own LAN copier sessions (sshd + `rsync --server`/`find`) are now family members and count toward the budget, so a copy that lands at a block's start could stop the host.
  - This fails closed but is fragile operationally. Suggestion: apply the 2% stop against `max(elapsed, planned block length)`, or from a minimum elapsed time. Leave the 25% sample cap as is.
- **N3. The sample cap is undercounted in one window.** `sample()` takes `born` from the post-census clock, while `before` was read at the previous census start. A process born during the previous census (up to about 2 s with CONFIRMATION) and absent from `before` counts 0 in its first sample. The per-block meter uses `born_since_ticks` from block start and does not have this gap.
- **N4. The 03 r4 pattern is resolved only if a source was cached.** A childless sshd parent with no captured child source in the current generation is "unknown" and keeps the identity rules, as specified.
- **N5. The manifest still needs re-pinning.** `FROZEN-T1.json` at cb1b still holds pre-OP-4 hashes for `health.py`, `host_audit.py`, `qualify.sh`, `ssh_transport.py` and `supervise.py`. It doesn't list `ssh_budget.py`, `test_op4.py`, `OP4-T1.md`, `receipts/op4-unit-tests.json` or this review. This is expected, because OP-4 doesn't admit itself, but it must be re-pinned before staging.
- **N6. The copier snapshot overrides the live environment.** In `ssh_transport.copier_activity`, the captured SSH_CONNECTION and T1_COPIER_* values come from the same process generation. This holds under the same-UID filesystem trust model already disclosed (OP-3 N3).

## Exact items for CONFIRM

1. Fix B1 (meter the `cutime+cstime` delta of tagged rows in `update` and `sample`) and add a test for it.
2. Recommended, not required: N2 floor on the average-stop denominator.
3. N5 re-pin at admission.
