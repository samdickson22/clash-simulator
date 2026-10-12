Verdict: REJECT

Round 2 of the replacement-cycle tooling review. Reviewed `tools/round.py` SHA-256 `6823591c01faedc3d63b511e0401e0a46365310d977051517244311e377ae2c8`. Line numbers refer to that version unless otherwise stated. This verdict concerns the reusable orchestrator; it does not establish a defect in the already launched replacement-r1 experiment.

## Round-1 finding status

| Round-1 finding | Status | Evidence in round.py and remaining issue |
|---|---|---|
| 1. Failed qualification/runtime comparison masked by successful carry-over | RESOLVED | `remote()` uses `bash -euo pipefail -s` with its body on stdin (39–43). The separate Python comparison must succeed before copying (221–239). It checks qualification PASS/checks/host/job/current pin SHA, compares all five smoke-runtime binding maps, verifies current pinned file/native/input bytes, and checks full carry-over hashes. Both barriers must pass before finalize receipt publication (254–259). |
| 2. Inadequate stop/drain and masked checks | PARTIAL | Both STOP requests precede waiting; supervisor and worker PGIDs replace command-line matching (68–85). Drain requires exact completed IDs, ACK bindings and matching inactive copier identities on hub/source, retaining STOP-COPY on failed revocation (102–124). Census still explicitly suppresses failure, ownership metadata is incompletely bound, the worker inventory can be read before its final update, and final copier health is incompletely checked. See R2-1 and R2-2. |
| 3. Unbound historical hub membership/provenance | PARTIAL | Only history namespaces/phases are scanned; each dispatch SHA and host assignment is checked; semantic descriptors are compared and canonicalized; duplicate durable IDs and exact logical coverage are rejected (142–174). Proof host, descriptor host/dispatch, historical launch/runtime provenance and historical raw-file integrity remain unverified. See R2-2. |
| 4. Failed inventory advances authoritative ledger/dispatch | PARTIAL | Frozen replace.py now runs once against a private working ledger/dispatch; validation precedes publication, and failed work requires manual reconciliation (130–179). Publication is still unlocked and uses successive non-atomic copies, and consumers do not verify the full artifact/receipt chain. See R2-3 and R2-4. |
| 5. Missing P2 prelaunch and escalation conditions | PARTIAL | Loss/k thresholds are computed and recorded; prelaunch rejects them; maintenance/stamps/timers are read (175–184, 287–306). Unexpected stop/refusal escalation, proof the relevant timer fired, and the 08:40 builder handshake/timeout are not enforced. A motd-expiry override has no bound ruling. See R2-5 and R2-6. |
| 6. Empty replacement-history enumeration | RESOLVED | Explicit history entries replace `ls`/word splitting (50, 144–146, 161). A history containing only reporting is enumerable without an empty-glob failure. The CLI intentionally starts at N=2 for this already bootstrapped run (335). Numeric history/round sequencing is still absent; see R2-4. |
| 7. Stage helper ignores selected extras archive | RESOLVED | Export, upload, SHA verification and extraction explicitly select the new host/round archive (189, 192, 204–208). Overlay verification and pinned PREREG copying/checking are explicit (194–195). The preliminary T1-path grep is weak, but fresh frozen source binding verifies the exact reference tree and job-path normalization before the qualifying receipt can PASS. |
| 8. Detachment reported as successful launch | PARTIAL | Launch waits for launch.json, admitted=true and supervisor PID existence on each host (318–327), which closes the detachment-only defect. Runtime/identity bindings and partial-launch/history recovery are incomplete. See R2-4 and R2-7. |

## Findings

### R2-1 — MAJOR — Stop can certify quiescence after a failed census or with an incomplete ownership inventory

**Lines:** 54–62, 69–85; final copier checks at 118–122.

**Scenario:** `group_live()` runs `ps ... || true`. If ps fails with no stdout, the strict remote shell returns zero and the parser returns `{}`. Both the polling check and final check therefore certify zero live members. A local shell control with a failing mock ps returned rc=0 and empty stdout; the pure function with mocked empty remote output returned `{}`. Strict SSH wrapping does not repair an explicit `|| true`.

The supervisor admission is read once immediately after STOP, before the supervisor is proved gone. Frozen supervise.py calculates `reason` before launching free slots and appends ownership records as it launches workers (`supervise.py:69,98–108`). STOP and the admission read can fall between that reason calculation and a new worker's registration. The recorded PGID set can consequently miss a group. The final admission file is never re-read. Launch is bound only by host/dispatch; admission only by supervisor PID; exit only by host. Job, phase, supervisor PGID and complete identity are not cross-checked or preserved as hash-bound evidence.

Drain substantially improves revocation, but final health checks only `revoked`, `lifecycle_error` and `fatal_error`. It does not require final=true, host/phase/freshness, absence of `error`/`block_errors`, or the final listed/durable/returned/pending set. Inactive admission identities are compared, but the final source/hub receipts' job/phase/source_host are not rechecked. These are narrower guarantees than the stated final drain proof.

**Fix:** remove census failure suppression, reject malformed/incomplete census output, and distinguish a successful empty membership result from failed enumeration. Bind launch/admission/exit to the requested job, host, base phase and pinned supervisor identity. After proving the supervisor group dead, re-read the now-stable admission and check every recorded worker group; retain that full final inventory and metadata hashes. Check final copier health and both inactive admissions against the same phase/host/job and stop interval, and re-establish the complete ACK set after revocation before removing STOP-COPY. Use only read-only identity/group probes and owned STOP tokens.

### R2-2 — MAJOR — Hub admission is history-scoped but does not establish full historical block integrity or runtime provenance

**Lines:** 89–95, 106–110, 144–158, 170–174.

**Scenario:** `hub_ok()` hashes complete.json and the ACK, but checks neither ACK sealed/game count nor the returned marker's complete SHA/source host. A synthetic in-memory test supplied sealed=false, games=0 and a returned marker naming the wrong source host and complete SHA; `hub_ok()` returned True. The reviewed copier's own verification is stricter (`mirror_k4s.py:261–270,303–309`).

Inventory checks the dispatch row's host, but explicitly removes host and dispatch from the descriptor comparison. It never checks `proof['host']`. A self-consistent ACK/complete pair with the right logical descriptor but wrong proof/descriptor host is thus admitted to coverage. History binds a dispatch hash, but no historical source launch or runtime-pin binding is checked. The supplied history contains namespace/phase/dispatch/launch time only.

Also, frozen replace.py hashes game files only for rows belonging to the currently inventoried source phases (`replace.py:24–30`). Historical completions outside that remainder are counted solely from their descriptors and ACK metadata. A historical game file deleted or corrupted after copier revocation can still contribute to exact coverage. The arithmetic coverage check cannot establish byte integrity.

**Fix:** enforce the full ACK/returned/proof-host bindings and exact descriptor equality, including historical host/dispatch. Bind each history entry to authenticated launch/runtime/freeze evidence for both hosts. Re-verify every counted historical block's exact game-name/count inventory and hashes through an outcome-blind verifier, not just the current stopped remainder. This can be done in a non-frozen wrapper without modifying replace.py or interpreting game outcomes. Persist the verified hub-view inventory and its metadata hashes.

### R2-3 — MAJOR — Publication still permits a partially advanced authoritative ledger, and concurrent rounds can overwrite each other

**Lines:** 127–134, 159, 178–184.

**Scenario:** after successful private validation, line 179 copies backup, working ledger into the authoritative ledger, then dispatch into its final name. `copyfile()` truncates and writes directly. A disk error/interruption after the ledger copy but before dispatch/receipt publication leaves an advanced ledger without a successful inventory. Failure during a copy can leave a truncated authority file. The receipt is atomic individually, but the ledger/dispatch/receipt transaction is not recoverable automatically.

The work directory excludes a same-N second attempt; it is not a run-wide ledger/history lock. Two different Ns can copy the same input ledger, consume the same lost IDs, and publish incompatible artifacts. There is no immutable input hash check before promotion or transaction marker defining which generation is authoritative. The backup itself can be overwritten during reconciliation.

**Fix:** hold a run-wide lock through source/history validation, input snapshot, replace invocation, validation and publication. Preserve an immutable input ledger and bind its SHA. Prepare generation artifacts via temporary files and atomic renames, with a durable publication journal or a single atomic pointer to a verified generation. Require recovery/reconciliation of any interrupted publication before another inventory or launch. A gated inventory may be published for audit, but its blocked disposition must remain explicit; crossing a gate should not cause a second blind inventory.

### R2-4 — MAJOR — Receipt existence is treated as authorization; finalized dispatch/ledger hashes are not enforced at launch

**Lines:** 45–50, 127–140, 200, 213–216, 248–259, 287–290, 308–330.

**Scenario:** `need()` checks existence and parses JSON. It does not verify receipt round, predecessor SHA or current artifacts. Finalize checks the dispatch SHA once, but launch passes the current dispatch file to launch_phase.sh and confirms the supervisor against a newly computed SHA of that current file (313–322). If the dispatch changes after finalize, the helper copies the changed bytes and the wrapper accepts their launch hash. Neither frozen reporting_release nor supervise.py checks that the launched dispatch matches the dispatch SHA recorded in REPORTING-AUTHORIZATION (`barrier.py:46–62`, `supervise.py:35–55`). Canonical rows alone do not enforce the approved ledger/coverage assignment.

Similarly, `inv['ledger_sha256']` is copied into authorization without checking the current authoritative ledger. Prelaunch trusts recorded escalation and launch does not recheck inventory escalation. Old stop/drain receipts can be reused after history advances: inventory compares only their namespaces, never requires their source to equal history[-1] or validates numeric N sequencing. Different round directories can therefore operate on stale source authority.

**Fix:** validate a chained receipt schema with round/source/namespace/base-phase and predecessor hashes. Require the stopped source to match the current history tip and permit exactly the next round, under the run-wide lock. Before stage/finalize/prelaunch/launch, verify the published dispatch, ledger, inventory and authorization hashes appropriate to that step. Immediately before each host launch, compare local/remote dispatch to the finalized approved SHA and bind the resulting launch runtime-pin SHA to that host's finalized qualification. Do not replace expected hashes with hashes recomputed from potentially changed inputs.

### R2-5 — MAJOR — Unexpected stops and refusals do not set a persistent escalation gate

**Lines:** 82–85, 139–140, 175–184, 287–290, 316–326.

**Scenario:** a supervisor exits for signal, memory_floor, foreign_compute unrelated to motd, or offhost-copy failure. Stop records the reason but accepts it. Inventory's gate depends only on population loss counts and max k. Under those thresholds the wrapper can proceed through prelaunch and relaunch without coordinator disposition. The imported stop-reason.json and per-block exits are not evaluated. That also misses earlier unexpected stop events represented in failed block exits when the final reason is the scheduled owned_STOP.

A helper/admission/barrier refusal raises and stops that invocation, but no persistent refusal gate is created. A later invocation or later namespace can continue without a bound coordinator response. This does not enforce Option A/P2's escalation on any non-apt/motd stop or refusal. A scheduled P2 owned_STOP is authorized, but it must be distinguishable from an unrelated stop rather than broadly allowing every owned_STOP.

**Fix:** bind each planned cut to its timer/policy authority. Evaluate stop-event/per-block exit evidence and classify approved apt/motd events using their process evidence; foreign_compute alone does not prove motd. Write a persistent run-level blocked/escalation receipt for every unexpected stop or refusal, and require an explicit coordinator disposition bound to that event before subsequent staging/admission/launch. Retain the correctly implemented 150/45 and k=9/7 gates.

### R2-6 — MAJOR — P2 timer completion and builder handshake remain operator assertions; timer/census errors can be hidden

**Lines:** 261–272, 274–306, 310, 334.

**Scenario:** prelaunch records textual next/last timer rows but never requires a nonempty valid timer set or proves that the selected cut's timer occurrence has fired. It can pass before the timer with quiet maintenance and fresh stamps. The timer and maintenance pipelines use `|| true`; failed systemctl or ps can look like an empty, quiet result. A pure state-parser control with no TIMER or PROC records returned an ordinary state tuple without failure.

For the 08:40 cut, `--builder na` is accepted, and `released`/`timeout` are merely strings. There is no cut identity, coordinator go/release receipt, quiet-window start, or elapsed 30-minute check. `timeout` can be supplied immediately. Conversely the flag is required for every cut even though the handshake applies only at 08:40.

`--accept-motd-expiry` permits a stamp to expire inside the window without supplying the coordinator ruling that the error text demands. `--window-hours` accepts negative/non-finite values, which can bypass the expiry comparison. The 15-minute receipt freshness test does not re-evaluate stamps/timers/maintenance at the actual two-host launch, and a future-dated receipt is accepted.

**Fix:** parse/read timers through a failure-preserving interface, require both known timers, bind the selected cut/occurrence and prove it has fired with maintenance exited before relaunch. Capture ps successfully before filtering it. At 08:40 require a bound coordinator/builder release receipt or a documented quiet-window start plus an elapsed 30 minutes; require na only for other cuts. Require a hash-bound ruling for any motd-window exception, validate a finite positive window, and check that stamps remain safe for that window at actual launch. Reject future/stale receipt timestamps and refresh state immediately before admitting each host.

### R2-7 — MAJOR — Partial launch and history-write failure leave an active namespace outside the next stop's history

**Lines:** 314–331; stop's source selection at 65.

**Scenario:** 03 confirms launch and 04's helper/admission then fails. The exception/`fail()` leaves 03 live, but neither a partial launch receipt nor the new namespace is recorded in history. The next `stop` targets history[-1], the already stopped preceding namespace. The explicit failure message asks for manual owned STOP, but a helper subprocess failure at 316 bypasses even that message. No automatic owned-stop/reconciliation path or durable recovery state is established.

Even with two successful launches, launch.json is written before history.json. If the process/filesystem fails between those writes, `launch.json` prevents retry, history remains stale, and the same source-selection problem occurs. Confirmation also checks only PID existence, host, current dispatch hash and admitted=true; it does not bind the live process to the detached/pinned identity, check admission host, or compare launch runtime-pin SHA to finalize. PID reuse can satisfy `kill -0`.

**Fix:** durably record a pending launch transaction and each host's identity/confirmation as it occurs. On any helper/refusal/confirmation failure, use the authorized owned STOP for every launched host and prove shutdown, preserve partial evidence, and enter reconciliation/escalation. Make successful history advancement recoverable and atomic with the launch generation; let stop/recovery find pending active namespaces. Confirm the pinned supervisor's full identity, admission host/phase context, approved dispatch and finalized runtime SHA. Never launch the same claimed namespace twice.

## Sealing, staging and compatibility

- **Outcome sealing:** the wrapper has no outcome-release/reducer call and does not project winner/loss/contrast data. Descriptor, count, hash and receipt reads remain blind. Frozen replace.py physically reads raw games for hashing, and the reviewed copier copies/hashes them; that is distinct from interpreting outcomes. I opened no game outcome data during this review.
- **Remote strictness:** the Python remote API correctly places its script on stdin under explicit strict options; a local strict-shell control exited 1 without running the following echo. The remaining fail-open paths are explicit `|| true` constructs. The separately reviewed launch_phase.sh retains its own older SSH command bodies, so the module docstring's claim that every remote step uses this API is too broad.
- **Stage:** explicit archive selection, full extras SHA, post-stage overlay verification, pinned PREREG, fresh destination and fresh detached qualification are present. `grep -q "$J" plan.json` alone proves only one matching substring; the frozen qualification source-binding check provides the complete rebind/reference check. I did not inspect remote stage directories or assert their contents.
- **Finalize:** the failed-check masking defect is fixed. Fresh qualification bindings, smoke map equality, runtime bytes, full FROZEN/SMOKE/admission carry-over hashes, the frozen 03 idle identity and both frozen reporting barriers are checked. Finalize still needs the receipt-chain enforcement described above. Its receipt stores a qualification summary rather than hashes of the qualification/runtime evidence, which limits later launch binding.
- **Python 3.8:** parsing, compilation in memory, module import and pure-function controls passed on `/bin/python3` 3.8.10. No incompatible syntax or standard-library API was found. The run steps themselves were not executed.

## Validation and scope

Read the prior findings, Option A at afe83faa, P2 at adc12f36, current history/progress/launch metadata, and the relevant frozen/reviewed source files. Both historical dispatch hashes matched history; all 3900 reporting rows and 3508 replacement-r1 rows passed frozen canonical(). All 33 current ledger lost/replacement descriptors passed canonical(). These local metadata checks do not attest current remote state or hub game bytes.

Only in-memory pure-function checks with remote/subprocess/file reads mocked where needed, Python 3.8 import/compile, read-only local metadata checks, and isolated shell controls were run. No round.py step, SSH, remote-host command, commit, push or game outcome-data read occurred. Bytecode writing was disabled. This review is the only file written.

Reviewed dependency hashes: launch_phase.sh `fb199bc37a284c94cfa479f82fd3e37345d7f12c66db7c0a87ea46cc22d3f3f9`; mirror_k4s.py `47eb96d61bd094ffea300f6892844e63ede1c6127795e93a72781e9c1d7da5cd`.
