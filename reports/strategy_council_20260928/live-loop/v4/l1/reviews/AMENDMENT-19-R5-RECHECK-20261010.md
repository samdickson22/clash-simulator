# Amendment 19 r4→r5 diff-only re-check

**Reviewer:** the same independent Claude reviewer as r2 (`AMENDMENT-19-REVIEW-20261010.md`, c2a092da…) and r4 (`AMENDMENT-19-R4-DELTA-REVIEW-20261010.md`, 8820200841ce…), for coordinator 0523ae6f, 2026-10-10, about 04:38–05:00Z.

**Review was read-only.**
- **127x05 (nice 19):** suites ran on Python 3.12.12 and `check_package.py` on system 3.8.
- **127x04:** one read-only `ls`/`ps`/`meminfo`/`who` probe at 04:41Z. Nothing was written there and nothing was signalled.
- **This file:** the r4 review is pinned in the r5 package manifest, so this is a separate file rather than an append. The r4 file is unchanged (8820200841ce…).
- **Reviewer files:** this file and `reviews/a19-reviewer-artifacts/r5/`. r2 and r4 artifacts are unmodified.

## Verdict: APPROVE_WITH_CONDITIONS. The r5 code bytes are approved for freeze.

D1–D4 are implemented exactly, and my r4 F1/F2 race tests now pass with the expected `SERIAL_VERIFY_SUPERSEDED` outcome. In 18 runs that use the production supervisor and the production `lock()`, 18 superseded: 14 by `runner-stop-check` and 4 by `supervisor-sigterm`.

None of the conditions (E1–E3 in §5) needs a code change under the r5 bytes. They concern binding fields, the deadline and document hygiene.

**The deadline needs a code change if the coordinator wants 10-13.** `a19_authority.py:50` still hard-caps `valid_until_utc` at 2026-10-11T04:00Z.
- The coordinator's intended cap of 2026-10-13T04:00Z would be **rejected** by `authenticate()` with "Approval/cache hardstop".
- Raising it needs a one-constant production change and a re-pin (E1).

## 1. Bytes, scope and minimality

| Item | Result |
|---|---|
| Package manifest 4e8ba2bd… | All 38 member SHAs match. `check_package.py --manifest-sha256 4e8ba2bd…` **PASS**: 19 original fields, 24 epochs, 10 production files, 347 A18 frozen pins. |
| Held r4 manifest | bef7f189… still matches. The r4 package is untouched. |
| Plan 7d2a92bc… | 19 original top-level fields are canonically equal to 68e24722. The only added field is `operational_body_verification`. |
| Plan changes from r4 | `revision` A19-r5; new `epoch_admission_inventory` and `handoff_retirement_paths`; `parallel_a1_prerequisite` → `canonical_serial_if_complete_else_single_completed_superseding_parallel`; both file maps. |
| Source pins eb56e782… | `production` and `auxiliary` are canonically equal to the plan maps. All 10 + 13 files were re-hashed. |
| `r4-r5-source.diff` 7e189c51… | I regenerated it from the held r4 files and the r5 files, and it is **byte-identical**. Every `.py` file in r5 appears in the delta JSON 504b89ac…, and every r4 SHA in that JSON matches the held r4 file. |
| Unchanged production files | `a19_kernel` 5ec530be, `a19_worker` a19cf853, `a19_reduce` 8a30e2a8, `a19_common` c4f1b9ba, `a19_a2` 36c6b364 and `a19_resources` 9661b4ac are **byte-identical to r4**, and the first five are byte-identical to r2. |
| Changed production files | `a19_handoff`, `a19_authority`, `a19_pool` and `a19_launcher` only, as declared. |

**Authority** changes only three things:
- the revision string;
- `output_parent` → `…-verification-r5`;
- the D3 block in `seal_barrier` and `completed_parallel_prerequisite`.

**Pool** changes only D4.

**Launcher** changes only three lines:
- the `retain_handoff_failure` import;
- `CLASHER_SSH_SLOT=a19-r5`;
- a two-line exception hook.

The test changes are four new or adapted files. `check_package.py` changes only the r5 filename and revision.

**Is the launcher hook needed and correct?** Yes on both counts, and it is minimal.
- **Necessary.** `complete.json` is written *after* `serial_handoff` returns, so a write error there is a post-STOP exception outside the handoff's `try`. Without the hook, the attempt would hold STOP, a SUPERSEDED `handoff.json` and `failure.json`, but no `handoff-failure.json`. That would violate D2 as written.
- **Correct.**
  - `retain_handoff_failure` does nothing unless this attempt's `handoff-intent.json` exists **and** the STOP's `handoff_intent_sha256` equals its SHA. A foreign or absent STOP, and every A2 or pre-STOP failure, therefore record nothing.
  - The first record wins, so when the handoff already wrote one the launcher's call does nothing.
  - Its own errors are swallowed, so the original exception and `failure.json` still propagate.
  - `receipts[0] if 'receipts' in locals() and receipts else None` is safe for an exception raised before `receipts` is assigned.
- **Residual.** A persistent filesystem failure, or SIGKILL/SIGTERM of the controller after STOP, can leave no new record. Intent, STOP and proof remain. The author discloses this, and nothing more can be guaranteed.

## 2. D1–D4, item by item

| Item | Status | Evidence |
|---|---|---|
| **D1** | **Met exactly** | See D1 detail below. |
| **D2** | **Met** | See D2 detail below. |
| **D3** | **Met** | See D3 detail below. |
| **D4** | **Met** (optional reducer record not done; acceptable) | See D4 detail below. |
| R4 | Met | `handoff.json` in the SERIAL_ALREADY_COMPLETE case now carries `stop_written`, `stop` and `handoff_intent`, including exit 0 after STOP. |

**D1 detail.** After STOP, the handoff requires all of the following:
- `verify-exit.identity == verify_identity` and `sha(verify.log) == log_sha256`;
- the STOP SHA equals the one A19 wrote, and the seal is unchanged;
- `failure.json == {utc, stage: verify, exit_code: ex.exit_code, reason: ex.reason}`.

It then accepts exactly two shapes:
- **−15:** the reason must be `Operational STOP or resource floor`. Recorded as `supervisor-sigterm`.
- **1:** the reason must be null or that string, the last non-empty line must be exactly `RuntimeError: Operational stop requested`, the log must contain no `Body seal differs`, `verify-exit.utc ≥ STOP.utc` (both use microsecond isoformat), and there must be no `complete.json`. Recorded as `runner-stop-check`.

`RuntimeError: Resource floor`, a scientific failure, an earlier timestamp, a changed log or a changed STOP each fail closed and are never relabelled. I checked that the signature is robust in production:
- The frozen `lock()` checks STOP *before* the floor.
- Of the 333 frozen `.py` modules, 23 have broad `except` clauses. All of them either re-raise unchanged or sit off the `verify_body` path.
- `admission_session` and the unwind of `queue_audit_io.records` raise nothing new, so the traceback's last line stays the RuntimeError.

**D2 detail.**
- After STOP the loop calls only `guard.record('post-stop-wait')`, wrapped so it cannot raise, plus the bounded wait, which gets a fresh 90 s.
- `guard()`, `capacity()` and the deadline are never called after STOP.
- Any exception from the STOP write onward goes to `except BaseException`. That path writes `handoff-failure.json` binding the parallel receipt, the STOP path and SHA, and the intent path and SHA, then re-raises.
- The launcher also catches a final `complete.json` error (see §1).

**D3 detail.**
- **`seal_barrier`:** if `SEAL_ROOT/complete.json` exists, the A2 receipt path must equal `SEAL_ROOT/seal-verification.json`, and the existing serial branch also re-checks `complete.json`, `verify-exit` and the plan, approval and verifier pins. Otherwise the receipt must use the parallel v2 schema and pass `completed_parallel_prerequisite`.
- **`completed_parallel_prerequisite`:** now requires `handoff.status == SERIAL_VERIFY_SUPERSEDED`. SERIAL_ALREADY_COMPLETE is rejected, so a parallel receipt can never be canonical while a genuine serial completion exists.
- **Race:** none. SUPERSEDED implies serial was retired without completing, so `complete.json` cannot appear later.

**D4 detail.**
- The inner admission loop now calls `capacity()` once per spawn and deep-copies `guard.last_snapshot` and `pause_reasons` right after that call. In production `Guard.capacity()` sets `last_poll=0` and forces exactly one fresh `snapshot()`.
- `epoch-NN/admission-inventory.json` holds `{utc, epoch, slot, slots_available, pause_reasons, snapshot}`. It is written with exclusive-create, fsync and directory fsync **before** `Popen`, and its descriptor is bound in `launch.json`.
- If the write fails, the existing path writes pool `failure.json` and nothing is spawned.
- The rows carry no command lines; this is unchanged resources code, already verified in r4.

## 3. Tests

**Author suite.** **145/145 PASS** on rerun (3.12.12, nice 19, 216.9 s; `r5/author-suite-rerun.log`). This matches the receipt 8bcbf207…, which reports 145 tests in 217.4 s.

**My r4 tests with F1/F2 inverted, plus r5 additions.** `r5/test_rev_a19_r5.py`: **20/20 PASS** (254.8 s, under `taskset -c 40`). It is the r4 file with `PKG` pointing to r5 and only the F1/F2 assertions inverted. My original `killpg(SIGKILL)` cleanup is kept; the author's copy weakens it to `kill(SIGTERM)`, which is test hygiene only.

**F1 inverted (single run).** The fast cadence gives SUPERSEDED via `runner-stop-check`, with exit 1 and `failure.json` retained. A new attempt is still refused at the pre-check, which is correct.

**F1 at the measured 04 cadence** (hold 1.07 s, gap 0.85 s, random phase against the 5 s poll). Outcome files: `stop-race-outcomes-measured.json` and `-sweep.json`.

| Runs | Result | `runner-stop-check` | `supervisor-sigterm` |
|---|---|---:|---:|
| Measured cadence, seeds 0–5 | 6/6 SUPERSEDED | 5 | 1 |
| Measured cadence, seeds 6–11 | 6/6 SUPERSEDED | 3 | 3 |
| Fast cadence | 6/6 SUPERSEDED | 6 | 0 |

That is 18/18 in total, and both paths are exercised under the production supervisor 884f0304 and the AST-extracted production `lock()` 8c3c0523.

**F2 inverted.** A guard that raises after STOP gives SUPERSEDED via `supervisor-sigterm`.

**New r5 tests:**
- **D2:** a guard object whose `__call__` raises the deadline error and whose `record` raises a PSI error after STOP still gives SUPERSEDED, and `stop`, `stop_written` and `handoff_intent` are bound.
- **D2:** a seal mutated after STOP fails with "Original seal changed during handoff". It writes a `handoff-failure.json` that binds the exact STOP, intent and proof, and writes no `handoff.json`.
- **`retain_handoff_failure`:** with no intent, or a foreign STOP, nothing is written. The first record wins.
- **D3:** `completed_parallel_prerequisite` accepts SUPERSEDED and rejects SERIAL_ALREADY_COMPLETE.
- **D4 with the production `Guard`:** `snapshot`, `check_snapshot` and `launch_blockers` are stubbed with generation counters. Each of the 24 admission files holds exactly the snapshot generation produced by its admitting `capacity()` call. No rescan happens before `Popen`, `slots_available` equals that snapshot's decision, and all 24 SHAs are distinct and bound.

**Checker.** `check_package.py` PASS (§1).

## 4. Regressions: none found

**C1 and §10.2–§10.6.** `a19_resources.py` is byte-identical, so ownership, real-UID and inaccessible accounting, the X5 gate, the PSI thresholds, the floors, the console pause and telemetry are unchanged. My PSI boundary tests pass again.

**C2.** The launcher's ordering is unchanged:
1. the pre-check;
2. `fresh_verify`;
3. `guard()` and `verify_sources`;
4. `serial_handoff`;
5. `complete.json`.

The pre-STOP part of the handoff is unchanged except that it captures `intent`. These tests still pass:
- `check_only` writes nothing;
- no STOP without this attempt's proof;
- a seal change blocks STOP;
- serial completing first gives ALREADY_COMPLETE with no STOP;
- a second completion raises `FileExistsError`;
- scientific failure is never relabelled;
- the ignored-SIGTERM residual is unchanged.

**C3.** Strictly tightened (SUPERSEDED only).

**C5.** Unchanged apart from `output_parent` r5. Still unchanged:
- the amendment is rehashed against the freeze and the operational approval;
- the 8-field A1 approval;
- the operational fields;
- pinned Python and `PYTHONPATH`;
- the exact deploy set.

**§10.1.** Unchanged.

**Scientific path.** Kernel, worker, reducer, common and A2 binding are byte-identical, and science stays on 68e24722.

**Live 04 at 04:41Z (read-only).**
- The seal is still running: 2499718/2499719 on CPU 52, nice 19, elapsed 07:07:51. There is no `seal-exit`, STOP or failure yet.
- X5 is still live: fit 3727520 and supervisor 3727388.
- MemAvailable is about 107 GiB, there are no console users and no A19 directories exist.
- So O1–O4 cannot hold yet, and A19 cannot launch now in any case.

## 5. Conditions

- **E1. Deadline.**
  - **Under the r5 bytes**, `valid_until_utc` must be ≤ `2026-10-11T04:00:00Z`; anything later is rejected by `a19_authority.py:50`.
  - **To use the coordinator's 2026-10-13T04:00Z,** change only that constant to `datetime.datetime(2026,10,13,4,…)`, then re-pin the authority SHA, the plan, `source-pins` and the manifest.
    - I will accept that as a one-hunk diff-only check.
    - If A20 goes ahead, fold the change into A20's combined re-pin.
    - The guard deadline, worker/reducer `authenticate` and the post-STOP exemption need no other change.
  - **Why it matters even without A20.** Serial A1 is expected around 21:30–22:00Z on 10-10, and each A2 verification takes about 6.8 h or more (O5). So the A2-only fallback would also hit the 10-11T04Z cap.
- **E2. Amendment text binding.**
  - **The problem.** The r5 draft (2b09f87a…) is a terse delta that no longer restates r4 §1–§8: scope, C1 ownership, the PSI policy, C2/C3 and the deploy contract. It also does not cite the r4 draft by SHA.
  - **Fix, either of:**
    - The FROZEN record must add `incorporated_amendment_sha256 = b43a39790c4977e8f2c9548429578901a5a44ca4d9e13868e5b80374c9351cef` (the r4 draft, normative except as amended by D1–D4) and `review_response_sha256 = 273b082622ea08b16ad1190dade51e9010e6090e30fc3da83697cb0ca7298d84`.
    - Or the author issues a document-only r5.1 draft that incorporates these. That changes only `amendment_sha256` in the freeze, the operational approval and the request, not any code pin.
- **E3. OPERATOR.md corrections, before use** (not code):
  - **(a) Deploy count.** OPERATOR says to deploy "exactly the 21 pinned Python files". r5 pins **23** (10 production + 13 auxiliary), and `authenticate` requires the deployed `*.py` set to equal the plan maps, so deploying 21 fails closed.
  - **(b) Receipt wording.** "If it completes during parallel work, bind both receipts" must read: `complete.json` corroborates both, but **A2 binds only the serial receipt** (D3, enforced).
- **O1–O6 carry over unchanged.**
  - O1: lease, cores, no new launches, one SSH, and a fresh inventory with no blockers.
  - O2: X5 fit **and** supervisor 3727388 have exited.
  - O3: MemAvailable ≥ 80 GiB.
  - O4: authenticated seal exit.
  - O5: throughput recommendation.
  - O6: the R3 worker on cores 12–19 has actually exited.
- **Launch policy.** I endorse the coordinator's recorded policy: A19 on A1 only if r5 **and** A20 are both approved and O1–O6 hold; otherwise serial A1, with A19 reserved for A2.
- **If A20 changes any of the 10 production files,** its combined plan, source map and freeze **supersede** the r5 values in §6. The r5 D1–D4 hunks must carry forward byte-identically, and A20's diff must be confined to its declared lock-scope hunks plus E1.

**Non-blocking residuals.**
- **Post-STOP telemetry is stale.** It repeats the pre-STOP `last_snapshot` because `record` does not rescan. It is bounded at about 5 rows/s for at most 90 s.
- **A shutdown trailer would fail closed.** If an interpreter-shutdown "Exception ignored…" trailer followed the runner's traceback, D1 would fail closed. That strands the A1 path but gives no wrong science, and I found no source for such a trailer.
- **The ignored-SIGTERM residual is unchanged from r4.**

## 6. Approval fields to bind (r5 bytes; superseded by A20's combined values if A20 re-pins)

**Revised `APPROVE_A1`.** Exactly 8 keys:

| Key | Value |
|---|---|
| `decision` | `APPROVE_A1` |
| `execution_plan_sha256` | `7d2a92bc06315c7a1fcabc2636c9818cec1784446ee35fd6b9b5399c28f4fc12` |
| `freeze_sha256`, `file_layer_review_sha256`, `assembly_sha256`, `evidence_recovery_sha256`, `evidence_recovery_approval_sha256`, `a18_bindings` | canonically byte-equal to 19401ce4, as in my r4 §9 |

**A19 `FROZEN`:**

| Key | Value |
|---|---|
| `decision` | `FROZEN` |
| `execution_plan_sha256` | `7d2a92bc…` |
| `amendment_sha256` | `2b09f87a742a072bcb411708a332331c9463669efb2465903c54b6a0efea3839`, or the r5.1 document SHA under E2, rehashed from the deployed file |
| E2 extras | `incorporated_amendment_sha256=b43a3979…`, `review_response_sha256=273b0826…` |
| Recommended extras | `independent_review_sha256=c2a092da…`, `r4_delta_review_sha256=8820200841ce…`, `r5_recheck_review_sha256=<SHA of this file>`, `package_manifest_sha256=4e8ba2bd669eaaf4ff82f885caf7ffecb702dfe796f52f61174ddb9c530de64d` |

`source_files_sha256` must be exactly these 10 files; the canonical map SHA is `60f931e9…`.

| File | SHA-256 |
|---|---|
| `a19_a2.py` | `36c6b364234ef3be47a86294c836b29fc313e7313dc9f20bf0189fd05985518e` |
| `a19_authority.py` | `cf0727ecdbec4483344e16530381ddb144cc8c7eb83623a19e9cffb36d7812a1` |
| `a19_common.py` | `c4f1b9bae3aa88982a275700078fef4941aea3218258ca904080dba2a7d88d3c` |
| `a19_handoff.py` | `f652aaf57ec1fe887d8c00143756afd9bc8f4f8c73ac6770ef4ae481a3a28f87` |
| `a19_kernel.py` | `5ec530be87b47b90d93e48dce9a77d0b1cb85be45e131408f6d0fa692fdcaee4` |
| `a19_launcher.py` | `a7da10bc749ed0db7f08698b75842472d84ee0a60a1883fec0da82e88f75285e` |
| `a19_pool.py` | `f686a6f9d9f11ceba74328a8ed66f7b31d6e5fe8eab2c26d13a11955e50c3c22` |
| `a19_reduce.py` | `8a30e2a87b6ed8e7001e42f68fd12a5b503224356e0054686397382905288c4c` |
| `a19_resources.py` | `9661b4aca2c05d3fee3c1e013c06bdc5044406cbb373c731ddc603e7ba1a8eb0` |
| `a19_worker.py` | `a19cf8536320ac440658dc84e6c92f9b8dc6169b3135d3b509facebc3c77d54e` |

**`APPROVE_PARALLEL_BODY_VERIFICATION`.** All keys are enforced by `authenticate`:

| Key | Value |
|---|---|
| `decision` | `APPROVE_PARALLEL_BODY_VERIFICATION` |
| `a19_freeze_sha256` | `<freeze record SHA>` |
| `execution_plan_sha256` | `7d2a92bc…` |
| `original_execution_plan_sha256` | `68e2472255ba5d1b79ec9f45217aa14208a31b6c44ccec890af332909efe8bc8` |
| `original_approval_sha256` | `19401ce4ccb70fced9d530234015861693328e4e0cebfa650dd78e9344374b88` |
| `source_files_sha256` | the 10-file map above, equal to the freeze |
| `amendment_sha256` | equal to the freeze |
| `authorized_stages` | `["a1-verify","a2-build-bounds","a2-verified-bounds"]` |
| `hosts` | `["127x04"]` |
| `seal_root` | `/mpac/sdicks02/jobs/clasher/v4-a1-body-seal-20261009-r4` |
| `seal_binding` | `authenticated-r4-exit-then-pin-actual-bytes` |
| `B_authorized` / `heldout_opening_authorized` | `false` / `false` |
| `valid_until_utc` | ≤ `2026-10-11T04:00:00Z` (E1; up to 2026-10-13T04:00Z only after the E1 constant change and re-pin) |
| `output_parent` | `/mpac/sdicks02/jobs/clasher/v4-a19-parallel-verification-r5` |
| `allow_serial_verify_handoff` | `true` |
| `handoff_policy` | `verify-then-retire` |
| `exclusive_physical_cpus` | `[0,1,2,3,4,5,6,7,8,9,10,11,47]` |
| `excluded_siblings` | `[64,65,66,67,68,69,70,71,72,73,74,75,111]` |
| `no_new_clasher_launches` / `x5_actual_exit_required` | `true` / `true` |
| Recommended unenforced extras | `x5_supervisor_exit_required=true` (O2), `min_mem_available_at_launch_bytes=85899345920` (O3), `r3_worker_exit_required=true` (O6), `requires_A20_for_a1_verify=true` (launch policy) |

**Request.**
- Deploy to `/mpac/sdicks02/jobs/clasher/v4-a19-review-r5` with **exactly the 23** pinned `.py` files.
- `amendment.path` points at the deployed draft.
- `stage_approval=null` for a1-verify.
- `CLASHER_SSH_SLOT=a19-r5`.

**`APPROVE_A2`, later, per stage:**
- explicit `authorized_stages`;
- the actual `body_seal_sha256`;
- `verification_execution_plan_sha256=7d2a92bc…` and `original_execution_plan_sha256=68e24722…`;
- `B_authorized=false` and `heldout_opening_authorized=false`;
- **exactly one** `a1_verification_receipt`. Use the serial `SEAL_ROOT/seal-verification.json` if `SEAL_ROOT/complete.json` exists; otherwise the `verified.json` of the single completed SUPERSEDED A19 attempt. This rule is now enforced in `seal_barrier`.

## Summary

**APPROVE_WITH_CONDITIONS. The r5 code is approved for freeze.**
- **Scope.** Only the declared files changed; I regenerated the diff byte-for-byte. The launcher hook is necessary, correct and minimal. The other six production files are identical to r4.
- **D1–D4.** Met exactly.
- **Tests.** Author suite 145/145; my inverted r4 tests plus the r5 additions 20/20. 18/18 runs with the production supervisor and `lock()` superseded (14 runner-stop-check, 4 sigterm).
- **Checker.** PASS.
- **Regressions.** None in C1–C5 or §10.
- **Conditions:**
  - **E1:** the code caps validity at 10-11T04Z, so 10-13 needs a one-constant change and re-pin.
  - **E2:** bind the r4 draft by SHA (`incorporated_amendment_sha256`).
  - **E3:** fix the OPERATOR file count (23, not 21) and the receipt wording.
  - **O1–O6** carry over.

## Reviewer artifacts (`reviews/a19-reviewer-artifacts/r5/`)

| File | SHA-256 |
|---|---|
| `test_rev_a19_r5.py` | `e1f16db6aea4ffc1084b470884ccd65db55690988136632271b7e3c67d3a7b5b` |
| `reviewer-tests-r5.log` | `129483768465781ac6866e0f7603488b0ab14cc261c163967a2752cca32e0f86` |
| `author-suite-rerun.log` | `3bb8ca8ec2f6757b7668b508a123ec357fad92c420a215fa7abd47e8911ca813` |
| `stop-race-outcomes-measured.json` | `f3548310cf1f0696016cef3858c0991e4924a79ce654022473bbdf0d92feb020` |
| `stop-race-outcomes-sweep.json` | `43e6075d8942f8a721d9ba54bfa77fc9a40270812785792429eae42a0d012b4d` |
