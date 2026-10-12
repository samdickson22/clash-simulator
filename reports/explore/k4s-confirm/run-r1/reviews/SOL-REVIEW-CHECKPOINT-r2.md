# Independent review: K4S checkpoint gate, round 2

**Verdict: REQUEST_CHANGES.** R2 and R3 are resolved. R1 is corrected when host failed-ID data is available, but a new early return suppresses the required k escalation when that data is unavailable, even though the ledger has been successfully validated. The supplied tests pass and meaningfully distinguish the fixes from the baseline; they miss this combined failure case. No remote mutation or study-outcome exposure was found.

## Scope and identity

Reviewed the immutable `f57fa318` tree in `/mpac/sdicks02/repos/clasher`, under `reports/explore/k4s-confirm/run-r1/`. The main checkout is at another commit, so repository objects supplied the authority. The standalone candidate, tests, fixture, and diff under `/mpac/sdicks02/k4s-runner/run-r1/` match those objects byte-for-byte. No checkout was changed.

| Artifact | Verified SHA-256 |
| --- | --- |
| Candidate `tools/candidate-r2/checkpoint.py` | `bb5d768572ef93f2cf5094715fdbdab658d53ac8cc2a357df355a86b29072b0b` |
| Baseline `b5530e98:.../tools/checkpoint.py` | `40cca7725def711070b9499a3226a79836a89482c400e1e3bddd6fedd19a64d2` |
| Supplied diff | `421659bd400e11eba6c9f228b1abd3c92d64e1844ce6ee9b3d53c22d30439707` |
| Tests `tools/candidate-r2/test_checkpoint.py` | `22fef0a65153391af7660f3f82f5b5414db75c66fb8a8c967868aeb7bc971599` |
| Fixture `tools/candidate-r2/fixtures/blind-ledger-r2.json` | `4a56abf356446c3cae6935674ffe4c92273ff8a91f689a097eaec76c935d5510` |

The supplied diff's hunks exactly match the baseline-to-candidate diff. The ordinary committed `tools/checkpoint.py` in `f57fa318` remains the baseline; this verdict concerns the candidate only. Line numbers below refer to the candidate.

Read the prior independent review `SOL-REVIEW-CHECKPOINT-r1.md`, the relevant frozen schedule and producer code, and the round-r2 audit. This was an offline code review: no SSH, source edits, commits, launches, or study-state changes.

## Required change: R1 remains incomplete

**MEDIUM — The unavailable-host branch suppresses a known k-limit alert (lines 113–116, 121).**

`ledger_gate()` reads and validates the ledger and computes `kmax` first. If `current_failed is None`, it then returns before executing the k comparison. That comparison depends exclusively on the validated ledger, so host failure does not make it unavailable.

Independent probes through both `ledger_gate()` and `main()` reproduced:

| Valid ledger maximum | Host failed IDs available | Host failed IDs unavailable |
| --- | --- | --- |
| primary k = 8 | required k alert emitted | k alert missing |
| guard k = 6 | required k alert emitted | k alert missing |
| primary k = 9 | k alert emitted | k alert missing |
| guard k = 7 | k alert emitted | k alert missing |

For the `main()` probes, injected remote output contained `FAILEDIDS primary-0001` with `LOSTPOP 0 0`. The mismatch correctly generated host UNKNOWN and cumulative UNKNOWN, wrote the receipt, printed JSON, and returned 2. Nevertheless, the receipt retained the known `ledger_max_k` of 8/6 or 9/7 without a `replacement k at limit-2` anomaly. The baseline's exact ledger AST still emits its old 9/7 alert after a host failure; suppression at those values is therefore a new regression.

This does **not** produce exit 0. The defect is loss of the independently established replacement-bank escalation, which R1 explicitly requires, during a concurrent host-data failure.

**Required fix:** evaluate the k alert immediately after successful ledger validation, before the unknown-current-failures return. Preserve that anomaly alongside the cumulative UNKNOWN anomaly. Add a regression with a valid ledger at primary 8 / guard 6 and `current_failed=None`, plus an injected `main()` host mismatch or runner failure. Verify the receipt and printed anomalies contain both the k alert and UNKNOWN, with exit 2, normally and under `-O`. Keep the 11/9 bank limits and 150/45 cumulative thresholds unchanged.

## Round-1 requirements verified

**R1 — partial.** Lines 23–25 explain the zero-based ruling correctly; line 121 uses `>=8` / `>=6`. The supplied 7/8 and 5/6 boundary tests pass with known host data. The early-return case above prevents full resolution.

**R2 — resolved.** Lines 107–112 read the ledger unconditionally and fail closed on missing/unreadable files, invalid JSON, and invalid schema. Validation requires an object with an events list; object lost/replacement descriptors; recognized, matching populations; matching integer cells within 0–49 or 0–17; population-compatible four-digit IDs; unique lost and replacement IDs; and explicit integer k within the bank. Booleans, floats, strings, nulls, missing values, negative k, and out-of-bank k are rejected. No validation relies on `assert`. Unavailable ledger totals/maxima are null rather than authoritative zeros. The outer gate boundary also protects the receipt from unexpected gate exceptions.

I reran all earlier malformed-ledger probes. In addition to the supplied gate tests, 30 cases were exercised through `main()` using injected host reads: all 22 supplied malformed documents, seven extra cases (null/missing lost descriptor, boolean/float/negative cell, duplicate replacement ID, unhashable population), and a missing ledger. Every case produced ledger UNKNOWN, a local receipt, matching printed/receipt anomalies, and return code 2. A directory used as the ledger also fails closed in the supplied unreadable-file test.

**R3 — resolved.** Lines 117–118 count per-population set unions of ledger lost IDs and the failed IDs collected across hosts. The one-loss overlap probe reports one loss instead of the baseline's two. Rechecking all 22 already-inventoried replacement-r1 failures reports 41 primary / 14 guard instead of the baseline's 57 / 20. Overlap counts/IDs are included in the receipt. A new guard failure on top of 44 ledger failures reaches 45 and alerts. The 149/150 and 44/45 boundaries remain correct. The committed fixture independently reproduces 55 events, totals 41/14, and population maximum k 2/1.

## FAILEDIDS, quoting, and effects

The new line 37 is operational and read-only: `grep -l` selects exit-file paths containing the producer's `"complete": false` flag; `sed` removes directories and the terminal `.json`; `tr` joins the basenames. `supervise.py` produces that boolean from process return code and local-completion-file existence, not game winner/loss. Its exit files contain descriptors, process metadata, stop/interference metadata, and completion status. The frozen `common.write()` serialization uses the exact space after the colon matched by this grep, and atomically replaces a `.tmp` file; the glob reads only `*.json`.

At line 147, J and phase are interpolated with `shlex.quote()`. The line quotes the directory portion and leaves only the intended `*.json` glob unquoted. Data emitted by command substitution is not evaluated again as shell commands. I executed only the EXITS/LOSTPOP/FAILEDIDS lines against temporary synthetic local exit files, using a job path containing spaces, a single quote, a semicolon, and literal `$(printf QUOTE_ERROR)`. They returned exactly `EXITS 3 2`, `LOSTPOP 1 1`, and the two expected failed basenames. No injected pathname text executed.

`failed_ids()` requires both fields, validates every ID with a full match, rejects duplicate IDs, parses exactly two integer counts, and requires both per-population cardinalities to match LOSTPOP. Empty FAILEDIDS with `0 0` is valid. Missing fields, wrong IDs/suffixes, duplicates, invalid integer forms, negative counts, and cardinality mismatches reject. In `main()`, rejection occurs before `x['lost']` is assigned, so `failed_known=False`; cumulative totals become UNKNOWN and the normal receipt/exit-2 path runs. The supplied end-to-end mismatch test and seven extra parser rejection probes confirm this. Sequential reads racing with newly added failed exits can conservatively yield UNKNOWN; the same SSH session is not an atomic snapshot.

No command kills processes, creates STOP files, operates services, dispatches work, alters the ledger, or changes game/study files. Remote commands are fixed reads: who/hostname, test, tr, find, ls, grep, wc, sed, head, and ps. The tool's reachable local write is line 209: create the health directory if necessary and write its JSON receipt. Other local operations read acknowledgments, ledger, copier receipts, process identity, hub acknowledgments, and completion/interference metadata. The `main()` refactor makes importing the candidate inert with respect to host reads and receipt writes. `commit_checkpoint.sh` is not invoked.

No game file is opened by checkpoint.py. The hub completion proofs inspected by the tool contain descriptors, process/timing information, game filenames/hashes, and interference metadata; the producer does not put winner/loss values into these proofs. The new ledger and failed-ID outputs expose operational block failures and replacement usage, not study match outcomes. This conclusion follows the producer schemas and reachable reads, not merely the `outcomes_read=False` marker.

## Tests and differential evidence

Commands run with the specified environment and scheduling priority:

```text
PYTHONDONTWRITEBYTECODE=1 nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B -m pytest -q -p no:cacheprovider /mpac/sdicks02/k4s-runner/run-r1/tools/candidate-r2/test_checkpoint.py
44 passed in 0.11s

PYTHONDONTWRITEBYTECODE=1 nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B -O -m pytest -q -p no:cacheprovider /mpac/sdicks02/k4s-runner/run-r1/tools/candidate-r2/test_checkpoint.py
44 passed, 1 warning in 0.11s
```

The `-O` warning is pytest's generic warning about disabled ordinary assertions. The suite uses explicit `ok()` raises, and the candidate uses `need()` raises, so these checks remain active.

For a meaningful baseline comparison, I executed the baseline's **exact ledger AST statements**, from immediately after the LED assignment through receipt cumulative-record construction, without importing or running its top-level SSH loop. An in-memory adapter supplied the fixture path, current failed-count lengths, and existing containers. It added `status='OK'` only to adapt successful legacy executions to the new test interface; it added no validation, thresholds, union arithmetic, or exception handling. The supplied test functions were reused, not rewritten against another implementation.

Of 35 selected supplied cases, the baseline had **8 passes / 27 failures**, while the candidate had **35 passes / 0 failures**. The failures comprise the two required 8/6 alert boundaries, 22 malformed-ledger cases, the missing/unreadable-ledger test, and two overlap regressions. Six controls (real fixture, four cumulative boundaries, and a fresh current-phase failure) and the two below-limit k cases pass on both. Failures came from wrong values/accepted invalid data or legacy uncaught exceptions, not missing new API attributes. The baseline missing-file test stops at its first failed assertion; its directory behavior is separately apparent from the unchanged read operation. All auxiliary Python probes also used `nice -n 19` and the existing k4s-freeze interpreter.

The supplied tests are useful: they cover numerical boundaries, strict validation, unions, independent per-cell maxima, and receipt/JSON/exit behavior with injected host calls. Their key gap is combining an already-at-limit ledger with host UNKNOWN, as described in the required change.

## Other risks and limits

- **Inherited remote I/O limitation, nonblocking for this diff:** the grep/count pipelines suppress stderr and do not propagate grep read errors. A missing synthetic exits directory produced `EXITS 0 0`, `LOSTPOP 0 0`, and empty FAILEDIDS, which the parser accepts. Thus the new cross-check fails closed on missing output fields or inconsistent data, but cannot distinguish mutually consistent zero results from a shared I/O failure. The baseline LOSTPOP/EXITS reads already have this limitation; the new FAILEDIDS read shares it. A future hardening should distinguish grep no-match from read failure and check the exits directory. No real job directory was altered to test this.
- **Smoke compatibility:** phase validation still permits smoke, but the new ID parser deliberately accepts only primary/guard. A failed `smoke-####` exit therefore yields UNKNOWN rather than a primary/guard cumulative value. This remains nonhealthy, but the supplied suite does not cover actual smoke failures. It is outside the replacement-r2 acceptance blocker above.
- The ledger validator checks the health-gate schema, not full frozen schedule canonicality or evidence hashes. Synthetic threshold fixtures likewise test gate arithmetic rather than real replacement-chain construction. Those stronger producer/audit checks remain separate responsibilities.
- Receipt write failure or malformed acknowledged-events input can still prevent a normal receipt. These limitations predate the candidate; no claim of universal failure recovery is made here.

No SSH, remote execution, source edits, or commits occurred. Tests used temporary local fixtures and injected host/process/clock data; bytecode and pytest cache writes were disabled. The requested review report is the only persistent artifact written by this review. After the known-k/unknown-host regression is fixed and verified normally and under `-O`, no other blocking change is identified for this candidate.
