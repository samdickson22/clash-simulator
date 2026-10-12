# Independent review: K4S checkpoint gate, r1

**Verdict: REQUEST_CHANGES.** The mechanical r2 changes are correct, and the intended health reads expose no study outcomes or remote mutation. The gate needs the 8/6 threshold correction and reliable ledger validation. Its cumulative arithmetic also needs an overlap safeguard.

## Scope and identity

Reviewed repository file: `reports/explore/k4s-confirm/run-r1/tools/checkpoint.py`, using the immutable **b5530e98** version, against **7ee26396**. The main checkout does not contain this path; the repository objects do. The standalone runner copy is `/mpac/sdicks02/k4s-runner/run-r1/tools/checkpoint.py`.

- Old blob: `da2d5bd17eb1d921de7a70dc4608d2d1233e793b`.
- New blob: `54f25dcab4ca1630eece801a36ee3e1f97d9cbfa`.
- New file SHA-256: `40cca7725def711070b9499a3226a79836a89482c400e1e3bddd6fedd19a64d2`.
- Supplied diff, found at `/mpac/sdicks02/k4s-runner/run-r1/reviews/CHECKPOINT-DIFF-7ee26396-b5530e98.diff`, verified SHA-256: `52cd4583d901c7a0ccd22b850252476d746a397e38770f802bd4df7e3247b941`. Its contents match the repository diff.

Context checked: ROUND-r2-AUDIT.md F2/F6; rounds/r2/RECEIPT-ERRATUM.md F2/F5; PREREG-K4S r3 §3.4; frozen schedule/replacement mechanics; COORDINATOR changes adc12f36 (P2), afe83faa (Option A), 38ed75a2 and 9acbe743 (stricter k ruling). Line numbers below refer to the new blob.

## Required changes

### R1 — MEDIUM: automatic k escalation is one replacement late (lines 108, 116)

The gate actually uses **primary k >= 9 / guard k >= 7**. The coordinator's stricter count reading requires **k >= 8 / 6** because k is zero-based. Exact replacement for line 116:

```python
if kmax['primary']>=8 or kmax['guard']>=6:anom.append(f'replacement k at limit-2: {kmax}')
```

Also correct line 108's explanatory comment: the alert is at **9/7 replacements per cell, equivalent to zero-based k >= 8/6**, under the 38ed75a2/9acbe743 ruling. Keep the bank limits 11/9 and cumulative thresholds 150/45 unchanged.

### R2 — MEDIUM: missing and structurally malformed ledgers can pass as healthy (lines 109–113)

`LED.exists() else []` treats a missing ledger as zero historical losses and zero k, without an anomaly. With otherwise healthy host data this reaches exit 0. Structural corruption can likewise pass silently:

- `{"events": {}}` is accepted as an empty event collection.
- An unknown lost population contributes to neither cumulative total.
- A missing/null replacement, missing/null k, or negative k can be reduced to k=0.
- An unknown replacement population creates another dictionary key, which neither primary nor guard escalation examines.

Invalid JSON, a missing `events` key, or a string k instead raises an uncaught exception outside the host try/except. These cases do exit nonzero (so they do **not** pass as healthy), but exit 1 without the promised anomaly receipt/JSON line instead of the documented exit-2 health path.

**Required:** read the ledger unconditionally and put reading, decoding, validation and aggregation behind the anomaly-reporting error boundary. Require a ledger object with an `events` list; each event must contain the needed lost/replacement descriptors with population in `{primary, guard}`, matching valid cells (primary 0–49, guard 0–17), a unique lost ID, and an explicit nonnegative integer replacement_k (reject booleans, floats and strings). Do not default missing fields/populations/k to valid values. A missing/unreadable/malformed ledger must append a ledger UNKNOWN anomaly, write the normal health receipt and print the normal JSON result, then exit 2. Report unavailable cumulative/k values as unknown rather than authoritative zeros. Use explicit checks that still run under `python -O`.

### R3 — MEDIUM: cumulative totals double-count losses already inventoried from the checked phase (line 114)

`cp,cg=lp0+LOST[0],lg0+LOST[1]` is correct **only when current-phase failed blocks are absent from the ledger**. That holds for the reviewed r2 dispatch/ledger: their lost-ID overlap is zero. The tool also accepts older/stopped phases, and the mutable ledger is advanced by inventory. Rechecking a phase after its losses enter that ledger adds them again. An isolated fixture with one ledger loss and that same current-phase failed block reports two losses; this can trigger a false 150/45 escalation.

**Required:** count the union of ledger lost IDs and current-phase failed IDs per population, or explicitly verify their disjointness and fail closed on overlap before adding counts. The existing aggregate `LOSTPOP` read alone cannot prove disjointness. Any additional evidence must remain outcome-blind and read-only. Do not assume phase names or job timing alone establish separation.

## Correct behavior and limits

**Cumulative thresholds:** with the committed blind-ledger-r2.json and no current failures, the gate reproduces **41 primary / 14 guard**, from 55 events. Adding current failures alerts at primary **150** and guard **45**, and stays below those alerts at 149/44. No change to these comparisons is required.

**Per-cell / per-population k:** for valid ledger records, the maximum of all replacement_k values within a population equals the maximum of its per-cell maxima. Therefore the present population reduction correctly answers whether **any cell** crosses the threshold; it does not mistakenly add k across cells. Independent grouping reproduces primary max k **2** (cells 10 and 19) and guard max k **1** (cells 0, 3 and 8). It does not output a per-cell map, which is unnecessary for this any-cell alert. This conclusion depends on validating population, cell and k as required in R2. The wrong alert boundary is R1.

**Mechanical changes:** default namespace `k4s-confirm-replacement-r2` is correct for r2. The dispatch SHA-256 is `1df20188998b9bfe659446fa3463bb2d8b369eba547e0a3331f8b1f2e84bfcd3`; its blocks count to **555 on 127x03 / 554 on 127x04**. `exp[h]` correctly unwraps those host-specific expectations while preserving scalar expectations for older phases. The default Python phase remains `reporting`; the companion watch.sh explicitly defaults to replacement-r2, so its normal invocation supplies the right phase.

**Host and study effects:** checkpoint.py issues only the fixed health-read shell template to 127x03/127x04: who, file existence, progress/exit/stop/copier metadata, directory counts and ps. Namespace and phase interpolation is shell-quoted; the supervisor PID extraction is numeric. No kill, STOP creation, service operation, launch, dispatch/ledger modification, game write, commit or push is reachable in this tool. Its explicit write is a local `/mpac/sdicks02/k4s-runner/run-r1/health/<phase>-<utc>.json` receipt, plus creating the health directory. Thus it is not literally filesystem-read-only, but it does not alter experimental state. SSH/process and filesystem reads still have ordinary operational overhead. The separate commit_checkpoint.sh helper is not invoked by checkpoint.py and is outside this diff's authorization.

**Outcome exposure:** none found for the frozen producer schemas. The tool never opens games/*.json or reads winner/loss values or statistical contrasts. It reads hub complete.json metadata for interference only; frozen completion proofs contain descriptors, timing/placement and game filenames/hashes, not game outcomes. The newly printed cumulative losses are failed operational blocks, not match losses; k is replacement-bank usage. Progress, copier errors, stop reasons and health flags are operational metadata. The raw remote metadata is also included in the receipt, so this assessment rests on the checked frozen producer schemas, not merely the `outcomes_read=False` marker.

## Validation

No dedicated checkpoint.py tests were found. Existing relevant schedule and loss-inventory tests were run from the local clasher-k4s-run worktree after verifying the test files, common.py, schedule.py, replace.py and plan.json match b5530e98 blobs:

```text
PYTHONDONTWRITEBYTECODE=1 nice -n 19 /mpac/sdicks02/venvs/k4s-freeze/bin/python -B -m pytest -q -p no:cacheprovider reports/explore/k4s-confirm/test_schedule.py reports/explore/k4s-confirm/test_replace.py
9 passed in 4.28s
```

The initial system-python attempt could not start pytest because that interpreter lacked it; the existing k4s-freeze environment succeeded without installing anything.

Separately, `nice -n 19 python3 -B` executed the exact ledger-gate AST statements from blob 54f25dca with in-memory paths/data only. Checks reproduced the actual ledger and dispatch totals, independent per-cell maxima, 149/150 and 44/45 boundaries, missed alerts at k=8/6, missing/schema-invalid ledger acceptance, uncaught malformed-input exceptions, and the overlap double count. No checkpoint top-level host loop was run. No SSH, outcome-file reads, source edits or commits occurred. Pytest used temporary fixtures; this review report is the only persistent output written by this review.

After R1–R3, require focused offline regression checks for the corrected k boundaries, missing/malformed ledger exit-2 receipts, valid per-cell maxima, population thresholds, and overlap handling before accepting the updated gate.
