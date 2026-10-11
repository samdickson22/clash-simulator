# SOL independent re-review: K4S Mac measurement and END, r2

**Verdict: REJECT.** The rate-name, SD1-schema, statistic, repeat-row, committed-TIERS-receipt and classification-seal fixes are substantial and work as described. However, the actual END producer cannot use the new evidence with the frozen background worker, and genuine multi-host producer receipts cannot pass the pool's whole-pins equality check. Remaining provenance and seal gaps can admit unsupported timing evidence. F-8 is not ready to freeze.

Reviewed `/mpac/sdicks02/repos/clasher-k4s-prep`, 2026-10-11, HEAD `201db04c99da5ae5277f7f15498d839c467cf0f1`. This is an independent review of code written by other agents. Governing sources read: PREREG-K4S-DRAFT-r3 §1.4, §1.5, §4.5, §5.4; CONFORMANCE-r2 N2/F-8; RECHECK-r3 R3/R5; TIERS r3 §6–§7; K4S-SPEC §4/§8; relevant frozen e4v3 source and contracts. Reviewed all requested Mac/END files, the r1 review and author's Round 2 mapping, and the reporting supervisor's source.

No network, SSH, Mac/fleet contact, native/game execution, or game outcome data was used. Repository files were read only. Additional reproductions used synthetic inputs in memory or read the synthetic pytest fixtures; no reproduction mutated those fixtures. The required pytest suite creates temporary synthetic receipts/Git repositories as part of its existing tests; no commit or push was performed in the worktree. This review is the sole authored review artifact.

## Round-1 findings

1. **RESOLVED — SD1 schema incompatibility.** `mac/k4s_logic.py:760–788` now reads the declared nested schema, checks artifact/checkpoint/calibration/threshold/mode, requires exactly the eight SD1 inference-source keys and re-hashes them. `mac/test_measure_k4s.py:451–488` exercises the shipped manifest structure and source inventory. The absent local `student-source/exit_r3/network.py` remains a staging prerequisite, correctly refused when unavailable; the tests substitute a synthetic source only in their temporary runtime.

2. **RESOLVED — Deadline rate names.** `mac/k4s_logic.py:59–64`, `:206–225`, `end_pool.py:162–166`, and `mac/measure_k4s.py:174–184` share bare rate keys and `<key>_count`. `test_end_reference.py:500–546` connects synthetic host receipts, pooling, recheck, the Mac reader and gate inputs. This fixes the naming defect; the actual producer still encounters new findings 10–11 below.

3. **RESOLVED — Host statistic and direction.** `end_pool.py:120–129` uses the geometric mean of pooled per-state median / host per-state median on the documented 300-state K4S population. Tests at `test_end_reference.py:160–215` cross-check the frozen statistic and the slow-subset counterexample. The inclusive-bound interpretation is addressed separately below.

4. **PARTIAL — Reporting provenance.** There are now committed-blob/ancestry checks (`end_pool.py:234–286`), exact descriptor host-set comparison (`:405–408`), slot/priority/guard/warm-up/MHz validation (`:327–380`) and a structured recheck. The supervisor's actual launch/exit/census/MHz field shapes fit the parser and full-occupancy join. But counted membership is not reconciled with raw supervisor exits or the blind ledger, original END attempts can be omitted, and unsealed END files are consumed. See 12–14. The background-worker evidence contract also remains incompatible (10).

5. **PARTIAL — Frozen identity.** `end_reference.py:81–111` now performs bundle/runtime/measurement, native, corpus, kernel/scorer and SD1 checks before backend construction at `:206`; this fixes the original unchecked producer path. Pool admission compares only the five values produced by `end_pool.py:383–389`, ignoring the producer's K4S-manifest and measurement-source pins. The Mac compares those same five values. See 15; the actual background path also remains blocked by 10.

6. **RESOLVED — Complete per-state repeats and registered cells.** `end_pool.py:72–110` uses explicit exceptions, checks exactly three finite positive observations per timing series, exact state membership, unique `(state, repeat)` rows with repeat 0–2, real Boolean flags, and registered budget/charge fields. Negative tests and the optimized-interpreter test pass. Production `run_pool` obtains the 300-state inventory before invoking this validation.

7. **RESOLVED — Committed TIERS receipts.** `mac/k4s_logic.py:517–566` requires a full ancestor commit, exact committed file inventory and byte equality for every reused blob. `mac/measure_k4s.py:262–269` requires the commitment arguments. `K4S-MAC-PROCEDURE.md:151–184` commits the sealed copy before K4S admission while retaining the session lock. The negative tests cover uncommitted, re-sealed, side-branch and inventory mismatches. This verifies supplied receipts; the operator still must supply every valid TIERS session as documented.

8. **RESOLVED — Classification seal verification.** `mac/classify_k4s_failure.py:178–197` requires a complete classification seal containing `classification.json`, re-hashes it, binds the session seal/status and reads summaries/preconditions only from their verified inventory. Tests at `mac/test_measure_k4s.py:912–950` cover tampering and omitted files. The parallel END boundary has not received this protection (13).

9. **PARTIAL — Cleanup/status consistency.** The exact r1 scenario, completed Mac measurement followed by `Session.close()` failure, is fixed: `mac/measure_k4s.py:723–734` records cleanup failure and seals `failed`, and `mac/classify_k4s_failure.py:63–87` normally excludes it. The end-to-end test at `mac/test_measure_k4s.py:955–985` passes. Status/gate-failure handling is still incomplete: a failed post-summary exactness check can retain a passing summary in reduction (17). The END producer independently repeats the original cleanup/status error (16).

## New numbered findings

10. **BLOCKER — Frozen background workers still require the TIERS END schema and population.**
    - **Location:** `end_reference.py:182`, `:245–247`; frozen read-only dependency `e4v3/replay_load.py:174–180`, `fleet_profile.py:32–44`, `fleet_end.py:132–145`.
    - **Scenario:** The main producer accepts `clasher.k4s.end-evidence.v1` with 3000 primary/900 guard blocks. It then starts `FleetBackground`. Every spawned worker calls `pinned_profile()`, which calls the frozen `fleet_end.evidence()`. That reader requires `clasher.e4v3.end-evidence.v1` and, for counted reporting, 2400/600 blocks. It also requires a bundle-pinned `reference_load_profile.end_evidence`, absent from the new runbook's stated profile requirements. Supplying the new evidence raises `ValueError: Unsupported END evidence`; changing only the schema reaches the wrong-count rejection. Pointing workers at separate TIERS evidence does not validate the intended K4S reporting provenance.
    - **Evidence:** Source trace above; an in-memory invocation of the real frozen evidence reader with the new schema returned `Unsupported END evidence`. The fake-backend measurement test never starts `FleetBackground`.
    - **Fix:** Add a K4S-owned background adapter that validates the K4S evidence and uses the same frozen corpus work/load/slot conventions. Keep frozen TIERS files untouched. Exercise the actual worker startup/profile/evidence chain offline with injected model/native work; do not invent a second evidence document with incompatible counts to satisfy the dependency.

11. **BLOCKER — Genuine per-host bundle pins cannot satisfy whole-pins equality.**
    - **Location:** `end_reference.py:88`, `:187–189`; `end_pool.py:147–148`.
    - **Scenario:** Each producer records `bundle_manifest_sha256` in `pins`. Its bundle must have `reference_load_profile.host` equal to that host. Two different counted hosts therefore require different bundle-manifest bytes and hashes. Pooling compares the entire canonical `pins` object across hosts and rejects them as `Hosts measured different frozen pins`, even if every shared measurement/model/kernel pin agrees.
    - **Evidence:** In-memory pooling of otherwise valid 300-state raw records differing only in their producer-required per-host bundle SHA reproduces that rejection. `test_end_reference.py:403–436` fabricates only the five common pins; it does not reproduce `frozen_identity()`'s full pin record.
    - **Fix:** Separate common identity pins from host-specific bundle/profile receipts. Enforce equality and frozen values on the common pins, and retain/validate each host's bundle hash separately. Add a producer-shaped two-host integration fixture.

12. **MAJOR — Counted membership is asserted independently of supervisor exits and the blind ledger; health-only boundaries are missing.**
    - **Location:** `end_pool.py:209–231`, `:269–283`; frozen reference implementation `e4v3/fleet_end.py:44–123`.
    - **Scenario:** `counted_membership()` checks logical IDs and owner pairs but never verifies that counted descriptors appear verbatim in the supervisor's `completed` list, rejects counted lost blocks, or validates replacement/loss bindings. It receives no phase exits. The blind ledger is checked only for `sealed=True`; its events are otherwise ignored. Launch phase identity is not checked against the phase key. Unlike the frozen validator, there are no health-only field allow-lists for inventory rows/descriptors or ledger events. A committed inventory can consequently count nonexistent, failed or lost work and can include non-health payloads that this pre-release reader parses without rejecting.
    - **Evidence:** The passing test fixture itself has all 3900 counted blocks while every `supervisor_exit.completed` is empty (`test_end_reference.py:359–369`). An in-memory inventory/ledger with extra synthetic non-health marker fields is accepted with `blocks=3900`. No real outcome data was used in this probe. The supervisor writes actual completed/failed/unstarted descriptors at `supervise.py:119`, so this is missing validation, not missing producer evidence.
    - **Fix:** Port the frozen membership/loss/replacement reconciliation into a K4S-owned validator, extending only the descriptor field allow-list for registered K4S fields. Validate phase names and launch phase, exact completed membership, ledger evidence-SHA bindings and lost-block exclusions. Reject unknown/non-health fields before consuming their contents; keep game artifacts outside this evidence interface.

13. **MAJOR — END pooling reads files outside their receipt seal, and recheck omits them too.**
    - **Location:** `end_pool.py:305–316`, `:334–375`, `:439–450`.
    - **Scenario:** `verify_pinned()` verifies whatever the manifest lists, but no required END inventory is enforced. The pool then directly reads `end-identity.json`, `end-complete.json`, `end-raw.json`, slot/guard/warm-up/MHz files regardless of inclusion. The frozen attempt classifier also directly reads failure evidence. A seal may omit `end-raw.json`, after which its timing bytes can change while all listed hashes remain valid. Recheck enumerates only listed files, so the same omission escapes its before/after input inventory.
    - **Evidence:** With the synthetic host-b fixture represented in memory, an initially sealed inventory omitting `end-raw.json` accepted changed `k4s_wall=[0.00001, 0.00001, 0.00001]` through the real `validate_host()`. `input_files()` did not include that raw file. No disk bytes were changed.
    - **Fix:** Apply the new `read_sealed`/`read_sealed_json` pattern to END. Require each consumed receipt, sidecar, scope and admissible status; require/hash JSONL guard/census inputs too. Validate the failure-classifier inventory before calling frozen helpers that read files directly. Require recheck inputs to include every consumed file.

14. **MAJOR — “All original attempts classified” cannot be established from the caller's attempt list.**
    - **Location:** `end_pool.py:298–324`, `:424`; `test_end_reference.py:584–590`.
    - **Scenario:** A host descriptor lists only its successful attempt, omitting an earlier exactness failure. No committed attempt-root inventory or launch ledger is checked against that list. The pool accepts it and unconditionally emits `all_original_attempts_classified=True`. The author's test comment says omission is detected, but the test supplies the failed attempt or reverses ordering; it never tests omission.
    - **Evidence:** Read-only use of the synthetic pytest fixtures: `classify_attempts('b', [good], ...)` passes even though the earlier `exact` attempt exists; supplying `[exact, good]` raises `Unrepeatable END failure`. Strict chronology cannot detect a missing attempt.
    - **Fix:** Bind a complete original-END-attempt inventory/launch registry established independently of the pool descriptor, and require exact membership/order before classification. Test omission of an exactness failure and an excess technical attempt. Preserve every attempt even when the pool is rerun.

15. **MAJOR — Recorded END measurement-source pins are not compared with the frozen source used for pooling/Mac admission.**
    - **Location:** `end_reference.py:108–110`; `end_pool.py:341–342`, `:383–389`; `mac/measure_k4s.py:373–379`; `mac/k4s_logic.py:908–913`.
    - **Scenario:** Raw receipts record `k4s_manifest_sha256` and `measurement_files`, but expected-pins construction ignores both. All hosts can use the same stale/incompatible measurement code while retaining the current kernel/scorer/SD1/corpus/native values. Whole-pins equality proves only agreement between hosts. Re-running pooling does not establish that the raw measurements used the currently frozen producer/backend/logic.
    - **Evidence:** A synthetic sealed receipt represented in memory with `k4s_manifest_sha256=000…000` and a zero SHA for `measurement_files[end_reference.py]` passes real `validate_host()` with the correct five common pins.
    - **Fix:** Require the raw K4S-manifest SHA and full measurement-source inventory to equal the descriptor's frozen manifest and its relevant source pins; verify executing source locations where appropriate. Preserve per-host bundle identity separately (11). Include these common source bindings in Mac provenance admission or an authenticated committed pool contract.

16. **MAJOR — END backend cleanup failure can leave a complete, poolable seal.**
    - **Location:** `end_reference.py:285–309`; frozen `e4v3/fleet_validity.py:278–279`.
    - **Scenario:** The producer writes `end-complete.json` and sets `status='complete'` before cleanup. If `be.close()` then raises, the inner `finally` seals the unchanged complete status. It writes no failure/cleanup evidence. The frozen classifier returns `passes=True` immediately for a complete seal, so a nonzero-exit END attempt can be pooled as successful.
    - **Evidence:** Executing the exact AST-extracted cleanup block with a synthetic backend whose `close()` raises propagated the exception but called `store.seal('complete')`. This required no native work or disk mutation.
    - **Fix:** Give END the Mac runner's cleanup-failure handling: retain cleanup evidence, change status to failed, and mechanically classify the failure. Cleanup success must precede a poolable completion/status, and pool admission must reconcile all failure/completion receipts. Ensure failure paths stop the monitor promptly too.

17. **MAJOR — A post-summary exactness failure can still reduce to a passing Mac cell.**
    - **Location:** `mac/measure_k4s.py:593–599`; `mac/classify_k4s_failure.py:74–77`, `:190–197`, `:146–159`.
    - **Scenario:** `Session.run()` writes a passing summary, then re-validates the bundle. A changed specification produces `Exactness mismatch: frozen r3 specification` from frozen `validate_bundle()`/`assert_exact()`, and main seals failed. Classification returns a valid `gate-failure` with `gate0_failed=True`. `read_entry()` uses the existing passing summary unchanged; it creates a failing summary only when no summary exists. Reduction consults summary gate 0, ignoring the classification's gate-failure flag, and may select 0.9. Cleanup evidence/status is also bypassed by the classifier's early gate-failure return.
    - **Evidence:** In-memory reduction of a passing synthetic summary plus the real classifier result for that failed exactness trace returned `category='gate-failure', valid=True, c_M='0.9', gate0.passes=True`.
    - **Fix:** Make classification and summary consistent at admission: every valid gate-failure classification must force gate 0 false (or reject a contradictory summary). Reconcile sealed status and cleanup evidence explicitly while preserving the no-repeat rule for exactness failures. Test the actual write-summary → post-validation failure → classify → reduce sequence.

## Supervisor schema, inclusive ratios and frozen dependencies

The reporting supervisor's raw file shapes are compatible with the new main-process evidence path: `launch.json` has host/phase/slots (`supervise.py:55`); `supervisor-exit.json` has host/UTC and completed/failed/unstarted descriptors (`:119`); census has host/UTC/inflight (`:109–111`); MHz uses that same UTC, slot count and `{cpu, mhz}` entries (`:112–116`). Frozen `host_reporting()` joins them by UTC and selects `inflight == slots`, as required. Preserve the original JSONL rows when packaging them. The defects are the unadapted background-reader contract (10) and omitted provenance checks (12), rather than a census/MHz field-name mismatch.

**Inclusive ratio choice: acceptable against K4S r3's explicit text, but not identical to TIERS's floating comparison.** `in_host_ratio_window()` accepts the nearest doubles 0.95 and 1.05. Frozen `abs(r-1) <= .05` rejects those exact doubles because both differences round above .05. An in-memory probe confirmed `(K4S=True, TIERS=False)` at both endpoints. The author flags this accurately. K4S §4.5 explicitly says inclusive, so I do not request changing the K4S check or any frozen TIERS file. Keep this distinction explicit in the freeze/procedure and retain endpoint/nextafter tests.

**Frozen bytes remain untouched.** `git diff --exit-code HEAD` and the final `git diff --numstat HEAD` comparison were empty for the entire TIERS Mac package, `reports/explore/t1`, and TIERS r3 preregistration. The manifest-current test also passed, including SHA equality to committed blobs for every `reused_readonly` file. The shipped K4S manifest is correctly still a draft; do not freeze it while these findings remain open.

**Inherited TIERS blocker still exists.** Frozen `e4v3/measure_tiers.py:70` uses `math.isfinite` without importing `math`. Source inspection reconfirms the r1 finding. This is a TIERS-side dependency decision; this review does not authorize editing or re-hashing frozen TIERS artifacts.

## Validation

Required command, run from `reports/explore/k4s-confirm`:

```text
nice -n 19 /mpac/sdicks02/venvs/t1-verifier/bin/python -B -m pytest -q -p no:cacheprovider mac test_end_reference.py
123 passed in 6.95s
```

Additional in-memory/read-only synthetic probes confirmed findings 10–17 as described. The suite's “end-to-end” fixture creates host receipts itself, omits producer-added bundle/source pins, and does not start the frozen background worker. It therefore cannot establish real producer → pool → recheck → Mac compatibility. No actual corpus/model/native timings, reporting outcomes, or Mac execution were used or claimed.
