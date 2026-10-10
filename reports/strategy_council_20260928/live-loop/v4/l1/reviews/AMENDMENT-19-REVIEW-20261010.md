# Amendment 19 review: parallel fresh-process body verification (r2)

Reviewer: independent Claude reviewer for coordinator 0523ae6f, 2026-10-10, 03:17–03:50Z. The review was read-only. Code, tests and the package checker ran on 127x05 under nice 19, using Python 3.12.12 (the production minor version) and the system python3 3.8 for the checker. On 127x04 the reviewer only ran read-only `/proc`, `ps`, `sha256sum`, `ls` and metadata reads. Nothing was written there, no signal was sent, and no r4 file, A19 launcher or STOP was touched. The reviewer's own files are this review and `reviews/a19-reviewer-artifacts/`.

The brief named `reports/strategy_council_20260928/reviews/`. That directory doesn't exist; the A12–A18 reviews live in `l1/reviews/`, so this file sits beside them.

**Verdict: APPROVE_WITH_CONDITIONS.**
- **Scientific design:** sound. Parallel verification is semantically identical to frozen serial `verify_body` and is stricter in a few places. No path was found by which a wrong or unverified body passes.
- **Required before freeze (r3 delta):** three small code conditions, C1–C3.
- **Required before launch:** two operational conditions, C4–C5.
- **Follow-up review:** a diff-only check of r3 against these conditions is enough.

As submitted, r2 cannot run on 04 at all. Its inventory raises PermissionError there (the addendum case). Even after fixing that, the current 04 process mix leaves 0–2 worker slots under A19's own cap (§6).

## 1. Bytes

| Item | Recomputed SHA | Result |
|---|---|---|
| Draft r2 | bf53360f… | match |
| Package manifest | df7e185e… | match; `check_package.py --manifest-sha256 df7e185e…` PASS (19 original fields, 24 epochs, 10 production files, 347 A18 files) |
| Candidate plan | 544f419f… | match |
| Plan delta | 46838b61… | match |
| Source pins | 34ad146e… | match; production and auxiliary maps equal the plan's `operational_body_verification` maps; all 17 files re-hashed |
| Test receipt | 08c88e06… | match; the author's 48 tests re-run PASS on 3.8 and on 3.12 |
| Frozen verifier | 002d6894… | match in the snapshot and in 04's `BASE/execution/.../l1` |
| 04 deployed original plan / approval | 68e24722… / 19401ce4… | match (`v4-a1-parallel-r5/`) |
| 04 r4 `supervise.py` / `run_stage.py` | 884f0304… / 8c3c0523… | match the receipts copy and the hard-coded pins in `seal_barrier` |
| 04 SSH wrapper | 623d2587… | match `ssh_wrapper_sha256` |

**Independent delta check:**
- Compared by canonical bytes, not by Python `==` (which the checker uses): the candidate equals the original on all 19 original top-level fields and adds exactly `operational_body_verification`.
- r1→r2 changes only that field.
- 24 epochs, 362 source pins, 380 PYTHONPATH pins and 25 external pins are unchanged.
- `mem_available_floor_bytes` 30064771072 is exactly 28 GiB.

**Checker limits (minor).**
- It compares with Python `==`, which lets `1 == 1.0` through. The production `authenticate()` uses canonical bytes, so this matters only for review.
- It doesn't cross-check `source-pins.json` against the plan. The reviewer did, and they match.
- It verifies the 347-file snapshot in the repo copy, not in the 04 runtime tree. At runtime the frozen `authenticate_plan`/`verify_sources` does that, in every worker and in the reducer.

## 2. Scientific equivalence

**Kernel against frozen code.** `a19_kernel.recompute_epoch` is the frozen `recompute_body` loop body, line for line:
- the same `score_body_records(args_for(p,e,b))` for b=1..9 in ascending order;
- the same epoch-key check;
- the same `rank_body_cells`;
- the same `body_threshold`, `ranking` and `cell_sha256` (via frozen `digest`).

`reduce_and_compare` rebuilds exactly the frozen dict: schema, the 24 epochs, readiness, `FREEZE_SHA`, scope, `heldout_opening_authorized=False`, and `execution_plan_sha256` set to the **original** 68e24722. It then passes that through frozen `json_identity` and compares with Python `!=`, exactly as `verify_body` does. Two further checks are stricter than frozen code:
- an extra canonical-bytes comparison;
- extra structure checks (24 integer epochs, nine branch keys, ranking epoch and readiness).

Readiness consistency is checked against epoch 1. That is equivalent to the frozen sequential check.

**Differences found, none unsafe.**
1. **More `verify_sources(p)` calls.** It runs once per worker and in the reducer, not once at the end. This is stricter.
2. **Stricter seal parsing.** The seal is loaded with `a19_common.load`, which rejects duplicate keys and NaN. Frozen `load` is a plain `json.loads`, so this is also stricter: a NaN seal fails under frozen code too, because NaN ≠ NaN.
3. **Separate admission sessions.** The serial run uses one admission session for all 24 epochs; A19 uses one per epoch worker. `AdmissionSession` keys entries per epoch folder/kwargs and writes `epoch-NN.json`, so each epoch is admitted once and reused for its 9 bodies in both designs.
   - Any order-dependent process-local cache could only make the fresh results *differ* from the seal, which is a false fail.
   - It cannot make a wrong seal match.
4. **Extra owned-evidence filter (stricter).** It requires hosts 03/04/08 and excludes paths containing `heldout`, `journal` or ending in `-completion.jsonl`. The reviewer applied the filter to r4's real 13 completed seal sessions on 04: 28,190 entries (03: 16,734; 04: 7,446; 08: 4,010) and **0 forbidden**. There is no false-fail risk from this filter today.

**Reviewer tests** (`test_rev_a19.py` 55fade89…, all 17 PASS on 3.12, log `reviewer-tests.log` 82915908…).
- `KernelDifferential`. The frozen `recompute_body`/`verify_body` are AST-extracted (002d6894) and fed a synthetic scorer/ranker producing awkward JSON (0.1+0.2, 1e-308, -0.0, 2^53+1, unicode, nested floats). Every epoch result goes through the real worker `write` → file → `pinned` path in shuffled completion order. The seal is written with frozen `durable_json` formatting.
  - **12 inputs:** the kernel and frozen `verify_body` return byte-identical canonical values.
  - **300 random seal mutations:** none was accepted by the kernel while frozen rejected it. In 7 cases the kernel was stricter (int↔float, -0.0).
  - **300 worker-row mutations:** none was accepted except one confined to the *redundant* top-level `readiness` copy of a non-first epoch, where 64 vs 64.0 is equal under Python `==`. Frozen `recompute_body` applies the same `==` across epochs. The compared full value was unchanged, so this is not a defect.
  - **Swapped epoch rows** are rejected.
  - **The new plan SHA 544f419f** cannot replace 68e24722 in the comparison.
- `A2Binding`. This runs on the **real frozen module**: the exact 002d6894 file executed, with only its imported dependencies stubbed.
  - `bind` keeps the identical `__code__`, `__defaults__` and `__closure__`.
  - The private globals dict has the same key set, and every value is the *same object* except `verify_body`.
  - The module's globals are byte-for-id unchanged after binding.
  - `recompute_bounds` keeps the module's globals and never references `verify_body`.
  - Behaviour: each `build_bounds`/`verified_bounds` call invokes the callback first, before bound computation. A repeated call re-verifies before refusing with "Bounds already exist". A failing callback leaves no `bounds/`. `bounds/complete.json` carries 68e24722.

**No cached-receipt bypass.**
- The launcher has no skip or verify-from-receipt path.
- `fresh_verify` creates a new UUID root.
- `run_pool` uses `mkdir(exist_ok=False)` and exclusive `'x'` writes.
- The reducer requires matching `invocation`, Popen identity, reducer identity and every file pin.
- A2's prior A1 receipt is a prerequisite only, and the callback always recomputes all 216 branches.

**68e24722 stays inside the science.**
- The scientific `plan` passed to every frozen function is the *original* plan dict returned by `authenticate()`, not the candidate.
- The seal comparison and the A2 callback's `plan_sha` are hard-wired to `ORIGINAL_PLAN_SHA`.
- `build_bounds` receives 68e24722.
- 544f419f appears only in operational receipts.

## 3. Freshness and independence

**Fresh, isolated processes.**
- Each epoch is a separate `subprocess.Popen` exec of the pinned interpreter (no fork-inherited state, `close_fds` default).
- Each worker runs its own `start_new_session` group, its own full `authenticate()` (both plans through frozen `authenticate_plan`), its own seal barrier, its own admission session and its own result files.
- The parent records Popen identity (pid/starttime/boot) and its own `exit.json`. Acceptance requires the parent-observed `exit_code==0`, never a child claim.
- No controller flock is inherited, so `owner_lock` and `controller.lock` file descriptors are not passed to children.

**Fail-closed on bad results.**
- Duplicate, missing, partial, tampered, wrong-epoch or reused-identity results are all rejected (the author's five adversaries plus the reviewer's swap and mutation tests).
- Any failure writes `failure.json`, terminates only retained, identity-checked child groups and records each child's `exit.json`.
- There is no retry and no partial PASS.

**Source integrity.**
- The deployed directory must contain exactly the 17 pinned `.py` files, so no shadow module can be planted beside `a19_*.py`.
- Frozen code is imported from `CODE` after the a19 modules, and `verify_sources` constrains `clasher.*` origins.

## 4. Handoff safety

**Production supervisor tests.** These ran against the **production r4 `supervise.py` bytes** (SHA 884f0304, with only the ROOT, BASE and interpreter constants substituted). The author's real-process test used a simplified supervisor, not the production one.
- **Normal STOP:** STOP retires only the verify child. The verify exit is -15 with reason `Operational STOP or resource floor`, `failure.json` matches exactly, and the seal-exit stays 0. The supervisor exits 1, STOP is retained and the seal is unchanged. Result: `SERIAL_VERIFY_SUPERSEDED`.
- **Exit-0 race:** the verify child completes during the supervisor's 5 s poll after STOP was written. The handoff returns `SERIAL_ALREADY_COMPLETE` using the genuine `complete.json`, and no failure record exists.
- **Scientific failure:** a verify child exit of 1 is **never relabelled**. The handoff raises, r4's `failure.json` keeps `exit_code=1, reason=null`, and no `handoff.json` is written.
- **Residual (non-blocking).** If the verify child ignores SIGTERM, the production supervisor's `p.wait(timeout=60)` raises and the supervisor dies without writing `verify-exit.json` or `failure.json`. The child is left orphaned and live. A19 fails closed ("Owned supervisor handoff timeout") with its own `failure.json` and `handoff-intent.json`. This is r4 behaviour, not A19's; the operator rule should be not to retry and to report.

**Pre-STOP checks.** These are correct:
- seal exit 0 with the exact identity;
- the seal process gone, and STOP is never written while the seal is live;
- no pre-existing STOP or failure;
- the verify identity is fresh and on the seal's boot;
- the exact `verify` command;
- a live `/proc` PPID equal to the authenticated supervisor;
- the supervisor's `cmdline` containing the absolute `…/r4/supervise.py`. That was confirmed on 04: the supervisor runs as `python -B /mpac/…/r4/supervise.py`, so the attestation will match.

The adapter never signals r4 processes. The only r4 write is the exclusive STOP, plus A19's own `handoff-intent.json`.

**Race with the r4 supervisor.** The supervisor writes `verify-identity.json` before its loop, and the handoff waits for it. STOP is written only after the attestation. The remaining races are exit-0 (handled) and scientific failure (not relabelled).

**Finding H1 (drives C2).** The handoff is **irreversible**, and it happens *before* any capacity admission. `execute()` runs `serial_handoff` and only afterwards `run_pool`, whose `capacity()` may be 0. The pool then waits, launching nothing, until the approval deadline (reviewer test). On today's 04 (§6) this would retire a serial verifier that is otherwise ~12.7 h from completion and then stall with 0–2 slots.

## 5. Plan delta, pins, `check_package.py`

These checks pass (§1). Six further points:
1. **Approval binding.** The frozen authenticator accepts the candidate under a revised eight-key `APPROVE_A1`; extra top-level plan keys are not refused.
2. **Field binding.** `authenticate()` binds both plans, the exact eight A1 fields (seven equal to 19401ce4), the A19 freeze, the operational approval, the stage approval, pinned Python 3.12.12, SciPy 1.17.1, `PYTHONPATH`, the working directory and the SSH wrapper.
3. **Template.** `REQUEST-TEMPLATE.json` cannot pass because its placeholders fail the pins.
4. **Amendment SHA not re-hashed.** `amendment_sha256` in the freeze and operational records is only compared between the two records, never against the actual draft file. The coordinator must bind the real value (C5).
5. **Weak A2 prerequisite.** A *parallel* A1 prerequisite receipt is weaker than the serial one; see C3. The serial case requires the genuine `complete.json` and `verify-exit.json`. The parallel case accepts any pinned `verified.json` with the right fields, even from an attempt that later wrote `failure.json` (for example, the post-reduction `verify_sources` failed). Reviewer test `test_parallel_receipt_without_attempt_completion_is_accepted` shows this.
6. **Deadline.** `valid_until_utc` is capped at 2026-10-11T04:00Z. A2 needs two full verifications plus serial bound computation and the events copy, so the deadline may bind; expiry fails closed. A bound failure inside `recompute_bounds` happens before `bounds/` is created, so a retry isn't blocked.

## 6. Resources and fleet rules

**Placement.** On 04, cpu0–11 have siblings 64–75, cpu47 has sibling 111 and cpu52 has sibling 116. `configure_cpu` refuses any core whose siblings include 52/116, and the guard re-checks single-core affinity, nice 19, `CUDA_VISIBLE_DEVICES=''` and one math thread. There is no console user (`who` = 0) and load average is about 5.8. The ExIt r2 workers are pinned to 118–126, so there is no core overlap.

**I/O locks.** A19 uses the same `proofs/127xNN.io.lock` files with the same read, hash and records scope and the same reentrancy as r4's `run_stage.py`. The only differences are a non-blocking spin with `guard()` and function restoration in `finally`. Exclusion is the same.
- **Throughput note.** `record_rows` holds the host lock while it decompresses and JSON-parses each whole decoder stream, and it does so twice per match per branch. 03 holds about 59% of evidence entries, so if parsing is a large share of the 31.8 min/epoch, speedup is bounded near the number of source hosts (~2–3×), not the worker count.
- The draft's 1.5–3 h/call range is unmeasured. The seal child shows 5:13 h of CPU in 5:50 h elapsed, so per-process work is CPU-bound but lock occupancy is unknown.

**Addendum: PermissionError (confirmed, blocks launch, fixed by C1).**
- **Where it occurs.** On 04, four same-UID processes deny `/proc/<pid>/cwd` and `smaps_rollup`: two `sshd: sdicks02@notty`, `(sd-pam)` and `gnome-keyring-daemon`. Their `/proc` inode owner is still sdicks02, so the r2 `st_uid` filter admits them and `os.readlink` raises.
- **Effect.** The r2 `inventory()` catches only `FileNotFoundError` and `ProcessLookupError`, so the first `guard()` in the launcher raises. It also raises on 05 (reviewer test). This fails closed before any STOP, so it is not unsafe, but it makes the package non-functional.
- **Fix.** `reviews/a19-reviewer-artifacts/proposed_inventory_r3.py` (d3632c41…), tested; see C1.

**Capacity arithmetic.** At 03:23Z, after the in-progress capture-era cleanup, 25 Clasher-path processes remain on 04:

| Group | Processes | Notes |
|---|---:|---|
| ExIt r2 (`exit-r2-20261010-r1`) | 8 | Active fit, about 17.1 GB PSS, nice 10, cores 118–126. **Not capture-era.** |
| r4 | 4–5 | Supervisor, seal, two `[mux]` masters with `ControlPersist=600`, transient ssh |
| `backup_extended60` | 3 | |
| r16 load telemetry | 3 | |
| `verified-retention03` | 3 | |
| `recovery61` `parallel_verify` | 3 | |

- **Without C1.** 25 exceeds the cap of 16, so the launcher cannot start.
- **With C1 (counting the 4 inaccessible processes) and only ExIt left.** The count is 8 + 4 + 1 controller + 2 r4 masters (for up to 10 min after r4 ends). Capacity is `16−15−5 = 0` worker slots; it stays at 0 even after the masters expire.
- **Without conservative counting.** At most 2 slots (6.35 h/call).
- **Conclusion.** While ExIt r2 runs on 04, A19 has no useful parallelism under its own cap; the draft's 4.5–9 h total assumed 8–10 slots. This is a coordinator co-tenancy decision (C4), not a code defect.
- **Guard aborts.** The worker-side guard enforces the *host-wide* ≤16 count every second. Any transient extra process aborts the whole attempt: a coordinator monitoring ssh adds an `sshd` (inaccessible, counted under C1) plus a Clasher-marked command, and so would an ExIt helper. This is harmless to science but costly once the serial verifier has been retired, which is why C2 matters.
- **Scan cost.** Each guard scan also reads `smaps_rollup` for the ExIt processes (12 GB RSS) at about 1 Hz per worker. That is cheap but needless; see recommendation R1.

**Retiring residual groups through their own STOP mechanisms is sound, with these conditions:**
- authenticate each group's pid, starttime and boot plus its supervisor before STOP;
- write one record per group, and confirm that the bash → `time -v` → python chain fully exits with no orphan;
- never use pattern kills;
- check dependencies first: `verified-retention03`, the `recovery61` verifier/floors and the cache-handoff and floor monitors may guard evidence the live seal reads from 03/08. If in doubt, keep them and accept fewer slots;
- the authority is capture-era only: ExIt r2 is another thread's live job, and the r16 telemetry and `backup_extended60` groups are not capture monitors. None of these may be retired under that authority.

Some floor monitors also ssh to 127x13 and 127x14 (roader's split); retiring them is consistent with the fleet split.

## 7. Could a wrong or unverified body pass?

The reviewer found no path. Acceptance requires all of the following:
- 24 parent-observed exit-0 fresh execs;
- every pin rechecked by a fresh reducer process;
- frozen `json_identity` reconstruction with Python `==` *and* canonical-byte equality against the actual seal bytes;
- a seal rehash before, during and after;
- `verify_sources` everywhere.

The serial-complete path uses only the genuine r4 `complete.json`, `verify-exit.json` and receipt. Scientific failure is never relabelled. The only weakness is C3: the A2 prerequisite could cite a `verified.json` from an attempt that later failed. Even then, A2 re-verifies all 216 branches itself, so the risk is to provenance, not to the body.

## 8. Conditions

**r3 code delta.** Re-pin the plan and `source-pins.json`, update the test receipt, and get a diff-only follow-up review.

- **C1 — Conservative inventory (the addendum).** In `a19_resources.inventory()`:
  - Decide ownership by the *real* UID from `/proc/<pid>/status`.
  - On `PermissionError` for `cwd`, count the process against the cap and flag it inaccessible. Never exclude it and never let the exception escape.
  - On `PermissionError` for `smaps_rollup`, use resident bytes from `/proc/<pid>/statm` as an upper-bound PSS.
  - Keep `affinity=None` if it's unreadable.
  - Keep descendant marking for Clasher-marked parents.
  - Telemetry records `inaccessible_count` and those pids, with no command lines.
  - Adopt `proposed_inventory_r3.py` semantics and its two tests: injected cwd and smaps denial is counted, and the real host doesn't raise.

- **C2 — No irreversible STOP without admitted parallel capacity.** Choose one option.
  - **(a) Preferred: verify-then-retire.**
    - In the `a1-verify` branch, keep the existing `SERIAL_ALREADY_COMPLETE` pre-check.
    - Then run `fresh_verify` *while the serial verifier continues*: shared locks, r4 processes counted.
    - Call `serial_handoff` only after a successful `verified.json`. If serial completed meanwhile, record both receipts.
    - `complete.json` binds the parallel receipt and the handoff record.
    - Any parallel failure leaves r4 untouched.
  - **(b) Pre-STOP admission gate.**
    - Immediately before writing STOP, compute capacity with the C1 inventory, crediting only r4's supervisor and verify child (2) and *not* its mux masters.
    - Require at least `min_worker_slots_at_handoff`, an integer bound in the operational approval, ≥2, recommended 4.
    - Otherwise write `handoff-deferred.json`, write no STOP, and exit non-zero.
    - Also make a host-wide process-cap breach non-fatal unless it is sustained for ≥120 s, or enforce it only in the controller. Memory, disk and PSS floors stay immediate.
  - **Either option:** add a pool starvation rule. If there are zero active workers and capacity has been 0 for 30 consecutive minutes, fail closed with a record instead of waiting until the deadline.
  - Add tests: no STOP when capacity is below the minimum, or, for (a), no STOP after a parallel failure; and starvation fails closed.

- **C3 — Bind the A2 parallel prerequisite to a completed attempt.** When the prior receipt has schema `…a19-parallel-body-verification.v2`, require all of the following and add a rejection test (the reviewer's acceptance test must flip):
  - its path is `<output_parent>/a1-verify-<hex>/verification-<hex>/verified.json`;
  - the attempt-root `complete.json` exists with `stage=a1-verify`;
  - that `complete.json` lists the receipt descriptor (path and SHA) in `verification_receipts` and binds the same `body_seal_sha256`;
  - there is no `failure.json` in that attempt root.

**Operational, before launch.**

- **C4 — 04 co-tenancy and headroom.**
  - Before issuing launch authority, the coordinator records a fresh read-only C1 inventory.
  - Decide explicitly about ExIt r2: wait, relocate, or accept 0–2 slots.
  - Resolve the remaining non-capture groups only under their own authorities, as set out in §6.
  - Freeze new Clasher launches on 04 for the life of an A19 attempt.
  - Keep monitoring of 04 light (one ssh at a time).
  - No cap relaxation unless separately approved.
  - **Addendum (§11).** Launch only after X5 exits, per the 03:25Z ruling. Do not re-release the G filler onto 04 cores 0–11 or 47 (siblings 64–75, 111) while an A19 attempt is pending or running.

- **C5 — Exact bindings.** Bind the values in §9. Deploy the 17 r3 files byte-identically to `/mpac/sdicks02/jobs/clasher/v4-a19-review-r2` (or the r3 path pinned in the approval) with no other `.py` file. Re-hash 04's r4 state and identity at launch.

**Recommendations (non-blocking).**
- **R1.** Sample `smaps_rollup` only in the controller.
- **R2.** For the SIGTERM-ignoring residual, the operator should not retry and should report; any orphan retirement needs separate authority.
- **R3.** Record measured epochs/hour from the first wave before projecting A2 timing.

## 9. Approval fields to bind (after r3 passes the diff-only check)

**Revised `APPROVE_A1`.** Exactly 8 keys:

| Key | Value |
|---|---|
| `decision` | `APPROVE_A1` |
| `execution_plan_sha256` | `<r3 candidate plan SHA>` (not 544f419f, since r3 re-pins `operational_body_verification`) |
| `freeze_sha256` | `bd5b76433bf7eda6908ffe77418af3ae5dee27d87362ebb47d86c5721b17e7bc` |
| `file_layer_review_sha256` | `ff45e9edbffa606e020f3c91a4349074e2f19b0cbe431c44b1e70c359358d635` |
| `evidence_recovery_sha256` | `1adf50de13504df27a3c135e9e73a9b6861c99954f5f6795f80c380f36a1e35c` |
| `evidence_recovery_approval_sha256` | `64b1ebe435aa0a5cca2c9189e500fc43e279532cfae4aa4a671e3534497b4f60` |
| `assembly_sha256`, `a18_bindings` | Byte-identical (canonical) to 19401ce4 |

**A19 `FROZEN` record:**

| Key | Value |
|---|---|
| `decision` | `FROZEN` |
| `execution_plan_sha256` | `<r3 plan SHA>` |
| `source_files_sha256` | `<r3 10-file production map>` |
| `amendment_sha256` | `<actual r3 draft SHA>` (bf53360f only if the draft is unchanged) |
| Recommended extras | `independent_review_sha256` = this file's SHA; `followup_review_sha256` |

**`APPROVE_PARALLEL_BODY_VERIFICATION`:**

| Key | Value |
|---|---|
| `a19_freeze_sha256` | `<freeze record SHA>` |
| `execution_plan_sha256` | `<r3 plan SHA>` |
| `original_execution_plan_sha256` | `68e2472255ba5d1b79ec9f45217aa14208a31b6c44ccec890af332909efe8bc8` |
| `original_approval_sha256` | `19401ce4ccb70fced9d530234015861693328e4e0cebfa650dd78e9344374b88` |
| `source_files_sha256` | `<r3 map>` |
| `amendment_sha256` | `<r3 draft SHA, equal to freeze>` |
| `authorized_stages` | `["a1-verify","a2-build-bounds","a2-verified-bounds"]` |
| `hosts` | `["127x04"]` |
| `seal_root` | `/mpac/sdicks02/jobs/clasher/v4-a1-body-seal-20261009-r4` |
| `seal_binding` | `authenticated-r4-exit-then-pin-actual-bytes` |
| `B_authorized` | `false` |
| `heldout_opening_authorized` | `false` |
| `valid_until_utc` | ≤ `2026-10-11T04:00:00Z` |
| `output_parent` | `/mpac/sdicks02/jobs/clasher/v4-a19-parallel-verification-r2` |
| `allow_serial_verify_handoff` | `true` |
| If C2(b) | `min_worker_slots_at_handoff` ≥ 2 (recommended 4) |

**`APPROVE_A2`, per stage, later.** It is bound to an actual completed A1 receipt, which under C3 means a complete parallel attempt or the genuine r4 `complete.json`. It carries the actual seal SHA and both plan SHAs (68e24722 and the r3 plan), with `B_authorized=false` and `heldout_opening_authorized=false`.

## 10. Coordinator's r3 resource-policy direction (heads-up 03:30Z)

The proposal: an A19-owned process cap of ≤16 replaces the inherited all-Clasher ≤16 cap on home host 04. Host guards are MemAvailable ≥28 GiB, memory PSI full <20% sustained, the disk floor and I/O locks, never CPU 52/116, and no live non-perception GPU-fit loader. A conservative inventory is recorded at each launch.

**The direction is sound, provided the six points below are pinned in r3.**
- **Why it is sound.**
  - 04 is a Clasher-owned host with no console user, 128 threads and about 112 GB available.
  - The ≤16-total rule in the fleet notes is the *console-user* rule for shared hosts.
  - Owning the cap removes the dependence on co-tenants and transient monitoring ssh that §6 shows would leave 0–2 slots or abort attempts.
- **Read-only facts at 03:39Z.**
  - `/proc/pressure/memory` and `/proc/pressure/io` exist on 04 and read 0.00.
  - ExIt r2 PID 3727520 is a **live GPU fit**: 92% GPU utilisation, 2.5 GiB. It has 6 CPU-pinned child workers (cores 120–125), which look like data-loader workers.

1. **Define "A19-owned" by the process tree, not by path markers.** Owned means the authenticated controller, its retained Popen children by pid/starttime/boot, and all their descendants, including ssh clients. Shared mux masters are re-parented to init, so count them via the `a19-r2` ControlPath slot. Inaccessible processes stay in the C1 inventory *record*. The owned cap is then self-controlled, and a transient external process can no longer abort an attempt.
2. **Pin the GPU-loader guard exactly. As worded, it may match ExIt r2 and block A19 until ExIt ends.**
   - State the predicate precisely: which processes, matched how (GPU compute PID plus its descendants, or a specific job root).
   - State whether a match blocks *launch* or *aborts*.
   - State whether ExIt r2 is the intended target. If the intent is only to protect ExIt from starvation, use core disjointness plus PSI instead: A19 on 0–11 and 47 versus ExIt's 118–126 and its siblings 54–62. Then say so explicitly.
3. **Pin the PSI rule.** Specify the metric and window, for example `full avg60 ≥ 20%` on two consecutive 10 s samples, or `avg10` for a minimum duration. 20% "full" is a severe-thrash threshold; consider also stopping new launches at a lower level such as some avg60 ≥10%.
   - **Pause** new launches on PSI.
   - **Abort** owned groups on the MemAvailable floor, as in r2.
   - Make an unreadable `/proc/pressure` fail closed.
4. **Keep an owned-memory bound.** For example, owned PSS ≤48 GB, or a per-worker RSS ceiling. MemAvailable alone allows a slow leak to consume headroom that ExIt also relies on.
5. **Console users.** If `who` shows a console user at launch or during the run, stop launching new workers and drop to the fleet rule: 16 *total* Clasher processes with headroom. Record it.
6. **Inventory record.** Write it at launch, *at the handoff decision* (C2) and in telemetry: counts by owned, Clasher-marked, inaccessible and other, plus PSI and MemAvailable, with no command lines.

This policy **does not replace C2 or C3.** STOP stays irreversible, and verify-then-retire is still the preferred design. The I/O-lock throughput caveat (§6) still applies: 12 owned workers may not give 12× speedup when 127x03 holds about 59% of evidence reads under one lock. Measure the first wave (R3).

## 11. Monitor-retirement supplement (ae231ff9…)

**Bytes.** Recomputed: supplement ae231ff9, `retirement-summary.json` 089d6830 and `classification-67.json` e6f0b3bf all match. The counts are a=17 (5 r4/transport plus 12 conservatively held services), b=8 (ExIt/X5) and c=42 retired, with 14 groups and all wrapper exits 143. The held package df7e185e is unchanged: it was re-hashed and `check_package` passed at about 03:41Z.

**Effect on the evidence chain: none.**
- **The monitors were inert.** Every controller that the 42 retired monitors guarded was, per each group's own `status_before`, not live, not started, exited, or on unreachable 127x02. No retired monitor could have taken a protective action, so nothing that protected evidence was removed.
- **No pinned input changed.** No retired monitor's source, plan or lock file is in the A1 plan's 362, 380 or 25 pins. The supplement's preservation audit records no deletion and no source, plan, status or lock mutation. A SIGTERMed process releases its flocks on exit, and the lock files themselves persist.
- **The seal is healthy.**
  - The supplement records r4 authenticated with ticks advancing at 03:30:38Z.
  - The reviewer's own 03:40Z read-only check shows the seal worker 2499719 live: 6:06:50 elapsed, 5:28:42 CPU, no STOP, failure, exit or complete files.
  - The seal is a full deterministic recomputation, and A1 verification, serial or A19, recomputes all 216 cells against pinned inputs. Any input change would fail verification rather than pass silently.
- **Lock contention only.** The retired monitors took the same `v4-queue-independent-verifier-20261009-r1/proofs/<host>.io.lock` files (including 04 and 08) every cycle. Retiring them removes a small source of contention with the seal's source reads. That changes timing only, and no timing is admitted scientifically (A12–A18). Don't mix pre- and post-03:23Z seal throughput into one throughput baseline (R3).
- **The group-1 race.** This was a single-shot post-SIGTERM `/proc` observation that saw the exiting process. It is retained and does not touch the evidence. The A19 handoff does not have this pattern: it polls `live()` with an identity comparison, treats Z/X as not live, and runs inside a bounded loop.

**Effect on this review.**
- **§6 and C4.** Consistent. The 25 remaining processes are exactly a+b. The newer 03:25Z ruling preserves the 12 services, consistent with C4's "only under their own authorities". The all-Clasher cap is replaced in r3 by the §10 owned-cap policy.
- **§10 point 2 is resolved in intent.** COORDINATOR.md (b9e76937) says "Launch only after X5's fit exits", and X5 is the ExIt r2 fit on 04, expected around 06–07Z. The GPU-loader guard is therefore *meant* to block A19 until X5 exits; that is before the seal's expected end at 08:30–09:00Z, so no delay is expected. r3 must still pin the predicate exactly. A loader that appears during an A19 attempt should **pause new launches**, not abort owned workers. The 85.8% PSI-full trip recorded at line 1665 of COORDINATOR.md is the right precedent for the PSI guard.
- **New item added to C4: G filler.** COORDINATOR.md records the G teacher top-up as released onto 04 physical cores 0–47, pending re-release after X5. The reviewer checked read-only that G is not running on 04 now. G must **not** be re-released on 04 cores 0–11 or 47 (or their siblings 64–75 and 111) while an A19 attempt is pending or running. Otherwise G's load will trip A19's PSI and core guards or contend with its workers.
- **No new defect** in the r2 package. Verdict and conditions are unchanged, apart from this C4 addition.

## Summary

**APPROVE_WITH_CONDITIONS.**
- **Bytes:** all package pins match: draft bf53360f, manifest df7e185e, plan 544f419f, delta 46838b61 and pins 34ad146e. The 19 original fields are canonically unchanged and the 04 frozen and r4 files match.
- **Science:** sound. Reviewer tests (17 PASS) found the kernel equal to frozen `verify_body`, with 0 kernel-only accepts in 600 mutations. On the real frozen module, the A2 binding keeps the identical code and untouched globals. 68e24722 stays in the seal and bounds, and there is no cached bypass. The handoff is correct against the production r4 supervisor in three scenarios, including the exit-0 race, and never relabels a scientific failure.
- **Code conditions (r3):**
  - **C1:** the PermissionError inventory fix with conservative counting (confirmed on 04 and 05).
  - **C2:** no irreversible STOP without admitted capacity; verify-then-retire is preferred.
  - **C3:** the A2 parallel prerequisite must come from a completed attempt.
- **Operational conditions:**
  - **C4:** with ExIt r2 (8 processes) on 04, A19's own cap leaves 0–2 worker slots.
  - **C5:** exact bindings.

A diff-only r3 check is enough.

**Coordinator's r3 policy (§10).** Sound as a direction if r3 pins:
- the owned tree;
- the exact GPU-loader predicate (it currently matches live ExIt r2);
- the PSI metric and window;
- an owned-memory bound;
- the console-user fallback.

C2 and C3 still apply.

**Monitor-retirement supplement (§11).** It has no effect on the evidence chain:
- all 42 retired monitors guarded controllers that were not live, exited, or unreachable;
- none of their files is in any pin set;
- the seal stayed healthy;
- removing them only reduces lock contention.

The "no live fit loader" guard is meant to block until X5 (ExIt r2) exits, at about 06–07Z. C4 now also keeps the G filler off A19's cores.
