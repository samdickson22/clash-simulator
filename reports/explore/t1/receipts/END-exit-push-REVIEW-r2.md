# T1 END exit-wrapper r2: independent review

- Reviewer: Claude Opus 5.5 (1M), independent and read-only, running on 127x05.
- Written: 2026-10-12T00:47Z.
- Candidate: `reports/explore/t1/end_exit_push.sh` at commit 9fee6c95, SHA-256 `8886028110814eaa1fe9b7662b4a1fbb4d88184198212c19859f7014f3db3b4f`. I verified this hash from `git show 9fee6c95:…`.
- Diff: `END-exit-push-candidate-r2.diff`, SHA-256 `701a1478…94615`. Verified; its content is identical to the committed script.
- Context read: r1 REQUEST_CHANGES (`receipts/END-copier-review-r1-20261012T0039Z.json`); commits c9baa077, 64daa21c, 9fee6c95 and 776fa428 (origin/main, offline-check receipt); `PROGRESS-T1.md` up to the 00:43:40Z checkpoint.
- What I did not do: no SSH to any 127x host, no commits, and no sealed outcomes or heldout data opened. This file is my only write.

## Verdict: **APPROVE_WITH_CONDITIONS**

The core r2 design is sound and resolves r1's B1 and B2:
- E4 runs once.
- The wrapper does no network or polling work while E4 runs.
- The frozen OP-6 guard sees an idle bash ancestor that is neither foreign compute nor foreign activity.

Every defect I found is in the **post-exit push path**, or in launch procedure around it. None of them can disturb a timing window *if* the procedural conditions C1–C6 below are met. Those conditions need no byte changes. If T1 prefers to fix them in code instead (H1–H5), the new SHA needs a narrow delta confirmation before launch.

## Check 1: nothing runs during timing — PASS

**The wrapper does nothing until E4 exits.** Lines 1–19 are pure local tests, then a single foreground `"$@"`. The shell has no traps, timers, background jobs or `sleep`, so bash blocks in `wait4` until E4 exits: zero ticks and zero wakeups. Every `rsync`/`ssh`/`sleep` call comes after line 20.

**How the frozen guard sees the parent.** I traced it against the frozen sources; all nine modules match the `FROZEN-T1.json` entries, and the manifest is `24817e16`.
- **Not owned.** `owned_tree` only descends from the roots in E4's `owned` array (`fleet_reference.py:46,125,130`, `fleet_validity.py:21-37,143`), so the wrapper, as an ancestor, is never owned. The guard replaces `host_audit.own_process` with a lambda over that tree (`fleet_validity.py:115`).
- **Not `foreign_compute`.** Its cmdline is `bash …/end_exit_push.sh …`: `#!/usr/bin/env bash` makes `env` exec `bash`. `foreign_compute` forbids only python, raylet, cargo, rustc, gcc, clang, node, java and ffmpeg, plus sshd-with-children, `op2_denied` and system dbus (`host_audit.py:84-92`).
- **Not `foreign_active`.** That needs more than 0.1 s of its *own* CPU per sample (`host_audit.py:182`). A waiting bash uses none.
- **Not SSH-family.** `ssh_budget.ancestor` needs a live `sshd: sdicks02@notty` ancestor (`ssh_budget.py:18-26`). The frozen `detach.sh` uses `setsid -f`, so the wrapper is reparented off the launch session. The inherited `SSH_CONNECTION` in its environ is ignored without that ancestor, exactly as for E4 itself under the same frozen detach.
- **OP-2 confirmation does not apply.** It runs only on 127x03 (`perception_confirmation.py:46`).
- **No copier exists.** With `owned-copier-admission.json` absent, `copier_activity` returns False (`ssh_transport.py:13-14`), and `ReportingGuard` accepts the absence (`fleet_validity.py:110-112`).

So the parent is admissible in the same sense as any idle non-python process. It is *not* "owned" or "pinned", but the frozen guard doesn't require that, and nothing about it needs pinning.

**detach.sh.** It is frozen (`1648dfdc`, matching the freeze). It writes the receipt before `exec`, and its outer poll exits within about 50 ms. That happens before E4's bundle validation and guard admission, and is unchanged frozen behaviour.

## Findings

Numbered, with severity. "Timing-relevant" means the finding can affect a guarded window.

### F1 — High (evidence liveness): the retry loop is neither bounded nor transport-only, and a missing `measurement/` blocks delivery of `exit.json` forever
- **Where:** `end_exit_push.sh:28-43`.
- **What happens:** the loop retries on *any* non-zero status and stops only on success or a `STOP-COPY` sentinel on the timing host. Line 29's `timeout 900` bounds a single attempt, not the loop.
- **Missing source.** If `$job/measurement` doesn't exist, rsync exits 23. I confirmed this locally with rsync 3.1.3 (`change_dir … failed … code 23`). That happens whenever E4 dies before `ReceiptStore(args.output)` at `measure_tiers.py` `main()`:
  - an argparse error;
  - a bad argv giving exec 126/127 (for example a bare `OMP_NUM_THREADS=1` passed as argv[0]);
  - an interpreter or import crash;
  - SIGKILL before the mkdir.

  Line 30 then fails every ~10 s forever. Because `exit.json` is chained after it with `&&` (`:31-32`), 05 **never receives the exit code**.
- **Other permanent errors** also loop forever: 05 disk full (11), permissions (23), host-key mismatch (255).
- **The mock missed it.** The offline mock `transport_retry_only` (receipt `END-exit-push-offline-check-20261012T0043Z`) only exercised a transient error, so the receipt's claim of "retries cover transport errors only" is false for these bytes.

### F2 — High (timing-relevant): a lingering push loop from an earlier attempt can kill a later timing run on the same host
- **Where it bites:** A6 runs on **127x01** (`END-A6-staging-20261012T0027Z.json`), and the 01 reference also runs on 127x01.
- **Why admission misses it:** a still-looping A6 wrapper (F1) is outside any E4 owned tree. While it sleeps it passes reference admission.
- **How it kills the run:** each wake spawns `ssh` + `rsync --checksum` over the A6 receipts. Re-hashing a large directory easily exceeds 0.1 s of CPU in a 1 Hz sample, which is `foreign_active` and a guard stop with no retry. Even when cheap, it is an unreviewed periodic process during timing.

### F3 — Medium: the 05 receive path isn't namespaced by host or attempt
- **Where:** `:30,32,38`.
- **What happens:** the destination is `127x05:$job/…`, with the *same absolute path* as on the timing host. The only freshness checks are host-local (`:13-14`), and `/mpac` is per host.
- **Why it's likely:** T1 has previously used one job name for both hosts (`replacement-frozen-op6-0108-r1`, `end-a3-f6cebbaa-0108-r1`).
- **Consequence:** if 08 and 01, or A6 and 01, share a `$job` path, the second push merges into the first. rsync `-a` runs without `--delete`, the filenames are identical (`receipt-manifest.*`, `capacity.jsonl`, …), and `exit.json` and `TRANSFER-COMPLETE.json` get overwritten. That corrupts the durable 05 copy. The originals on the hosts survive.

### F4 — Medium: the "05 verifies the full seal before any ACK" step is not part of the candidate
- **Where:** `:34`. It writes `hash_verification_pending:true`, but no verifier code exists. I grepped the repo and the job directory for `durable-measurement`/`TRANSFER-COMPLETE` and found only older copier scripts.
- **Why it matters:** `--partial` (`:29`) leaves truncated files **under their final names** after an interrupted attempt. Only `TRANSFER-COMPLETE.json` plus a full per-file manifest check tells a partial push apart from a complete one.
- **Sealed vs unsealed:** a SIGKILL or host-loss attempt has no `receipt-manifest.*` at all, so it cannot be "seal-verified" and must be recorded as unsealed.

### F5 — Low-Medium: the detach log and detach receipt are never pushed
- E4's stdout/stderr, including any traceback, goes to the detach log. That log has to sit outside `measurement/`.
- For exactly the F1 early-death cases, it is the *only* failure evidence. The claim that "all raw success and failure fragments" are pushed is incomplete.

### F6 — Low: the job path and argv are only loosely checked
- The wrapper never asserts that the E4 argv contains `--output "$job/measurement"`. A mismatch falls straight into F1.
- `$job` = `/mpac/sdicks02/jobs/clasher/t1-20261010-r1/` (trailing slash, i.e. the shared root) matches the `/*` case at `:7-8`. It would then push `exit.json` into the shared root on 05.

### F7 — Low: `exit.json` hardcodes `"measurement_returned":true,"outcomes_sealed":true`
- **Where:** `:22`.
- **Why it matters:** both values are written even after a crash with no seal. Treat them as wrapper self-report only. Seal status comes solely from `receipt-manifest.json.status`.

### F8 — Low: `timeout` has no `-k`
- **Where:** `:29,31,37`.
- A TERM-ignoring hang would not be bounded. This is post-exit only; `ServerAliveInterval 30` in the shared `~/.ssh/config` mitigates it.

### F9 — Info: what the detach receipt now points at
- The detach receipt PID/PGID now identify the **wrapper**, not E4; E4 shares the wrapper's process group.
- Guard ownership is unaffected, as shown in Check 1.
- Anything that reads "receipt PID alive" as "E4 running" is wrong during the push phase; use `exit.json` instead.
- Killing the receipt PGID kills both processes, which is acceptable.

### F10 — Info (timing-relevant, procedural): "no SSH during timing" must cover every thread, not just this wrapper
- That includes T1's own 20-minute END timer, health probes and the paused hub mirror.
- 127x01 is the fleet hub, so any inbound LAN SSH to it during its window becomes an SSH-family process under the frozen 0.5%-per-block flag.
- K4S uses 03/04 with its hub on 05, so it doesn't touch 01 or 08.

## Check 2: exit and push
- **Exit code:** recorded faithfully (`:19-20`), including 128+n for signals; the write is atomic via tmp + `mv`.
- **E4 cannot be re-run:** `"$@"` sits outside any loop. PASS.
- **Failure fragments:** whenever E4 reaches `ReceiptStore`, its `except`/`finally` writes `failure.json` and seals, so failure fragments are pushed. PASS. Early-death cases fail: see F1 and F5.
- **Retries:** not bounded and not transport-only: see F1.
- **Verification before ACK:** not implemented: see F4.
- **Partial vs complete:** distinguishable only through `TRANSFER-COMPLETE` plus full manifest verification: see F4.

## Check 3: attribution (B2)
B2 is moot for r2.
- No copier is registered, so nothing during timing needs source attribution.
- The post-run rsync runs from the timing host to 05 only after E4, and therefore its guard monitor, has exited. It is never in any guard's view.
- On 05 the receiving `sshd`/`rsync --server` runs on an untimed host.

Requirement: no receipt may claim source-IP binding. r2's receipt correctly says `no_owned_copier_registration:true`.

## Check 4: binding and launch order
The progress log gives this order:
1. fresh C2 apt/motd recheck before EVERY launch;
2. fresh guard job (byte-identical freeze, bus and seed inputs; no copier admission; idle and supervisor admissions only if pinned);
3. launch via frozen detach;
4. E4 exit;
5. push;
6. 05 verification.

It also keeps 08 first and the 01 cutoff at 04:17:43Z. That order is correct. Two steps are missing and are added as C1 and C2 below:
- before each launch, prove no earlier wrapper is still alive on that host;
- have 05 pre-create the receive namespace empty.

**Outcomes:** the wrapper only touches E4 reference receipts, which are fixed public fixtures with `outcome_access=False`. No sealed outcomes are read.

## Check 5: frozen bytes — PASS
- **Diff scope:** `git diff c9baa077^ origin/main` touches only `end_owned_copier.py` (new, withdrawn), `end_exit_push.sh` (new), `PROGRESS-T1.md` and receipts.
- **Guard and launch bytes:** `FROZEN-T1.json` = `24817e16…`. All nine guard modules match their freeze entries. `detach.sh` = `1648dfdc`, `launch.sh` = `49db4d29` and `runtime.sh` = `18306c83`, all matching the freeze.
- **E4 bytes:** these are identical at `c9baa077^`, 9fee6c95, origin/main and in the staged `END-A3-package-f6cebbaa.tar`:
  - `measure_tiers.py` `6066228b`
  - `fleet_reference.py` `c767a6e0`
  - `fleet_validity.py` `94d0e7f2`
  - `receipts.py` `839a43be`
- **Shared-checkout note:** the local shared checkout on 05 (HEAD 4292e520, behind origin) has a *different* `measure_tiers.py` (`5d7de8e3`), although its `main()` is identical. The launch must use the staged package bytes, never the shared checkout.

## Check 6: tests
- `bash -n` on the committed bytes, run under `nice -n 19 taskset -c 63` on 127x05: PASS.
- rsync 3.1.3 dry-run on a missing source returns 23, which confirms F1.
- shellcheck isn't installed.
- I didn't re-run the worker's mocks, because they need writes under the job prefix; their receipt is consistent with the code except for F1's untested permanent-error path.

## Conditions (mandatory before any launch; procedural, no byte changes)
- **C1 (F2).** Before every launch on a host, prove every earlier wrapper on that host has exited, and that its push was verified on 05 or deliberately abandoned. Use the detach receipt's PID and start time gone from `/proc`, or a `STOP-COPY` followed by observed exit. This applies above all to the A6 wrapper on 127x01 before the 01 reference.
- **C2 (F3).** Give A6, 08-ref and 01-ref distinct `$job` paths. 05 pre-creates each one empty and refuses to proceed if `durable-measurement/`, `exit.json` or `TRANSFER-COMPLETE.json` already exist there.
- **C3 (F4).** ACK only after a reviewed or byte-recorded 05-local verifier has passed every check below. It must not interpret outcomes.
  - (a) `TRANSFER-COMPLETE.json` is present.
  - (b) `receipt-manifest.sha256` matches `receipt-manifest.json`.
  - (c) Every listed file's SHA matches.
  - (d) No unlisted files exist beyond the two manifest files.
  - (e) `exit.json.exit_code == 0` ⇔ `status == "complete"`.
  - (f) A missing manifest is recorded as UNSEALED, never as complete.
- **C4 (F1/F5/F6).** Record the exact argv, including `--output $job/measurement`, in the launch receipt, and pass a canonical `$job` with no trailing slash. After E4 exits, check whether `exit.json` reached 05. If it hasn't within about 20 minutes, the operator may SSH in (timing has ended) to:
  - pull `exit.json`, the detach log and the detach receipt;
  - create `STOP-COPY` and confirm the wrapper has exited.
  
  Pull the detach log and receipt for every attempt anyway.
- **C5 (F10).** For each timing window, the coordinator confirms that no thread SSHes into the timed host. That includes T1's own END timer, health probes and mirror.
- **C6.** Stage `end_exit_push.sh` on each host and check its SHA (`8886028…`) there. Invoke it by absolute path via the frozen `detach.sh`, with log and receipt outside `measurement/`.

## Optional hardening (only with a delta re-review)
- **H1.** Push `exit.json` and the detach log *before* and independently of `measurement/`, and tolerate a missing `measurement/`.
- **H2.** Retry only on 255, 10, 12, 30, 35 or 124. Cap retries by count or deadline, and write a local `PUSH-FAILED.json` when the cap is hit.
- **H3.** Namespace the 05 destination by `$(hostname)`.
- **H4.** Assert `--output "$job/measurement"` in argv, and require `$job` to be exactly one path component below the prefix.
- **H5.** Use `timeout -k 30`; drop the hardcoded `outcomes_sealed`.
