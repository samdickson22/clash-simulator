# Amendment 19 r2→r4 delta review: verify-then-retire, completed-attempt provenance, PSI policy

Reviewer: the same independent Claude reviewer as the r2 review (`AMENDMENT-19-REVIEW-20261010.md`, c2a092da…), for coordinator 0523ae6f, 2026-10-10, 04:01–05:10Z. The review was read-only.
- **05 (nice 19):** tests and checkers ran here, using Python 3.12.12 for the suites and system 3.8 for `check_package.py`.
- **04:** only read-only `/proc`, `ps` and `who` reads. The exact r4 `a19_common`/`a19_resources` bytes were piped over ssh stdin, so nothing was written on 04, no signal was sent, and no launcher, STOP or r4 file was touched.
- **Reviewer's own files:** this review and `reviews/a19-reviewer-artifacts/r4/`. The r2 reviewer artifacts are unmodified (55fade89, d3632c41, 82915908).

## Verdict: REJECT r4 bytes for freeze (narrow); the design is approved

**What r4 gets right.** The C1, C3 and C5 code, the §10 policy and the PSI semantics are implemented correctly. C2 ordering is correct: STOP is never written before a successful parallel proof, and a parallel failure never touches serial.

**The defect: a STOP race in the production runner (F1, new; I missed it in r2).**
- The production r4 runner (`run_stage.py` 8c3c0523) checks STOP itself before every new host-lock acquisition. When it sees STOP it raises `RuntimeError('Operational stop requested')` and **exits 1**, usually before the supervisor's 5 s poll sends SIGTERM.
- r4's `serial_handoff` accepts only exit −15. So after the irreversible STOP:
  - the A19 attempt fails with `Unexpected serial verification exit`;
  - r4 retains a `failure.json` with `exit_code=1`, which looks like a scientific failure;
  - every later A19 a1-verify attempt is refused at the pre-check.
- The parallel `verified.json` then becomes unusable under C3, so the A1 path dead-ends and a new amendment is needed.

**How likely is it?**
- Reproduced with the exact production `supervise.py` (884f0304) and the AST-extracted production `lock()` (8c3c0523).
- At the lock cadence measured on 04's live seal child, **5 of 6 handoffs failed this way** (`r4/stop-race-outcomes.json`).
- This would most likely happen on the real run.

**F2 (smaller) compounds it.** The post-STOP wait loop still calls `guard()`, so a PSI, deadline or floor hard-fail after STOP has the same stranding effect.

**The fix is small and local (D1–D3, §8).** A diff-only r5 check of `a19_handoff.py`, `a19_authority.py` and tests is enough. Nothing scientific changes.

## 1. Bytes and pins

| Item | Recomputed | Result |
|---|---|---|
| Package manifest | bef7f189… | match. `check_package.py --manifest-sha256 bef7f189…` **PASS**: 19 original fields, 24 epochs, 10 production files, **347 A18 frozen pins** |
| Held r2 / r3 manifests | df7e185e… / 0c0f0832… | both checkers PASS (plans 544f419f / e864d0e6) |
| Draft r4 | b43a3979… | match |
| Verification plan | a32d2830… | match |
| Plan delta | fc07fedb… | match |
| Source pins | 44ca4230… | match. The `production` and `auxiliary` maps are canonically equal to the plan's `source_files_sha256` (10 files) and `auxiliary_files_sha256` (11 files). All 21 files were re-hashed. The SSH wrapper is 623d2587… and the frozen verifier 002d6894… |
| r2→r4 diff / r3→r4 diff | b4c137e3… / b7ff7649… | match |
| Test receipt | a3b07cbf… | match. **105/105 PASS on rerun** (3.12.12, 108.7 s; `r4/author-suite-rerun.log` 1dc68111…) |

**Original plan.** The original plan has 19 top-level fields, and they are **canonically byte-equal** in a32d2830. That comparison uses canonical bytes, not Python `==`. Exactly one field is added, `operational_body_verification`. Inner pin counts are unchanged: 362 source, 380 PYTHONPATH and 25 external.

**Unchanged files.** `a19_a2.py` (36c6b364), `a19_common.py` (c4f1b9ba), `a19_kernel.py` (5ec530be), `a19_reduce.py` (8a30e2a8) and `a19_worker.py` (a19cf853) are **byte-identical to r2**. Only authority, handoff, launcher, pool and resources change. `proposed_inventory_r3.py` is byte-identical to my d3632c41.

**Changed keys in `operational_body_verification` from r2:**
- `revision` = A19-r4;
- `handoff_policy`;
- `parallel_a1_prerequisite`;
- `resource_policy`;
- both file maps.

Placement (12 workers on cpus 0–11, control on 47, host 04) and freshness flags are unchanged.

**Original approval.** 19401ce4 is in `amendments/coordinator-approval-A1-r2.json`, and its 8 fields are listed in §7.

**Earlier interpreter failure.** The disclosed Python 3.8 failure (`Path.is_relative_to` in frozen `state_root`) is genuine and was correctly not "fixed". The authoritative suite is 3.12.12.

## 2. Conditions C1–C5 and §10, item by item

| Item | Status | Evidence |
|---|---|---|
| **C1** conservative inventory | **Met** | `_probe` uses real UID from `status`. Denials of `owner`, `stat`, `cmdline` and `cwd` all set `unknown` and are counted in `admission_processes`. `smaps` falls back to `statm` RSS, then to MemTotal. Affinity is null if unreadable. Live exact r4 code on 04 (04:10Z): **no exception**, 4 inaccessible processes (all `cwd`-denied, as in r2), `training_identity_unknown=[]`. My r2 PermissionError probes now fail as intended (`PermissionError not raised`). |
| **C2** verify-then-retire | **Ordering met; retirement step defective (F1, F2)** | §3 |
| **C3** completed attempt | **Met** | `completed_parallel_prerequisite` checks: canonical resolved path under `output_parent`, `a1-verify-<32hex>/verification-<32hex>/verified.json`, no `failure.json` or `STOP`, `complete.stage=a1-verify`, same seal, `verification_receipts==[receipt]` exactly, both plan SHAs, false B/heldout, handoff status, `request-binding` equal to the completion request, and the same verification plan and operational approval. The author's flipped probe rejects (`Failed/stopped A1 attempt`). A pre-check-only completion (`parallel_work_launched=False`) has no `verification_receipts`, so it cannot serve as a parallel prerequisite (KeyError, fail-closed), which is correct. |
| **C4** co-tenancy | **Met in code, operational at launch** | §4 |
| **C5** bindings | **Met** | `authenticate` rehashes `request.amendment.path` against the freeze and requires the operational approval to equal the freeze. The 8-field A1 approval has 7 fields canonically equal to 19401ce4. The new operational fields (`handoff_policy`, cores, siblings, `no_new_clasher_launches`, `x5_actual_exit_required`) are enforced. The deploy directory must hold exactly the 21 pinned `.py` files. `output_parent` is pinned to `…-verification-r4`. The deadline is ≤ 2026-10-11T04:00Z. |
| §10.1 owned tree | Met | Seeds are the controller plus `register()`ed Popen identities (pid/start/boot), with descendants propagated and retained across reparenting. Masters match the `-a19-r<N>` ControlPath regex only for `ssh` argv0. Only retained Popen objects are signalled (`terminate_owned`). |
| §10.2 X5 predicate | Met | §4 |
| §10.3 PSI | Met | §5 |
| §10.4 memory | Met | Owned PSS ≤ 48 GB is sampled only by the controller (workers call `snapshot(scan=False)`); MemAvailable ≥ 28 GiB; disk ≥ 40%. |
| §10.5 console | Met | `who` non-empty pauses new launches (capacity 0) and adds the total-Clasher16 reason. Running children continue. |
| §10.6 telemetry | Met | `record()` is called at launch, at handoff-decision, on every pause/resume transition, on hard-failure and every 10 s, and is fsynced. It holds counts, PIDs, PSI and memory, plus the full inventory rows. Rows carry pid, parent, starttime, state, flags, affinity and memory; **no command lines**. |
| R1–R3 | Met / documented | R1 controller-only PSS. R2 no retry. R3 first-wave measurement is in OPERATOR. |

## 3. Verify-then-retire: races (new tests in `r4/test_rev_a19_r4.py`, 12/12 PASS)

**Ordering is correct.** In `launcher.execute` the a1-verify sequence is:
1. the `serial_handoff(check_only=True)` pre-check, which is read-only;
2. `fresh_verify` (24 workers, then the fresh reducer, then the seal rehash, then `verify_sources`);
3. `guard()` and `verify_sources` again;
4. `serial_handoff(parallel_receipt=…)`;
5. `complete.json`.

Any exception before step 4 writes `failure.json` and never reaches STOP. The serial verifier does not take `owner_lock` (frozen `verify_body` doesn't, and run_stage doesn't), so the parallel `owner_lock(state)` does not block it.

**Tested:**
- `check_only` never writes STOP or any output.
- No STOP without a proof, and none with a proof from another attempt.
- A seal change before handoff means no STOP.
- Serial finishing first gives `SERIAL_ALREADY_COMPLETE` binding the original receipt, with **no STOP**.
- A second completion record is impossible (exclusive create, `FileExistsError`).

| Race | r4 behaviour | Verdict |
|---|---|---|
| Serial completes during the parallel run | The final `finished()` returns `SERIAL_ALREADY_COMPLETE`. `handoff.json` binds the original receipt, and `complete.json` binds the parallel receipt and that handoff. | Correct, but see D3: two valid receipts |
| Serial completes between `attest` and STOP | r2 production test: the supervisor completes, the post-STOP `finished()` returns ALREADY_COMPLETE, and STOP is left beside a genuine `complete.json`. | Correct. The handoff record should say STOP was written (R4) |
| Serial fails scientifically during the parallel run | `while not live(verify)` and `require(not failure.json)` raise "Serial verification failed; not supersession". The A19 attempt fails, and both records are retained. | Correct fail-closed. The contradiction is never relabelled |
| Seal bytes change | Rehashed at fresh_verify start and end, at handoff entry, in `finished()` and after STOP. | Correct |
| Double completion | `complete.json` and `handoff.json` use `'x'`; `controller.lock` is held across the attempt. A second a1-verify attempt either takes the pre-check ALREADY_COMPLETE path (no parallel receipt) or is refused by `Pre-existing failure/STOP`. | At most one completed A1 attempt carries a parallel receipt |
| **STOP seen by the runner (F1)** | The production `lock()` checks `(ROOT/'STOP').exists()` before each outermost lock and raises `RuntimeError`, giving child exit 1. The supervisor records `verify-exit` exit 1 and `failure.json {stage: verify, exit_code: 1, reason: null or the STOP reason}`. r4 requires `exit_code==-15`, so it raises `Unexpected serial verification exit` **after** STOP. Afterwards the pre-check for any new attempt raises `Pre-existing failure/STOP`, and the parallel receipt is barred by C3. | **Defect, blocks freeze** |
| **guard() after STOP (F2)** | The post-STOP `while live(...)` loop calls `guard()`. A deadline, 120 s PSI ≥ 30%, memory or disk failure there raises after STOP. The serial process retires (−15) anyway, and A19 has no completion. | **Defect** |

**How often F1 fires.**
- Read-only 20 ms `/proc/2499719/fd` sampling on 04 (04:04Z, 90 s) found ≥ 47 new outermost `io.lock` acquisitions, about 0.52/s, with a lock held in 56% of samples. The 300 s confirmation is in §6.
- With a uniform 0–5 s supervisor poll phase, the runner sees STOP first with probability ≈ 1 − (1−e^{−2.6})/2.6 ≈ **64%** (a lower bound, since short holds are missed).
- The fixture at that cadence gave **5/6**.
- r2's tests and the author's tests both used inert children that never run the production `lock()`, which is why this was missed. I own the r2 miss.

**Which receipt is authoritative when both complete.** Code accepts *either* for A2:
- the serial receipt via `SEAL_ROOT/complete.json`;
- or the parallel receipt via `completed_parallel_prerequisite` with handoff `SERIAL_ALREADY_COMPLETE`.

They are scientifically equivalent, but downstream must bind exactly one; see D3.

## 4. C4: X5 gate, loader pause and co-tenancy (live read-only, 04:10Z)

**X5 gate on the live host.** The exact r4 `snapshot()` on 04 reports:
- `launch_blockers = [Actual X5 fit/loader exit required, No live training or fit loader]`;
- all 7 pinned X5 identities are present on boot bd010cb6;
- `training_pids` is **exactly** those 7: fit_runtime 3727520 plus 6 `pt_data_worker` descendants. There are no false positives among the 28 Clasher-marked processes.

**Capacity once X5 exits.** Capacity is `16 − (1 controller + 4 inaccessible) − 5` = **6 slots**. Each monitoring ssh adds one inaccessible `sshd`, which lowers slots by one but never aborts the attempt. Peak owned processes stay ≤ 16, because the host-wide I/O locks allow at most about 2 concurrent ssh clients across all workers.

**X5 supervisor.** The fit's parent, 3727388 (`exit-r2…/ops/supervise.py --arm X5`, nice 10, about 10% CPU on cpu 88), is **not** in the gate. If it runs post-fit stages that don't match `training_command`, such as eval, they won't block A19. A later fit would be caught by the predicate and pause launches; that pause can starve for 30 min and then fail, leaving serial intact. Operational condition O2 covers this.

**Cores.** No process is busy on 0–11, 47, 64–75 or 111 now, and G is not on 04.

**Loader appearing mid-run.** It goes to `pause_reasons`, then `capacity()` returns 0. Running children continue; nothing is signalled and nothing is SIGSTOPped. Initial launch with a blocker is a retained failure before any scientific work.

## 5. PSI pause and hard-fail semantics

`PressureWatch`, tested at the boundaries:
- **Pause** at `full avg10 ≥ 10` for 30 s. A dip below 10 resets the clock.
- **Resume** only after `< 5` for 120 s. Exactly 5.0 resets the clock.
- **Hard-fail** at `≥ 30` for 120 s. A dip resets the clock.
- `some` alone never pauses.
- NaN, >100 and missing lines are rejected.
- MemAvailable < 28 GiB is an immediate `check_snapshot` failure.

These match the coordinator's direction exactly.

**Consequences.**
- **Pauses** only gate `capacity()`, and every transition is fsynced.
- **Hard-fail** goes `guard()` → pool `failure.json` → `terminate_owned` on retained children only → attempt `failure.json`. The serial verifier is untouched, as long as the failure happens before STOP (F2).

**No scientific effect.** Wall-clock, pause and resource data appear only in operational telemetry. No timing enters `verified.json` comparisons, the seal or bounds. The kernel and reducer bytes are unchanged and science stays on 68e24722.

**Correlated-floor residual (O3).** The r4 supervisor and runner enforce the *same* 28 GiB MemAvailable floor. If A19's growth pushed the host below it, both would die together. The owned PSS ≤ 48 GB cap bounds this only when launch headroom is ≥ 28 GiB + 48 GB plus margin.

## 6. Throughput: measured lock occupancy (affects expected benefit, not safety)

**Measurement.** Read-only, 300 s of 20 ms `/proc/2499719/fd` sampling on the live seal child, which runs the same recompute loop and `lock()` wrapper as verify. Result in `r4/probe-04-lock-occupancy.json`, ending 04:16:54Z:

| Lock | Hold fraction | New outermost acquisitions |
|---|---:|---:|
| `127x04.io.lock` | **0.534** | 157 |
| `127x03.io.lock` | 0.108 | 24 |
| `127x08.io.lock` | 0.026 | 6 |
| Any lock | 0.668 | 187 (0.62/s) |

The process uses 0.987 of a CPU, so the time inside the lock is **CPU (decompress and parse) inside a host-wide lock**, not I/O wait.

**The bottleneck is 04's local lock, not 03's.** My r2 note and the draft's §8 both expected 03. Each verifier holds the single 04 lock for about 53% of its wall time, so **all processes sharing the lock together cap at about 1/0.534 ≈ 1.9 verifier-equivalents**, whatever the worker count. Consequences:
- **A1 under verify-then-retire.**
  - The serial verifier runs at the same time, uses a *blocking* flock and needs about 0.53 of the lock. A19's 6 workers share the remaining ≈ 0.87, so a full A19 pass takes about 12.7 h / 0.87 ≈ **14–15 h**.
  - Serial alone needs about 12.7 h, so A19 is **unlikely to finish A1 before serial**.
  - Contention may also delay serial. The A1 result arrives no earlier than serial alone would deliver it.
- **A2 stages (no serial running).** At best about 12.7 / 1.87 ≈ **6.8 h per verification**, not the draft's 1.1–3.2 h.
- **Updated F1 rate.** At 0.62 acquisitions/s the analytic estimate rises to ≈ 69%.

**Recommendation O5 (non-blocking; the coordinator decides).** Under the frozen lock scope, launching A19 for **a1-verify** gives little or no speedup and takes on the irreversible-STOP risk for no gain. Two options:
- Let the serial verifier finish, around 21:30–22:00Z if it starts at 08:30–09:00Z. Then use its genuine receipt (D3) and A19 only for the A2 stages. Note: about 6.8 h per A2 verification plus bound computation runs past the 2026-10-11T04:00Z cap.
- Commission a separate *operational* amendment that narrows the 04-local lock scope, for example to the read/hash call rather than the whole decompress-and-parse. That is the real throughput lever, and it changes no science, because the lock is operational.

The first-wave measurement (R3) remains the authority before any ETA is quoted.

## 7. Starvation and failure paths

| Path | Behaviour |
|---|---|
| Initial blocker or capacity 0 | Retained `failure.json`; no scientific work and no STOP |
| Pool starvation (no active workers, capacity 0 for 1800 s) | Pool `failure.json` lists completed, active and pending epochs; serial intact. Tested (author's and adapted tests). |
| Worker, reducer or comparison failure | Group termination of retained identities, per-child `exit.json`, and `cleanup-failure.json` if needed. No retry and no partial PASS. |
| Ignored SIGTERM on the serial child after STOP | r4 supervisor residual (R2). A19 fails with a timeout; no retry, no orphan signal. |

All of these are non-destructive. Every write is exclusive-create, and the only cross-tree write is the single STOP.

## 8. Conditions

### r5 code delta: required before freeze, diff-only re-check

- **D1. Accept the runner's own STOP-check exit as supersession, with strict evidence.**
  - After STOP, accept either:
    - (a) the current −15 path; or
    - (b) `verify-exit.identity==verify_identity`, `exit_code==1`, `reason ∈ {null, 'Operational STOP or resource floor'}`, and `failure.json` equal to `{utc, stage: verify, exit_code: 1, reason: <same>}`.
  - For (b), also require all of the following:
    - `sha(verify.log)==verify-exit.log_sha256`;
    - the last non-empty line of `verify.log` is exactly `RuntimeError: Operational stop requested`, and the log contains no `Body seal differs`;
    - the STOP SHA equals the one A19 wrote;
    - the `verify-exit.utc` timestamp is not before STOP's `utc`;
    - there is no r4 `complete.json`;
    - the seal is unchanged.
  - Record `SERIAL_VERIFY_SUPERSEDED` with `retirement_path ∈ {supervisor-sigterm, runner-stop-check}`.
  - `RuntimeError: Resource floor` and any other exit stay retained failures.
  - **Test:** extend `test_a19_real_handoff.py` to run the production `lock()` (my fixture can be reused) at fast and measured cadence; both paths must give SUPERSEDED.
- **D2. Nothing after STOP may fail the attempt for resource or deadline reasons.**
  - Replace `guard()` in the post-STOP loop with non-raising telemetry. No A19 children exist at that point.
  - Keep only the bounded identity wait (90 s) and the record checks.
  - Any post-STOP exception must write a distinct `handoff-failure.json`, binding the parallel receipt, STOP and intent, in addition to `failure.json`.
  - **Test:** a guard that raises once STOP exists must still yield SUPERSEDED.
- **D3. One canonical A1 receipt downstream, enforced in `seal_barrier`.**
  - If `SEAL_ROOT/complete.json` exists (genuine serial completion), the A2 `a1_verification_receipt` **must** be the serial `seal-verification.json`; reject a parallel receipt.
  - Otherwise it must be the parallel receipt of the single completed attempt whose handoff is `SERIAL_VERIFY_SUPERSEDED`.
  - The A19 `complete.json` keeps both receipts as corroboration.
  - **Test:** both orders.
- **R4 (non-blocking).** Add `stop_written: true/false` and the `handoff-intent` descriptor to `handoff.json` in the ALREADY_COMPLETE-after-STOP case.

**Re-pin after r5.** Re-pin the plan and `source-pins`, rerun the full suite on 3.12.12, and send the r4→r5 diff. Kernel, worker, reducer, common and A2 must remain byte-identical.

### Operational, before launch

- **O1 (C4).** All of the following must hold before launch:
  - the coordinator's actual lease of cores 0–11 and 47, with siblings 64–75 and 111;
  - G is not on them, and never on 52/116;
  - no new Clasher launches on 04 for the life of the attempt;
  - one monitoring ssh at a time;
  - a fresh exact-code inventory recorded with `launch_blockers==[]`.
- **O2 (X5 release).** "Actual X5 exit" means all 7 pinned identities are gone **and** the X5 arm supervisor 3727388 has exited, or the coordinator records that its remaining stages are non-training, nice ≥ 10 and off A19's cores. Don't launch on an estimate.
- **O3 (memory headroom).** MemAvailable ≥ 80 GiB at launch, so that A19's 48 GB owned cap cannot by itself push r4's supervisor below its 28 GiB floor.
- **O4.** Launch only after the authenticated seal exit (the launcher waits anyway). The serial verifier starts automatically and is the fallback.

## 9. Approval fields the coordinator must bind (after r5 passes the diff-only check)

**Revised `APPROVE_A1`.** Exactly 8 keys:

| Key | Value |
|---|---|
| `decision` | `APPROVE_A1` |
| `execution_plan_sha256` | `<r5 plan SHA>` (a32d2830… only if r5 leaves the plan unchanged, which it can't, because `source_files_sha256` changes) |
| `freeze_sha256` | `bd5b76433bf7eda6908ffe77418af3ae5dee27d87362ebb47d86c5721b17e7bc` |
| `file_layer_review_sha256` | `ff45e9edbffa606e020f3c91a4349074e2f19b0cbe431c44b1e70c359358d635` |
| `evidence_recovery_sha256` | `1adf50de13504df27a3c135e9e73a9b6861c99954f5f6795f80c380f36a1e35c` |
| `evidence_recovery_approval_sha256` | `64b1ebe435aa0a5cca2c9189e500fc43e279532cfae4aa4a671e3534497b4f60` |
| `assembly_sha256`, `a18_bindings` | canonically byte-equal to 19401ce4 |

**A19 `FROZEN`:**

| Key | Value |
|---|---|
| `decision` | `FROZEN` |
| `execution_plan_sha256` | `<r5 plan SHA>` |
| `source_files_sha256` | `<r5 10-file production map>` |
| `amendment_sha256` | `<actual r5 draft SHA>`, rehashed from the deployed file |
| Recommended extras | `independent_review_sha256=c2a092da…`, `r4_delta_review_sha256=<this file>`, `r5_followup_review_sha256` |

**`APPROVE_PARALLEL_BODY_VERIFICATION`.** All keys are enforced by `authenticate`:

| Key | Value |
|---|---|
| `decision` | `APPROVE_PARALLEL_BODY_VERIFICATION` |
| `a19_freeze_sha256` | `<freeze record SHA>` |
| `execution_plan_sha256` | `<r5 plan SHA>` |
| `original_execution_plan_sha256` | `68e2472255ba5d1b79ec9f45217aa14208a31b6c44ccec890af332909efe8bc8` |
| `original_approval_sha256` | `19401ce4ccb70fced9d530234015861693328e4e0cebfa650dd78e9344374b88` |
| `source_files_sha256` | `<r5 map>`, equal to freeze |
| `amendment_sha256` | equal to freeze |
| `authorized_stages` | `["a1-verify","a2-build-bounds","a2-verified-bounds"]` |
| `hosts` | `["127x04"]` |
| `seal_root` | `/mpac/sdicks02/jobs/clasher/v4-a1-body-seal-20261009-r4` |
| `seal_binding` | `authenticated-r4-exit-then-pin-actual-bytes` |
| `B_authorized` / `heldout_opening_authorized` | `false` / `false` |
| `valid_until_utc` | ≤ `2026-10-11T04:00:00Z` |
| `output_parent` | `/mpac/sdicks02/jobs/clasher/v4-a19-parallel-verification-r4` (or the r5 path, if r5 renames it) |
| `allow_serial_verify_handoff` | `true` |
| `handoff_policy` | `verify-then-retire` |
| `exclusive_physical_cpus` | `[0,1,2,3,4,5,6,7,8,9,10,11,47]` |
| `excluded_siblings` | `[64,65,66,67,68,69,70,71,72,73,74,75,111]` |
| `no_new_clasher_launches` / `x5_actual_exit_required` | `true` / `true` |
| Recommended unenforced extras | `x5_supervisor_exit_required=true` (O2), `min_mem_available_at_launch_bytes=85899345920` (O3) |

**Request.**
- `amendment.path` points at the deployed draft, which is rehashed.
- `stage_approval=null` for a1-verify.
- The deploy directory holds exactly the 21 (or r5) pinned `.py` files.

**`APPROVE_A2`, later, per stage:**
- `decision=APPROVE_A2` and explicit `authorized_stages`;
- the actual `body_seal_sha256`;
- `verification_execution_plan_sha256=<r5>` and `original_execution_plan_sha256=68e24722…`;
- exactly one `a1_verification_receipt`, chosen by the D3 rule;
- `B_authorized=false` and `heldout_opening_authorized=false`.

## Summary

**REJECT r4 bytes for freeze (narrow); the design is approved.**
- **Verified:**
  - all pins, including the 347 A18 files and 19 canonical plan fields;
  - the five r2-identical files;
  - 105/105 author tests on rerun;
  - C1, C3, C5 and §10, including PSI thresholds and the X5 gate, against live 04 with no false positives.
- **Blocking (F1, F2):**
  - The production r4 runner exits 1 on seeing STOP, and r4 accepts only −15. In 5 of 6 fixture runs at 04's measured lock cadence, the handoff failed after the irreversible STOP. That strands the A1 path: serial is retired with an exit-1 record, the parallel receipt is barred by C3, and new attempts are refused.
  - A post-STOP `guard()` can do the same.
- **Fix:** D1–D3, then a diff-only r5 check.
- **Operational:** O1–O4.
- **Throughput (O5):** 04's local I/O lock is held about 53% of the time, capping aggregate speedup at about 1.9×. A19 a1-verify is therefore unlikely to beat the serial verifier at all.

## Reviewer artifacts (`reviews/a19-reviewer-artifacts/r4/`)

| File | SHA-256 |
|---|---|
| `author-suite-rerun.log` | `1dc6811161c340f16656b270b552656aa3d10456198c9c02565ecf9bf84f9b50` |
| `probe-04-inventory-0406Z.json` | `143e6ebfe5d383f58390cd5034f8958d45967b7fb6f0d2fbc4316cf09158b43f` |
| `probe_04_inventory.py` | `74bbd4f8c70c5c4dd0b94f2db4dc42f8d602b7974e498a64bcbd793412fa67a9` |
| `probe-04-lock-occupancy.json` | `ce6d389d7cd744429c84971609a89d29743078ecca65759c003b3c6fc6c6e8d4` |
| `probe_04_lock_occupancy.py` | `d3dbd55fba39a49dd85fb2b7ce6e0bcf59aef2f0db39b03f494b6a1b894858e6` |
| `reviewer-tests-r4.log` | `e3d5bd3a67dd81239b02f1ff8c38194dbc7d38891b29fa8a86f5304d8a80222b` |
| `stop-race-outcomes.json` | `c230c5ef6253f65a177e2dd65b7f5f8d1e2d24efc66280084a4e74bd3e55636e` |
| `test_rev_a19_r4.py` | `96b812daa183cb5eb06bf88948187b447c3ddde0c3c4016c9ccb63d7c48b1941` |

## Addendum (04:20Z): the author's per-epoch inventory gap, and R3 on cores 12–19

**Confirmed from the code.**
- `run_pool` admits each epoch through `capacity()`, which forces a fresh `snapshot()`.
- That epoch's `launch.json` records only `utc`, `epoch`, `slot`, `identity` and `command`. Inventories are persisted only at launch, at handoff-decision, at pause/resume transitions and every 10 s.
- So two epochs admitted within one 10 s window share a telemetry snapshot. The exact inventory that admitted each epoch cannot be reconstructed afterwards.

**Ruling: required. Added as D4 to the r5 delta.**
- It is cheap and changes no science.
- It closes an audit gap in the policy the coordinator set: an inventory record at admission and at every epoch launch.
- Without it, a capacity or ownership dispute about a specific epoch cannot be resolved from the retained records.

**D4. Per-epoch admission inventory**, in `a19_pool.run_pool`:
1. **Same snapshot as the decision.** For each spawn, keep the exact snapshot object that the admitting `capacity()` call computed, for example by returning `(slots, snapshot)` or reading `guard.last_snapshot` immediately after that call. Don't take a second scan.
2. **Write and fsync before `Popen`.** Before that epoch's `Popen`, write `epoch-NN/admission-inventory.json` with the existing exclusive-create, fsync and directory-fsync `write()`. Contents:
   - `utc`, `epoch` and `slot`;
   - `slots_available` (the value that admitted it);
   - `pause_reasons`;
   - the full command-free snapshot: counts, PSI, MemAvailable, disk, inaccessible PIDs, training/X5 fields and inventory rows. Rows have no command lines, so none are added.
3. **Fail closed.** If the write fails, raise before `Popen`. That is the ordinary pool failure path, with serial left intact.
4. **Bind it in `launch.json`.** Add `admission_inventory={path, sha256}` to that epoch's `launch.json`.
5. **Reducer, optional.** Record the same for the reducer's `retained_child` launch with `slots_available=null`, since the reducer is not capacity-gated.
6. **Tests:**
   - **(a)** Two launches within one 10 s interval give two distinct files whose SHAs are bound in their `launch.json`. The second snapshot is fresh: it counts the first worker as owned, or the fake shows two distinct capacity calls.
   - **(b)** The file exists before `Popen`, for example because the fixture child reads it and fails if absent.
   - **(c)** An injected write failure gives no `Popen` and a pool `failure.json`.
   - **(d)** No command-line field is present.

D4 is an operational record only. Kernel, worker, reducer, common and A2 bytes stay unchanged. It joins D1–D3 in one r4→r5 diff. My quick verification will check:
- the diff touches only `a19_handoff.py`, `a19_authority.py`, `a19_pool.py` and tests, plus re-pins;
- byte identity of the five unchanged files;
- `check_package` passes (347 pins, 19 fields);
- the full suite passes on 3.12.12;
- my `r4/test_rev_a19_r4.py`: the F1/F2 tests must be inverted to expect `SERIAL_VERIFY_SUPERSEDED`.

**O6 (operator). R3 worker on 04 cores 12–19.**
- **Before the request is issued:** the R3 worker's temporary offline-CPU slot on cores 12–19 (siblings 76–83) must be vacated before any A19 launch request is issued.
- **Recorded proof:** its actual exit, by the identity the coordinator recorded at lease, is included in the pre-launch read-only inventory (O1).
- **Why:** its cores don't overlap A19's 0–11 and 47 (siblings 64–75 and 111), but it shares host memory/PSI and the 04 I/O lock (§6). The 04 lock is the bottleneck, so even a light Clasher reader there directly cuts A19 throughput.
- **Covered by O1:** no new Clasher launch on 04 during the attempt.
- **Current state:** a read-only check at 04:18Z showed no process above 1% CPU on cores 12–19 or 76–83, so the lease is not visibly in use right now. The condition still applies to its actual identity.

**The verdict is unchanged.** r4 is rejected for freeze; r5 = D1–D4. Operational conditions are now O1–O6, with O5 a non-binding recommendation.
