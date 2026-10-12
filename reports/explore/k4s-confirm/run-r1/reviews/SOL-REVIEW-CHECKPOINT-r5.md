# Independent review: K4S checkpoint gate, round 5

**Verdict: REQUEST_CHANGES.** R4-1 and R4-2 are fixed, and the r1–r4 regression checks pass. One remaining failure-handling defect prevents approval: a Python reader that emits a valid payload and then fails can still produce **exit 0 with anomalies=[]**. The requested fail-closed verification therefore remains incomplete. Both supplied test runs pass **111/111**.

**Scope and identity.** Reviewed immutable commit **2903d69e** in /mpac/sdicks02/repos/clasher, under reports/explore/k4s-confirm/run-r1/. The active checkout is at another commit; repository objects supplied the authority. Read the independent r1–r4 reports. The standalone candidate, tests, fixture, baseline and supplied diffs under /mpac/sdicks02/k4s-runner/run-r1/ match the specified commit byte-for-byte. Candidate/test identity was rechecked after validation.

Verified SHA-256 values:

- Candidate tools/candidate-r4/checkpoint.py: 96df38619b693317e316779403e4435146d45c4963d8de0c944e170a2926e078.
- Candidate tests: 4099bd962845dea36d632814b3fa3c345e333fcbb2acfaa1dab95e1514f63efd.
- Baseline tools/checkpoint.py: aa898ab2db74e519a3682a14791a6bbc99a5d3abcdd15928c7722f0cde80441a.
- Full candidate diff: 33c7e91c90121983868bcd6708141b2744a07b27ec95b50ee94af5adf2b5048b.
- Incremental candidate diff: b104e0650465837a3fea31de2f8d66ed70600655189815f83aae49277d7b4966.
- Tests diff: a60438faae25576ebe69d325d78b87ccb3bb9ced8797157db798fefd4dad0f38.
- Ledger fixture: 4a56abf356446c3cae6935674ffe4c92273ff8a91f689a097eaec76c935d5510.

All three supplied diffs were independently applied **in memory** to their immutable baselines and exactly reconstructed the candidate/test bytes. No checkout or source file was changed. Line numbers below refer to the candidate.

**R4-1 — resolved.** The remote reader requires a JSON object with a string dispatch_sha256 fully matching lowercase SHA64. Main independently validates the full format and compares the whole value at lines 223–225. I reran the exact r4 shell-to-main probes: H+one hex character, H+H, and a non-JSON matching key/value fragment. All now emit LAUNCHDISPATCH INVALID and return 2 with matching receipt/printed anomalies. The immutable r4 candidate still returns 0 for all three controls.

Additional extraction-to-main probes reject short, uppercase, newline-suffixed, different, numeric, null, boolean, list and object SHA values; empty, non-object, missing-key and trailing-garbage JSON; absent files; and directories. A valid exact SHA passes.

**R4-2 — resolved.** The exit reader counts only when completed, failed and unstarted are all lists. I reran the r4 string, object and string-with-lists cases through the exact shell extraction and main(). Each now emits SUPEXITN INVALID and produces receipt-backed exit 2; the immutable r4 candidate still passes each case.

Independent probes reject each collection when missing, null, string, integer, boolean or object, along with empty/malformed/non-object JSON and a directory. The supplied extraction tests verify valid full and empty lists and valid counts with failures/unstarted blocks. exit_counts() accepts exactly three ASCII nonnegative decimal tokens; signs, negatives, decimals, Unicode digits, wrong token counts and INVALID are rejected. These checks survive -O.

**R5-1 — MEDIUM: nonzero Python status can be discarded after valid stdout (lines 46–62; parse at lines 73–76).**

Both readers use this structure:

    echo "KEY $(python3 -c '...' "$file" 2>/dev/null || echo INVALID)"

If Python prints its valid payload and subsequently exits nonzero, the fallback appends INVALID on a new line. The shell emits, for example:

    SUPEXITN 3 0 0
    INVALID
    LAUNCHDISPATCH H
    INVALID

Here H denotes the complete matching 64-character dispatch SHA. parse() retains the valid SUPEXITN/LAUNCHDISPATCH values and treats INVALID as a separate, unused key. The outer echo succeeds. Main sees valid metadata, produces the normal receipt and returns **0 with anomalies=[]**, despite both reader failures having triggered the fallback.

I reproduced this using the exact formatted candidate shell extraction against healthy synthetic launch/exit metadata. Failure injection shadowed python3 with a shell function that passed the original reader program and file argument to the freeze interpreter, appending an uncaught RuntimeError after the original program:

    python3() {
      review_python_code="$2
    raise RuntimeError()"
      /mpac/sdicks02/venvs/k4s-freeze/bin/python -B -c "$review_python_code" "$3"
    }

This changes only the in-memory failure-injection command, not any reviewed file. The original reader executes and prints before the injected exception. A second control runs the original reader unchanged and then returns status 73. Launch-only, exit-only and simultaneous failures all false-pass, in both /bin/bash and /bin/sh, normally and with the main driver under -O: **12/12 false passes per mode**. Every false pass writes a receipt agreeing with stdout.

This is a reader-process failure-injection test with valid metadata. The unmodified reader ordinarily finishes after its print. The defect is that the explicitly detected nonzero status does not invalidate stdout already emitted by that process.

**Required:** capture the reader output and status before emitting the keyed record. On any nonzero status, discard captured stdout and emit exactly KEY INVALID. An if/else around the command substitution can do this without adding remote writes or outcome reads. Preserve complete-payload validation in main(). Add extraction-to-main regressions for valid stdout followed by nonzero termination, independently for both readers, normally and under -O. They must produce an anomaly, matching receipt/stdout and exit 2.

**Other Python failures and quoting.** Missing python3, a nonzero execution with no stdout, an import exception before the reader try block, malformed JSON and read exceptions all fail closed in my probes. Both readers use open() in its default read mode and print only a SHA, three lengths or INVALID. J/P remain shlex.quote() assignments; file arguments remain double-quoted; doubled regex braces correctly become {64} after template formatting.

Exact extraction probes ran against a path containing spaces, a single quote, a semicolon and literal $(printf QUOTE_ERROR), with both shell implementations. No pathname expression executed. Before/after bytes of all synthetic metadata files were identical. The failure above concerns output/status handling.

**R1–R4 regressions.** AST comparison confirms validate_ledger(), ledger_gate(), failed_ids() and expected_counts() are unchanged from r4. The r4 tests are an unchanged prefix of the r5 tests. Independent probes normally and under -O confirm:

- All 31 prior malformed/missing/unreadable ledger cases fail closed through the gate with known/unknown host data and through main(), preserving UNKNOWN/null values, receipts and exit 2.
- Primary k=8/9, guard k=6/7, simultaneous 8/6 and below-limit 7/5 remain correct. Known k alerts survive mismatch, timeout, rc255 and missing FAILEDIDS on either or both hosts: 72 failure combinations per mode.
- The fixture remains 55 events, 41/14 losses and max k 2/1, agreeing with an independent per-cell reduction.
- Overlapping losses count once; distinct losses count twice. Rechecking the inventoried replacement-r1 failures remains 41/14, including duplicated current IDs across hosts.
- Primary 149/150 and guard 44/45 boundaries, including a new guard loss added to 44, remain correct through gate and main(). Bank limits remain 11/9.
- Seven failed-ID parser rejection cases and 28 history/dispatch rejection cases remain closed.
- Immutable dispatch counts remain reporting 1950/1950, replacement-r1 1754/1754, replacement-r2 555/554 and replacement-r3 286/289.
- Synthetic replacement-r3, replacement-r4 and replacement-r27 exact-completion exits pass; null-reason short exits retain both short-completion and unstarted anomalies.

Per interpreter mode, completed independent drivers exercised **83 ledger-gate calls, 262 main calls and 111 shell extractions**, plus parser checks. These totals include the six r4 differential controls and the twelve R5-1 false-pass demonstrations.

**Effects and outcome blindness.** Reinspection found no reachable remote mutation, process kill, STOP creation, service operation, launch, dispatch/ledger change, game write, commit or push. The local health-directory/receipt write remains part of main(). Importing the candidate does not execute its host loop.

The immutable supervise.py and run.py producers are unchanged from r4. Launch SHA and completed/failed/unstarted lists describe dispatch/process accounting. Completion proofs contain descriptors, timing/placement and game filenames/hashes; checkpoint reads their interference metadata on the hub. No game outcome file, winner/loss value or statistical contrast is read by the new readers.

**Tests and limits.** Required commands:

    PYTHONDONTWRITEBYTECODE=1 nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B -m pytest -q -p no:cacheprovider /mpac/sdicks02/k4s-runner/run-r1/tools/candidate-r4/test_checkpoint.py
    111 passed in 6.75s

    PYTHONDONTWRITEBYTECODE=1 nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B -O -m pytest -q -p no:cacheprovider /mpac/sdicks02/k4s-runner/run-r1/tools/candidate-r4/test_checkpoint.py
    111 passed, 1 warning in 6.76s

The optimized warning is pytest's generic assertion warning. Candidate validation and test ok() checks use explicit raises. The 37 added cases meaningfully test extraction-to-main behavior and fix the prior coverage gap; they do not exercise valid partial stdout followed by reader failure.

Inherited limitations remain unchanged: mutually consistent grep/count zeros can hide shared remote I/O failures; ledger validation is not a full schedule/evidence-hash audit; malformed acknowledgments or receipt-write failure can prevent normal receipt completion. They are not additional remediation requests.

No SSH, real-host execution, outcome-data reads, source edits, checkout changes or commits occurred. Tests/probes used temporary local fixtures and injected runner/process/clock data; bytecode and pytest cache writes were disabled. This requested review report is the only persistent output written by the review.

Approval requires R5-1's narrow status/output fix and its extraction-to-main regressions. Deployment is outside this review.

