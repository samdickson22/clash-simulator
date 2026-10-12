# T1 END exit-wrapper r3: narrow independent re-review

- Reviewer: Claude Opus 5.5 (1M), independent and read-only, running on 127x05.
- Written: 2026-10-12T01:02Z.
- Candidate: commit e2031fb4.
  - Wrapper `reports/explore/t1/end_exit_push.sh`, SHA-256 `0a87166f23f1eec742605da1f15e94f40602546a6926c7a53bc15d2a6b8d61b1`.
  - Verifier `reports/explore/t1/end_verify_push.py`, SHA-256 `325a00a6be155f21b2a745b783290d015b92edd7e25ba551d0765fab3a8d117c`.
  - I checked both hashes against `git show e2031fb4:…`.
- Diff `END-exit-push-r3-narrow.diff`, SHA-256 `d6d89197af5d…`. Verified. Its hunks match `git diff 9fee6c95 e2031fb4` for the two files exactly; only the `--no-index` path headers differ.
- Worker receipt `END-exit-push-r3-candidate-20261012T0055Z.json`. Test script `END-exit-push-r3-offline-tests.py`, SHA `7dfe6166…`, verified.
- Context read: r2 review (`END-exit-push-REVIEW-r2.md`), coordinator ruling cf913189, frozen `detach.sh`, `host_audit.py`, and E4 `receipts.py`/`measure_tiers.py` at e2031fb4.
- What I did not do: no SSH to any host, no commits, and no sealed outcomes or heldout data opened. Scratch was `/mpac/sdicks02/scratch/t1-r3-review-20261012T005843Z/`, now deleted. This file is my only write outside scratch.

## Verdict: **APPROVE_WITH_CONDITIONS**

**Wrapper.** The wrapper at `0a87166f` is approved as-is.
- It fixes F1 and F5–F8.
- It lays out F3 correctly.
- It keeps every round-2 timing guarantee.

**Verifier.** The verifier at `325a00a6` is approved **only** under conditions V1–V3 below. It does every check the ruling asked for. But I demonstrated two fail-open paths where it ACKs data that was not delivered by this attempt or is corrupt (R3-1, R3-2):
- R3-1 needs only an interpreter flag.
- R3-2 needs a skipped procedure step plus a reused attempt name.

Neither path is timing-relevant. Each has a fix of roughly 3–6 lines (given below). If T1 applies those fixes, the new verifier SHA needs only a delta check of those lines.

## Round-2 guarantees (regression check)

| Guarantee | r3 status | Evidence |
|---|---|---|
| Zero activity during timing | **PASS** | Everything before `"$@"` (`:5-38`) is local: `hostname`, string tests and the `argv.nul` write. A single foreground `"$@"` follows (`:41`), with no trap, job, timer or network call. All rsync, ssh, sleep and date calls come after `:42`. |
| Idle parent invisible to the OP-6 guard | **PASS** (unchanged) | `#!/usr/bin/env bash` makes argv0 `bash`. `foreign_compute` uses only the first token's basename (`host_audit.py`, `first=Path(r['cmd'].split()[0]).name`), so the python argv in the wrapper's cmdline is irrelevant. A waiting bash uses no CPU, so it is never `foreign_active`. |
| Exact argv run once | **PASS** | `"$@"` sits outside every loop. All 14 worker and reviewer end-to-end runs recorded exactly one invocation. `argv.nul` records the argv NUL-delimited before exec. |
| Frozen `detach.sh` compatibility | **PASS** | `detach.sh` (`1648dfdc`) creates `$log` by redirection and writes the receipt with `printf` *before* `exec`. So the wrapper's `:20` precondition (`detach.log` exists, `detach.json` non-empty) always holds when it is launched via `detach.sh $job/detach.log $job/detach.json …`, with no race. |

## Ruling items F1, F3–F8

| Item | Status | Notes |
|---|---|---|
| F1: early death still delivers the exit code | **FIXED** | `exit.json` is written unconditionally (`:43-48`), then each metadata file is pushed independently (`:70-72`), and `measurement/` only if it exists (`:73-75`). I tested this with the **real frozen `ReceiptStore`** and real rsync: argparse exit 2, SIGKILL 137 and raised failure 1 all deliver `exit.json` with the true code. |
| F3: receive namespaced per host and attempt, created empty beforehand | **FIXED in layout; creation is procedural** | Receive is `end-received/$host/$attempt`, and `--prepare` refuses an existing directory. The wrapper does **not** require that `--prepare` ran, because rsync creates the missing last path component. See R3-2. |
| F4: 05 verifier before any ACK | **IMPLEMENTED, two fail-open gaps** | Checks the marker, the seal SHA, every file SHA, no extra or missing files (dot-temp files included, since pathlib `rglob` matches them), and exit 0 ⇔ status complete. A missing manifest gives UNSEALED with no ACK. See R3-1 and R3-2. |
| F5: detach log and receipt pushed | **FIXED** | Pushed along with `argv.nul`. See R3-3 for a snapshot caveat. |
| F6: `--output` asserted, trailing slash rejected | **FIXED** | Eight reject cases all exit 90 with zero E4 invocations: job with trailing slash, `--output=`, `--output` twice, wrong output, output with trailing slash, no `--output`, dangling `--output`, wrong host. |
| F7: `exit.json` reflects the actual outcome | **FIXED** | Only observed values are written (`exit_code`, `measurement_exists`). No seal claim is hardcoded. |
| F8: `timeout -k` | **FIXED** | `timeout -k 30` on every transfer (`:59`, `:87`). Verified with the real `timeout` (R3-4). |

## Findings

### R3-1 — Medium (ACK correctness): every verifier check is an `assert`, so `python -O` or `PYTHONOPTIMIZE` turns the verifier into an unconditional ACK
- **Where:** `end_verify_push.py:15-18, 37-79, 91-92`.
- **Demonstrated:** I corrupted `durable-measurement/sub/nested.bin` after a good push.
  - A normal run gives `AssertionError: File SHA mismatch`.
  - `python3 -O` gives `ack_allowed: true`.
  - `PYTHONOPTIMIZE=1 python3` gives `ack_allowed: true`.
  - `python3 -I` with `PYTHONOPTIMIZE=1` rejects, because `-I` ignores `PYTHON*` variables.
- **Fix (2 lines):** add `if not __debug__: raise SystemExit('verifier requires assertions')` at module top. Better, replace the `assert`s with explicit `raise`.

### R3-2 — Medium (ACK correctness): stale or foreign data can be ACKed, because the marker is not bound to this run, `PUSH-FAILED.json` is ignored, and `--prepare` is not enforced
- **Where:**
  - `end_exit_push.sh:11-17,36`: `attempt` is the basename only, yet two parents are allowed (`$base` and `$base/fleet-end-attempts-0108/$host`). Both map to the same `end-received/$host/$attempt`.
  - `end_verify_push.py:39-50`: the marker is matched to `exit.json` only by host, attempt and exit code.
- **Demonstrated** with real rsync, the real `ReceiptStore`, and no `--prepare` (rsync auto-created the receive directory):
  1. Run 1, job `$base/X`, pushes and seals completely with exit 0.
  2. Run 2, job `$base/fleet-end-attempts-0108/127x01/X`, also exits 0. Its metadata push overwrites `exit.json`, `detach.log` and `argv.nul`. Its measurement push fails (rsync 23), so it writes `PUSH-FAILED.json`.
  3. The verifier returns **SEALED, `ack_allowed: true`**. It has ACKed run 1's measurement under run 2's `exit.json` and `detach.log`, while run 2's measurement never arrived.
- **Fix (about 4 lines):**
  - Put `exit_utc` (or the SHA-256 of `exit.json`) into `TRANSFER-COMPLETE.json`, and have the verifier require equality.
  - Have the verifier reject when `PUSH-FAILED.json` is present.
  - Optionally have `--prepare` write a nonce file the verifier requires, or reject a duplicate basename across the two parents in the wrapper.

### R3-3 — Low: the pushed `detach.log` is a snapshot taken at E4 exit, and `PUSH-FAILED.json` carries no rsync code
- **Where:** `:70`, `:84`.
- **What happens:** stderr from later transfers (for example a measurement push failure) exists only in the host's copy. `PUSH-FAILED.json` records no `rc`.
- **Recommendation:** add the last `rc` to `PUSH-FAILED.json`, and pull the host `detach.log` after any `PUSH-FAILED` (C4).

### R3-4 — Low (timing-relevant, procedural): the wrapper's lifetime is now bounded, but still about 22 minutes after exit, so C1 remains mandatory
- **Bound:** about 1300 s. That is the 1200 s deadline, plus up to 30 s kill grace and a 10 s sleep overrun, plus at most 60 s for the final `PUSH-FAILED` attempt. Once the deadline passes, later `push_file` calls return 124 immediately.
- **Verified** with the real `timeout`, the deadline patched to 20 s, and an rsync stand-in that ignores TERM and has a TERM-ignoring grandchild:
  - wall time 50.1 s, return code 92;
  - a single measurement attempt;
  - no lingering process afterwards. `timeout` signals its own process group, which killed the grandchild.
- **Consequence for 127x01:** before the 01 reference starts, the A6 wrapper on 01 must be observed gone: its receipt PID is absent from `/proc`.
- **F9 update:** `timeout` calls `setpgid`, so an in-flight rsync or ssh is **not** in the detach-receipt PGID. Killing that PGID mid-push will not kill rsync, although `timeout` still bounds it.
- No ssh ControlMaster or ControlPersist is configured for `127x??` (shared NFS `~/.ssh/config`), so ssh leaves no mux process behind.

### R3-5 — Info: retry classification is sound and every loop is bounded
**Codes:**
- **Retried** (at most 3 tries in a shared 1200 s deadline): rsync 10 (socket I/O), 12 (protocol stream / connection drop), 30 (data timeout), 35 (daemon connect timeout), 255 (ssh), and `timeout`'s 124/137.
- **Terminal immediately:** 1/2/3/5/11/13/14/20–25. That includes 23 (missing source or partial transfer) and 11 (05 disk full).
- **255 is a mixed case.** It also covers permanent ssh failures (auth, host key), but at most 3 attempts with no-op sleeps in between makes that harmless.

**Optional:** `-e 'ssh -o BatchMode=yes -o ConnectTimeout=20'`. It isn't needed: stdin is `/dev/null` with no tty, so prompts fail fast with 255.

**Brief vs code:** the brief says "exit 52 is transient; 255 and 53 bounded". That matches neither the code nor the receipt.
- 52 and 53 are not rsync codes, and the code doesn't classify them; both would be terminal.
- The worker tests cover only 255 (3 attempts) and 23 (1 attempt).
- My real-`timeout` run additionally covered 124/137.

### R3-6 — Info: ACK semantics and verifier exit codes
- **What ACK means:** `DURABLE-ACK.json` means durable, hash-verified delivery. It does **not** mean success. A sealed `failed` run is ACKed with `status: failed`.
- **Exit 0 ⇔ status `complete` was checked** against `measure_tiers.py` `main()` (lines 662–737):
  - success returns 0;
  - any exception writes `failure.json` and re-raises, giving exit 1;
  - a cleanup failure flips the status to failed and re-raises;
  - SIGKILL or SIGTERM leaves no seal, which gives UNSEALED.
  
  A run that seals `complete` but then exits non-zero (for example from an interpreter-teardown error) is rejected permanently and needs manual handling.
- **Verifier return codes:** 0 means ACK, 2 means UNSEALED. A traceback with exit 1 means any check failed, including malformed JSON or a missing key. In that case no file is written, so the caller must capture stdout/stderr as the rejection record.
- **Argv:** the verifier checks that `argv.nul` exists but not what it contains. The wrapper's `--output` check can't see argparse prefix abbreviations (an extra `--outp X` would win), so the recorded argv has to be compared at verify time (V3).

### R3-7 — Info: frozen bytes — PASS
- **Diff scope:** `git diff c9baa077^ e2031fb4` touches only `end_exit_push.sh`, `end_verify_push.py`, `end_owned_copier.py` (withdrawn), `PROGRESS-T1.md`, T1 receipts and K4S run-r1 health receipts.
- **Frozen manifest:** `FROZEN-T1.json` = `24817e16…`, identical at both ends.
- **Guard and launch files:** all 167 entries were re-hashed at e2031fb4. The guard modules and `detach.sh` `1648dfdc` match.
- **Six pre-existing mismatches:** `barrier.py`, `corpus.py`, `run.py`, `test_barrier.py`, `test_corpus.py` and `PROGRESS-T1.md`. They are byte-identical at `c9baa077^` and e2031fb4; the last code changes were 64608f6f and a51ea64c, before this delta. They were **not introduced here**; I'm listing them only so nobody misreads a full re-hash.
- **E4 files:** identical at `c9baa077^` and e2031fb4:
  - `measure_tiers.py` `6066228b`
  - `fleet_reference.py` `c767a6e0`
  - `fleet_validity.py` `94d0e7f2`
  - `receipts.py` `839a43be`

## Tests run (127x05, `nice -n 19 taskset -c 63`, scratch only)
- **Setup:** I took the wrapper and verifier from `git show e2031fb4`. The only change was the `base`/`BASE` constant, repointed to scratch.
- **Static check:** `bash -n` passes.
- **Worker suite** (`END-exit-push-r3-offline-tests.py`, paths repointed): **all 16 results reproduce.** That covers 6 wrapper modes and 10 verifier cases.
- **Reviewer additions,** run with real rsync 3.1.3 (with `127x05:` rewritten to a local path), the real `timeout`, and a fake E4 using the **frozen `receipts.py` `ReceiptStore`**:

| Case | Result |
|---|---|
| E4 ok (exit 0) | `exit.json` 0, SEALED `complete`, ACK |
| E4 raised (exit 1) | `exit.json` 1, SEALED `failed`, ACK (health only) |
| E4 SIGKILL after writes (137) | `exit.json` 137, UNSEALED, no ACK |
| argparse-style exit 2 before `ReceiptStore` | `exit.json` 2, metadata delivered, UNSEALED, no ACK |
| Measurement push partial, then rsync 23 | wrapper rc 92, `PUSH-FAILED`, no marker, verifier REJECT |
| Receive not prepared | rsync auto-creates it; verifier ACKs a correct push (so prepare is not enforced) |
| Stale reuse across two parents | **ACK of run 1 data under run 2 metadata** (R3-2) |
| 8 argv/job/host validation cases | all exit 90, 0 E4 invocations |
| Corrupted file under `-O` / `PYTHONOPTIMIZE` | **ACK** (R3-1); `-I` rejects |
| Hung TERM-ignoring rsync, deadline 20 s | rc 92, 50.1 s, 1 attempt, no lingering processes |

The scratch directory was deleted afterwards. The real `end-received/127x01` and `127x08` are still empty, and the job base has no test residue.

## Conditions (mandatory before launch unless R3-1 and R3-2 are fixed in code)
- **V1 (R3-1).** Always invoke the verifier as `nice -n 19 taskset -c 63 python3 -I /abs/path/end_verify_push.py --receive …`, never with `-O`. Record that argv in the verification receipt.
- **V2 (R3-2).** For every attempt:
  - before launch, run `--prepare` on 05 and record its JSON output; a FileExistsError means stop;
  - use attempt basenames that are unique per host across **both** allowed parents;
  - before trusting an ACK, confirm that `PUSH-FAILED.json` is absent and that `TRANSFER-COMPLETE.utc ≥ exit.json.utc`. Otherwise treat it as no-ACK and pull from the host.
- **V3 (R3-6).** At verification, compare the pushed `argv.nul` byte-for-byte with the approved launch argv from the launch receipt. Treat any traceback or non-zero verifier exit as no-ACK and record its output.
- **Carried from r2,** updated:
  - **C1:** prove that every prior wrapper on the host has exited. This is required for A6 → 01-ref, since the wrapper can live about 22 minutes after exit (R3-4).
  - **C4:** pull the host `detach.log` after any `PUSH-FAILED`, or if `exit.json` hasn't reached 05 within about 25 minutes of E4 exit. That pull happens only after timing has ended.
  - **C5:** no SSH into the timed host from any thread.
  - **C6:** stage the wrapper (`0a87166f`) on each timing host and the verifier (`325a00a6`) on 05, and check their SHAs. Launch via frozen `detach.sh $job/detach.log $job/detach.json /abs/end_exit_push.sh $job <exact argv>`. Use the staged A3 package bytes, never the shared checkout.
- **C2 and C3 are superseded:** C2 by `--prepare` plus V2, and C3 by the verifier plus V1–V3.
