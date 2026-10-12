# Independent review: K4S checkpoint gate, round 3

**Verdict: APPROVE.** R1 is now fully resolved: a validated ledger's k escalation survives unavailable host failed-ID data and remains alongside cumulative UNKNOWN. R2 and R3 stay resolved. No new host mutation or study-outcome exposure was found. Approval applies to the reviewed candidate, not the unchanged ordinary checkpoint tool.

## Scope and artifact identity

Reviewed immutable commit **af6e1e62** in /mpac/sdicks02/repos/clasher, under reports/explore/k4s-confirm/run-r1/. The active checkout is at a different commit; repository objects supplied the authority. The standalone files under /mpac/sdicks02/k4s-runner/run-r1/ were verified byte-for-byte against those objects before testing. Read the prior independent r1 and r2 reports.

Verified SHA-256 values:

| Artifact | SHA-256 |
| --- | --- |
| Candidate tools/candidate-r2/checkpoint.py | aa898ab2db74e519a3682a14791a6bbc99a5d3abcdd15928c7722f0cde80441a |
| Tests tools/candidate-r2/test_checkpoint.py | e1ae76e848f3018e23f06fe52c887c6856e5b331a57d86be8afbbf040a2ea6b5 |
| Fixture tools/candidate-r2/fixtures/blind-ledger-r2.json | 4a56abf356446c3cae6935674ffe4c92273ff8a91f689a097eaec76c935d5510 |
| Full diff reviews/CHECKPOINT-DIFF-r3-candidate.diff | 948a92c38f28700490e20bcd1c98c30ee89e7c81e0430ca11e670064aa57095b |
| Incremental diff reviews/CHECKPOINT-DIFF-r3-incremental.diff | a69ec1f26d60d1bc12552964c8c9f0dc91db0f1af41ac266f30e5cf593c35da4 |
| Previous candidate, f57fa318 | bb5d768572ef93f2cf5094715fdbdab658d53ac8cc2a357df355a86b29072b0b |
| Original baseline, b5530e98 | 40cca7725def711070b9499a3226a79836a89482c400e1e3bddd6fedd19a64d2 |

Both supplied diffs' hunks exactly match independently generated unified diffs from the specified immutable versions; only their descriptive filename headers differ from default generated headers.

## Incremental scope

The candidate's sole executable change is moving the existing kmax primary >= 8 / guard >= 6 comparison immediately after successful ledger validation, ahead of the host-dependent early return (candidate lines 114–119). The expression and alert text are unchanged. The other candidate changes are one documentation line and one explanatory comment. No validation, host command, arithmetic, threshold constant, receipt field, or I/O target changed.

When both k and cumulative-count thresholds are exceeded, the k anomaly now precedes the cumulative-count anomaly. Both still appear and still cause exit 2.

The previous test file is an unchanged prefix of the new file. The appended tests add exactly eight parameterized cases: five direct gate cases and three injected main() failure cases. Across the candidate directory, the commit changes only the candidate and test file. Bank maxima remain 11/9; k alert boundaries remain 8/6; cumulative boundaries remain 150/45.

## R1 — resolved, including host failure

Independent probes reran the four r2 rows through the actual ledger_gate() and main() functions:

| Valid ledger maximum | Gate: IDs available | Gate: IDs unavailable | Main: healthy host reads | Main: injected host failures |
| --- | --- | --- | --- | --- |
| primary k = 8, guard k = 0 | k alert | k alert + cumulative UNKNOWN | k alert, exit 2 | 12/12: k alert + cumulative UNKNOWN, exit 2 |
| primary k = 0, guard k = 6 | k alert | k alert + cumulative UNKNOWN | k alert, exit 2 | 12/12: k alert + cumulative UNKNOWN, exit 2 |
| primary k = 9, guard k = 0 | k alert | k alert + cumulative UNKNOWN | k alert, exit 2 | 12/12: k alert + cumulative UNKNOWN, exit 2 |
| primary k = 0, guard k = 7 | k alert | k alert + cumulative UNKNOWN | k alert, exit 2 | 12/12: k alert + cumulative UNKNOWN, exit 2 |

Each row's 12 injected cases comprise FAILEDIDS/LOSTPOP mismatch, runner timeout, return code 255 with empty stdout, and missing FAILEDIDS, each affecting only 127x03, only 127x04, or both hosts. These were synthetic runner responses: no SSH command was executed.

Every failure case wrote the temporary local health receipt and printed one JSON result. Receipt and printed anomalies/summary agreed. The receipt retained the validated ledger maxima, reported null primary/guard cumulative totals and UNKNOWN status, and contained exactly one k alert plus the cumulative UNKNOWN anomaly and host failure anomalies.

Additional controls passed: simultaneous primary 8 / guard 6 behaves the same; primary 7 / guard 5 emits no k alert, returns 0 with healthy host reads, and returns 2 with cumulative UNKNOWN under all 12 injected host failures.

For a differential control, the exact previous candidate source from f57fa318 was executed in an inert module with the same injected fixtures. It emitted the k alert in 4/4 known-ID gate cases and 4/4 healthy-host main cases, but in 0/4 unknown-ID gate cases and 0/48 unknown-host main cases. The new candidate emits the alert in all corresponding cases. Thus the probes directly distinguish the fix from the r2 regression.

## R2 and R3 — remain resolved

**R2:** the supplied validation tests pass. I also reran all 22 supplied malformed documents, the seven extra r2 probes (null/missing lost descriptor; boolean, float and negative cell; duplicate replacement ID; unhashable population), a missing file, and a directory used as the ledger. Each of these 31 inputs was exercised through the gate with both known and unknown current failures, then through main() with healthy injected host reads. All fail closed with ledger UNKNOWN and null unavailable totals/maxima. Main produces the receipt, matching printed anomalies, and exit 2. No invalid ledger produces a k alert based on unvalidated data. Validation uses explicit raises and stays active under -O.

**R3:** independent gate and main probes confirm that one inventoried loss plus the same current failure remains one loss; adding one distinct current failure makes two. Rechecking the 22 already-inventoried replacement-r1 failures still reports 41 primary / 14 guard, with overlap 16/6. Main fixtures also duplicate a failed ID across hosts to verify that the union still counts it once. No false cumulative escalation occurs. Independent 149/150 primary and 44/45 guard boundaries pass through both functions, as does a fresh guard failure added to 44 ledger losses.

The committed fixture still reproduces 55 events, totals 41/14, and population maxima 2/1; the supplied independent per-cell reduction check also passes.

## Effects and outcome blindness

The incremental change adds no I/O. Reinspection of the full candidate confirms that its remote template contains only health reads and output formatting. Namespace/phase interpolation remains shell-quoted. There is no process kill, STOP creation, service operation, launch, dispatch/ledger modification, game write, commit, or push reachable from this tool.

Its local mutation remains creation of the health directory if necessary and writing the health JSON receipt (line 211). Importing the candidate does not execute host checks or write receipts.

No game file is opened by the checkpoint tool. I rechecked the immutable producer schemas: supervise.py derives failed-exit complete from process return code and local-completion-file existence (lines 76 and 93); progress and exit records contain operational metadata. The completion proof in run.py (line 377), augmented by the supervisor with interference metadata, contains descriptors, timing/placement and game filenames/hashes, without winner/loss values. The checkpoint reads only that proof's interference data on the hub. The relevant producer files are unchanged from the reviewed r2 commit. Operational failed-block counts and replacement k are not study match outcomes.

## Validation and limits

Both required test runs used the specified scheduling priority and existing freeze interpreter, with bytecode and pytest cache disabled:

    PYTHONDONTWRITEBYTECODE=1 nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B -m pytest -q -p no:cacheprovider /mpac/sdicks02/k4s-runner/run-r1/tools/candidate-r2/test_checkpoint.py
    52 passed in 0.13s

    PYTHONDONTWRITEBYTECODE=1 nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B -O -m pytest -q -p no:cacheprovider /mpac/sdicks02/k4s-runner/run-r1/tools/candidate-r2/test_checkpoint.py
    52 passed, 1 warning in 0.12s

The optimized run's warning is pytest's generic warning about disabled ordinary assertions. Candidate validation and the supplied tests' ok() checks use explicit raises.

The separate probes also ran using nice -n 19 and the freeze interpreter, normally and under -O: 82 gate calls and 117 main calls per mode, all passing. Their checks use explicit raises. Fixtures, receipt destinations, runner, process identity and clock were local/injected; temporary directories were cleaned up. The exact-r2 differential control also used the freeze interpreter at nice 19.

The inherited limitations documented in r2 remain unchanged and are not new blockers: mutually consistent zero grep/count outputs can hide shared remote I/O failures; failed smoke IDs yield UNKNOWN under the primary/guard parser; ledger validation is not a full schedule/evidence-hash audit; malformed acknowledgments or receipt-write failure can still prevent normal receipt completion. This approval makes no stronger recovery guarantee.

The ordinary run-r1/tools/checkpoint.py in af6e1e62 still matches the original baseline. Approval is for tools/candidate-r2/checkpoint.py identified above; promoting it is outside this read-only review.

No SSH, real host execution, outcome-data reads, source edits, checkout changes, or commits occurred. Bytecode/cache writes were disabled. This requested review report is the only persistent artifact written by the review. No approval conditions or further blocking changes are identified.
