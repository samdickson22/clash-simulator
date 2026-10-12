# Independent review: K4S checkpoint gate, round 6

**Verdict: APPROVE.** R5-1 is fixed. The stricter parser accepts the legitimate template output exercised here, including optional lines and missing optional keys. No regression in the r1–r5 requirements, remote mutation, or study-outcome exposure was found. Approval applies only to the identified candidate; promotion and deployment are outside this review.

## Scope and identity

Reviewed immutable commit **1a44b8e8**, under `reports/explore/k4s-confirm/run-r1/` in /mpac/sdicks02/repos/clasher. The active checkout is at another commit; Git objects supplied the authority. Candidate, tests, fixture, baseline, and all three supplied diffs in /mpac/sdicks02/k4s-runner/run-r1/ matched those objects byte-for-byte. Read all five prior independent checkpoint reviews, including the specified round-5 report.

Verified SHA-256 values:

- Candidate `tools/candidate-r4/checkpoint.py`: `05d0908f67b30a4e84983b80b1d46ccf526b3cfec99dffc634e0fb36f94c9368`.
- Tests `tools/candidate-r4/test_checkpoint.py`: `536a5b2d4bd88584bdb641ec2d4be96ae097042aec927a0d25ed37867b58df1a`.
- Fixture: `4a56abf356446c3cae6935674ffe4c92273ff8a91f689a097eaec76c935d5510`.
- Baseline `tools/checkpoint.py`: `aa898ab2db74e519a3682a14791a6bbc99a5d3abcdd15928c7722f0cde80441a`.
- Full candidate diff: `0eaa74ab0641fe03c00f8ac4d5c3b5c3850266e8177ecacd859349353d7f8ae2`.
- Incremental candidate diff: `bd284c0ccc02791f6e45a7a63b20bf2353d9daa167ac04ae17c6ca30537e433e`.
- Incremental tests diff: `acc34eff20e042b9badaeab87eb20c3ad80a211baa5754e1f661114e6d33f83d`.

All three diffs were applied independently **in memory** to their immutable baselines and exactly reconstructed the candidate/test bytes. No checkout or source file changed. Candidate/test identity was rechecked before writing this report. Candidate line references follow.

## R5-1 — resolved

Both readers now capture stdout and inspect the command-substitution status before emitting a keyed line (lines 47–62). A nonzero status discards captured stdout and emits exactly `SUPEXITN INVALID` or `LAUNCHDISPATCH INVALID`. Main still independently validates those payloads.

I reran the exact round-5 failure mechanisms using the **full formatted REMOTE template**, unfiltered stdout, and real main(), against healthy synthetic launch/exit metadata:

1. A `python3` shell function executes the original reader program using the freeze interpreter, appending an uncaught `raise RuntimeError()` after the original program. Thus the real reader prints its valid payload before exiting nonzero.
2. A status-73 control executes the original reader unchanged, then returns 73.

Each mechanism failed launch only, exit only, and both readers, under **/bin/bash and /bin/sh**, with the driver and readers **normally and under -O**. Per interpreter mode, **12/12 candidate cases return 2**, with the relevant invalid-SHA/count anomaly and matching receipt/printed anomalies. Failed readers emit one keyed INVALID record, retain no valid payload, and leave no stray INVALID line.

For differential evidence, the exact immutable r5 candidate from **2903d69e**, SHA-256 beginning **96df3861**, was run through the same full-template/main fixtures: **12/12 still return 0 with anomalies=[] per mode**. These controls reproduce R5-1 and distinguish its fix from a probe that simply makes an otherwise healthy fixture fail.

The new parser also rejects the stray and duplicate record forms independently. Its checks use explicit raises and remain active under -O.

## Parser compatibility — verified

The allowlist at lines 74–75 equals the complete set of keys emitted by the template:

`WHO STOPFILES PROGRESS COMPLETE HUBACK EXITS LOSTPOP FAILEDIDS STOPREASON SUPEXIT SUPEXITN LAUNCHDISPATCH SRCRECEIPT SUPPROC`.

A static enumeration of every keyed echo and a dynamic union of full-template output both equal this 14-key set. No emitted key is omitted.

The parser enforces **at most one occurrence of each present key**, not mandatory presence of every allowlisted key. That is correct for the template: STOPREASON, SUPEXIT, SUPEXITN, and SUPPROC are conditional. Empty FAILEDIDS and other empty payloads still parse as keyed records. A final newline does not create an empty record.

Per interpreter mode, twelve unfiltered template-to-main profiles covered both shells and:

- healthy running hosts;
- supervisors exited with null reason and exact dispatch completion, retaining launch PID metadata while ps returns no live state;
- inactive supervisors without an exit receipt;
- STOPREASON present on running and exited hosts;
- inactive hosts with STOPREASON and no supervisor PID, omitting SUPPROC.

All output parsed without unknown-key, empty-key, or duplicate-key errors. Healthy running and exact-completion exited profiles returned **0 with anomalies=[]**. Inactive/stopped profiles returned **2 for their operational health conditions**, with matching receipt/stdout anomalies, rather than an invented parser failure. All 14 keys were exercised. Process/login output and job metadata were synthetic; no SSH runner executed.

Unknown keys, interior empty lines, and duplicate keys are malformed protocol records, not optional template output. Supplied tests verify that these become receipt-backed anomalies with exit 2.

## R1–R5 regressions — pass

AST comparison with r5 shows that **parse() is the only changed function**. In particular, main(), validate_ledger(), ledger_gate(), failed_ids(), expected_counts(), and exit_counts() are unchanged. The incremental executable changes outside parse() are confined to the two REMOTE readers and KEYS. All prior test functions remain unchanged; the suite adds fourteen cases.

Independent probes ran normally and under -O:

- **31 malformed/missing/unreadable ledger cases**, each through ledger_gate() with known and unknown host failures, and through main(). All preserve ledger UNKNOWN, null unavailable values, receipt/stdout agreement, and exit 2.
- **72 host-failure/k combinations**: primary k=8/9, guard k=6/7, simultaneous 8/6, and below-limit 7/5; mismatch, timeout, rc255, and missing FAILEDIDS on either or both hosts. Known k alerts survive host UNKNOWN and coexist with cumulative UNKNOWN.
- Primary **149/150** and guard **44/45** main boundaries, plus a fresh guard loss added to 44. Alert thresholds and bank maxima **11/9** remain unchanged.
- Overlap counts once; distinct losses count twice; failed IDs duplicated across hosts remain deduplicated. Rechecking the 22 inventoried replacement-r1 failures retains **41/14** losses and **16/6** overlap. Fixture tests independently reproduce 55 events and per-population max k 2/1.
- The six original r4 reader rejection shapes — H+hex, H+H, non-JSON matching fragment, string collections, object collections, and a string mixed with lists — fail closed through full template/main under both shells. Two valid path-quoting controls pass.
- Replacement-r3, replacement-r4, and replacement-r27 exact-completion exits pass; null-reason short exits retain both short-completion and unstarted anomalies.
- Immutable history/dispatch accounting independently reproduces reporting **1950/1950**, replacement-r1 **1754/1754**, replacement-r2 **555/554**, and replacement-r3 **286/289**, with verified full SHA binding.

Per interpreter mode, the independent drivers exercised **167 main calls, 100 full shell templates, 62 ledger-gate calls, and 36 parser calls**, plus parser controls and four immutable dispatch checks. The totals include the deliberate r5 false-pass differential controls. All verification conditions used explicit raises.

## Tests

Required commands ran at nice 19 using the specified freeze environment, with bytecode and pytest cache disabled:

```text
PYTHONDONTWRITEBYTECODE=1 nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B -m pytest -q -p no:cacheprovider /mpac/sdicks02/k4s-runner/run-r1/tools/candidate-r4/test_checkpoint.py
125 passed in 9.03s

PYTHONDONTWRITEBYTECODE=1 nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B -O -m pytest -q -p no:cacheprovider /mpac/sdicks02/k4s-runner/run-r1/tools/candidate-r4/test_checkpoint.py
125 passed, 1 warning in 8.92s
```

The optimized warning is pytest's generic warning about disabled ordinary assertions; candidate validation and the suite's ok() checks use explicit raises. The new PATH-shim tests run the real readers before returning status 7 and retain stray reader lines for inspection. The independent probes supplement these tests with both shells, the original exception/status-73 mechanisms, and unfiltered full-template output.

## Effects, outcome blindness, and limits

Both new readers use open() in its default read mode and expose only an operational dispatch SHA or completed/failed/unstarted list lengths. J/P remain shell-quoted assignments; file arguments remain double-quoted. Full-template controls used a path containing spaces, a single quote, a semicolon, and literal `$(printf QUOTE_ERROR)`; no pathname expression executed. All synthetic input-file bytes were identical before and after every template execution.

Reinspection found no reachable remote write, process kill, STOP creation, service operation, launch, dispatch/ledger change, game write, commit, or push. The tool's existing local health-directory/receipt write remains; probes directed it only into temporary synthetic roots. Importing the candidate does not run the host loop.

The immutable supervise.py and run.py producers are unchanged from r5. Their checked launch SHA and exit lists describe dispatch/process accounting. Completion proofs contain descriptors, timing/placement, and game filenames/hashes; checkpoint reads interference metadata. No game outcome file, winner/loss value, or statistical contrast was read by this review or introduced into the readers.

Inherited limitations remain unchanged: mutually consistent grep/count zeros can hide shared remote I/O failures; ledger validation is not a full schedule/evidence-hash audit; malformed acknowledgment input or receipt-write failure can prevent normal receipt completion. No new remediation condition is imposed for these previously documented limits.

No SSH, real-host execution, outcome-data reads, source edits, checkout changes, or commits occurred. Tests and independent probes used temporary local fixtures and injected runner/process/clock data. **This requested report is the only persistent artifact written by the review.** No approval conditions or unresolved blocking findings remain.
