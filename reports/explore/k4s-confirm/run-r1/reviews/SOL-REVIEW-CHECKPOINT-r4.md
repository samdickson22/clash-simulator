# Independent review: K4S checkpoint gate, round 4

**Verdict: REQUEST_CHANGES.** The candidate fixes audit r3 F1 for valid inputs, and the r1–r3 ledger, k and union fixes remain intact. Two new remote readers can turn malformed metadata into valid-looking values and return **exit 0 with no anomalies**. Those cases violate the change's fail-closed requirement. No explicit host or study-state mutation, quoting vulnerability, or study-outcome exposure was found.

Reviewed and decided at **2026-10-12T11:49Z**, before the requested approximately 13:15Z deadline.

**Scope and identity.** Reviewed immutable commit **5304fc0d** in /mpac/sdicks02/repos/clasher, under reports/explore/k4s-confirm/run-r1/. Read SOL-REVIEW-CHECKPOINT-r1.md, r2.md and r3.md and ROUND-r3-AUDIT.md F1 first. The active main checkout is at another commit; immutable repository objects supplied the authority. The standalone candidate, tests, fixture and diffs under /mpac/sdicks02/k4s-runner/run-r1/ match the specified commit byte-for-byte.

Verified SHA-256 values:

- Candidate tools/candidate-r4/checkpoint.py: cae34ed533cce24a424a9f90cbdedfb18dac67638d019c14e59fb6b16c18577b.
- Deployed baseline tools/checkpoint.py: aa898ab2db74e519a3682a14791a6bbc99a5d3abcdd15928c7722f0cde80441a.
- Candidate tests: fd2f32be200d95ce01c0d6e22cc22b6d7d5264f984d1b554e88658b3970812fd.
- Baseline tests: e1ae76e848f3018e23f06fe52c887c6856e5b331a57d86be8afbbf040a2ea6b5.
- Candidate diff: 1453e5b9de5b07bdb4eefc65ba8fae88cb753d9acf9183e78ea6117525e74363.
- Test diff: cb1dbcdd634b9d1c7ed42b1488a456a2ac8b5f49eedc083c36a25354500fda09.
- Ledger fixture: 4a56abf356446c3cae6935674ffe4c92273ff8a91f689a097eaec76c935d5510.

Both supplied diffs were independently applied **in memory** to their immutable baselines and exactly reconstruct the candidate bytes. No patch was applied to a filesystem checkout. Line numbers below refer to the candidate.

**R4-1 — MEDIUM: LAUNCHDISPATCH accepts an overlong or malformed launch hash as an exact match (line 45; comparison at lines 198–199).**

The second grep searches for a 64-character hexadecimal **substring**, and head -1 selects its first match. It does not validate the complete field value or parse launch.json. Let H be the valid history/dispatch SHA. With this valid JSON:

    {"dispatch_sha256": "<H>0"}

the actual candidate shell line emits LAUNCHDISPATCH H. Main compares that truncated value to H and accepts it. An independent shell-to-main probe, with otherwise healthy synthetic host data and completed counts 3/2, returned **0**, wrote the normal health receipt, and printed **anomalies=[]**. A 128-character value H+H behaves identically. A non-JSON file containing only the matching quoted key/value fragment also passes.

These are not probes that merely inject a forged LAUNCHDISPATCH value: I executed the **exact formatted candidate shell extraction** against temporary local launch.json files and passed its output into the actual main(). All three false passes reproduce normally and under -O.

**Required:** validate launch.json as an object and require its dispatch_sha256 to be an explicit string that fully matches the 64-hex format; compare the entire value to history without truncation or first-substring selection. Missing, unreadable, malformed or nonmatching launch metadata must produce an anomaly and exit 2. Add tests that exercise the actual extraction for H+one hex character, H+H, malformed JSON, missing/short/different SHA, and a valid exact match. Preserve read-only, outcome-blind operation.

**R4-2 — MEDIUM: SUPEXITN counts strings and objects as block lists (line 44; checks at lines 209–216).**

The Python reader calls len() without validating that completed, failed and unstarted are lists. Thus:

    {"reason": null, "completed": "abc", "failed": "", "unstarted": ""}

emits SUPEXITN 3 0 0. For a host dispatched three blocks with three complete.json files, every new check passes: the sum is three, completed equals the directory count, and unstarted is zero. The malformed receipt is accepted with **exit 0 and anomalies=[]**. A completed object with three keys and empty failed/unstarted objects also passes, as does a string completed field combined with actual empty lists.

Again, these three cases were run through the **actual candidate shell reader**, then main(), with a valid history/dispatch/launch binding and healthy second host. All reproduce normally and under -O. The strings and objects do not provide valid completed/failed/unstarted block collections; counting their characters or keys is not validated exit accounting.

**Required:** explicitly require all three collections to be lists before counting them; reject missing, null, scalar, string and object values. Use explicit checks that survive -O and emit an unambiguous unreadable/invalid signal that main() converts into an anomaly and exit 2. Also validate received counts as nonnegative integers. Add extraction-to-main tests for these schema errors, alongside valid empty/nonempty lists. Full schedule canonicality is outside this narrow request.

**Correct behavior verified.** The history lookup requires exactly one matching phase entry, a traversal-free JSON filename and a full lowercase 64-hex SHA. It reads and hashes the named dispatch bytes before deriving per-host row counts. The history is a list of phases; “exactly one” correctly refers to the entry for the checked phase, rather than the whole history.

I exercised 28 additional history/dispatch rejection cases through main(), including absent/directory/unparseable history, wrong history type, absent/duplicate phase entries, missing/unsafe/nonstring filenames, missing/short/long/uppercase/nonhex/mismatched SHA, missing/directory dispatch, malformed dispatch JSON, invalid blocks and malformed/missing host fields. All generated expected-count UNKNOWN, a receipt, matching printed anomalies and exit 2. Missing launch output, short SHA and a different SHA also fail closed. Missing/unparseable exit counts and count arithmetic mismatches are rejected.

Using only immutable history and dispatch bytes, expected_counts() independently reproduces:

- reporting: 1950 / 1950 on 127x03 / 127x04;
- replacement-r1: 1754 / 1754;
- replacement-r2: 555 / 554;
- replacement-r3: 286 / 289.

The committed history has no r4 entry yet. Synthetic replacement-r3, replacement-r4 and replacement-r27 fixtures demonstrate that the check is not restricted to the old map: a null exit with 2 completed and 1 unstarted against an expectation of 3 raises both the short-completion and unstarted anomalies. A valid full-completion null exit passes. The exact deployed aa898ab2 source, executed inertly with the same replacement-r4 fixture, returns **0**; the candidate returns **2**. This directly distinguishes the F1 fix from the baseline.

**R1–R3 regressions.** The ledger validator, ledger gate and failed-ID parser are unchanged by the diff. I nevertheless reran the earlier probes normally and under -O:

- All 31 malformed/missing/unreadable ledger cases from r3: the 22 supplied cases, seven extra descriptor/cell/duplicate-ID/unhashable-population cases, a missing file and a directory. Each fails closed through the gate with known and unknown host failures, and through main(), preserving UNKNOWN/null values, receipt/stdout agreement and exit 2.
- Primary k=8 and 9, guard k=6 and 7, simultaneous 8/6, and below-limit 7/5. The known k alert survives FAILEDIDS/LOSTPOP mismatch, timeout, rc255 and missing FAILEDIDS on either host or both: 72 injected failure combinations. UNKNOWN and the independently established k alert coexist.
- The real fixture remains 55 events, primary/guard losses 41/14 and maximum k 2/1; an independent per-cell reduction agrees.
- One inventoried/current loss remains one; a distinct current loss makes two. Rechecking the 22 inventoried replacement-r1 failures remains 41/14 with overlap 16/6. Repeated failed IDs across hosts are counted once.
- Primary 149/150 and guard 44/45 boundaries remain correct through gate and main(); a fresh guard failure added to 44 reaches 45. Bank limits remain 11/9, k alerts 8/6, and cumulative alerts 150/45.
- Seven additional failed-ID parser rejection cases still reject.

Per interpreter mode, the independent driver made **83 ledger_gate calls, 175 main calls, seven parser rejection checks, 28 history/dispatch rejection checks, and 13 synthetic shell executions**. The 175 main calls include the deliberate false-pass demonstrations and the baseline differential control. Every probe used explicit raises for its checks.

**Remote quoting, effects and outcome blindness.** Both new lines only read operational launch/exit metadata and print a SHA or counts. The exit reader uses json.load(open(...)) without a write mode. J and P remain assigned with shlex.quote(); all new file arguments are double-quoted. I executed the exact EXITS/LOSTPOP/FAILEDIDS and new metadata excerpts against a temporary path containing spaces, a single quote, a semicolon and literal $(printf QUOTE_ERROR). No injected pathname text executed; the valid control produced the expected failed IDs, counts and SHA. Before/after hashes of all synthetic files were unchanged by every shell execution. The parsing defects above are separate from quoting.

Reinspection found no reachable kill, STOP creation, service operation, launch, dispatch/ledger modification, game write, commit or push. Importing the tool does not run its host loop. Its explicit local mutation remains creation of the health directory and writing the health JSON receipt at line 260; it is therefore not literally filesystem-read-only, but that operational receipt does not alter study state.

I rechecked the immutable producer schemas: supervise.py line 55 supplies the launch SHA; lines 76/93 derive operational block completion from process return code and local-completion-file existence; line 119 writes completed/failed/unstarted descriptor lists. run.py's completion proof contains descriptors, timing/placement and game filenames/hashes; checkpoint reads only its interference data on the hub. No game outcome file, winner/loss value or statistical contrast is read. The new SHA and exit counts are outcome-blind.

**Tests and limits.** Required commands:

    PYTHONDONTWRITEBYTECODE=1 nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B -m pytest -q -p no:cacheprovider /mpac/sdicks02/k4s-runner/run-r1/tools/candidate-r4/test_checkpoint.py
    74 passed in 0.19s

    PYTHONDONTWRITEBYTECODE=1 nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B -O -m pytest -q -p no:cacheprovider /mpac/sdicks02/k4s-runner/run-r1/tools/candidate-r4/test_checkpoint.py
    74 passed, 1 warning in 0.19s

The optimized warning is pytest's generic warning about ordinary assertions. The supplied ok() checks and candidate validation use explicit raises.

The suite is meaningful for numerical boundaries, ledger schema, unions, dispatch binding, exit accounting and receipt/exit behavior. Its new main() cases inject already-extracted LAUNCHDISPATCH and SUPEXITN strings, so they do **not** test how remote bytes become those values. That gap hides both blockers. The test called “r4_shape” also runs replacement-r2; my separate later-phase and baseline controls cover actual phase selection.

The inherited r3 limitations remain: mutually consistent grep/count zeros can hide shared remote I/O errors, ledger validation is not a full schedule/evidence-hash audit, and malformed acknowledged-events input or receipt-write failure can prevent normal receipt completion. They were not introduced by this diff and are not additional remediation requirements here.

No SSH, real host execution, reporting-outcome reads, source edits, checkout changes or commits occurred. All shell executions used synthetic local metadata only. Tests/probes used temporary local fixtures and injected host/process/clock data; bytecode and pytest caches were disabled. This requested review report is the only persistent output written by this review.

Approval requires correcting R4-1 and R4-2 and verifying the extraction-to-main regressions normally and under -O. This verdict applies only to the identified candidate; deployment is outside this review.
