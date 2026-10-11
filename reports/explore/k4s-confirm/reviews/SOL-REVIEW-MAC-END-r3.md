# SOL independent re-review: K4S Mac measurement and END, r3

**Verdict: REJECT.** Most round-2 fixes satisfy their offline contracts, including the K4S background adapter, producer-shaped multi-host pins, membership reconciliation, sealed END reads, measurement-source identity and END cleanup ordering. Two integrity gaps remain: a recorded Mac gate-0 failure can be discarded following cleanup failure, and the caller can select a different attempt registry for the same END evidence, hiding an unrepeatable original attempt. F-8 should remain unfrozen pending these fixes and re-review.

Reviewed worktree: `/mpac/sdicks02/repos/clasher-k4s-prep`, HEAD `962ecce2cf05223aada69746f2758bcf573c82f6`, 2026-10-11. I did not write the implementation. Read the r1/r2 reviews and `mac/PROGRESS-MAC.md`'s Round 3 mapping, the requested Mac/END implementation, tests and procedures, and the relevant frozen dependencies. Governing contracts: PREREG-K4S r3 §1.4, §1.5, §4.4, §4.5, §5.4; CONFORMANCE-r2 N2/F-8; RECHECK-r3 R3/R5; TIERS r3 §6–§7; frozen e4v3; K4S-SPEC §4/§8.

No network, SSH, Mac/fleet-host contact, real model/native/corpus execution, or game outcome data was used. The worktree was read only. Additional probes ran in memory or read synthetic temporary receipts created by the specified tests. I issued no commit or push; the specified test suite internally creates commits in temporary synthetic repositories. This file is my sole authored artifact. Other workers were changing files outside this review's scope; those changes are not attributed to this review.

Locations below are relative to `reports/explore/k4s-confirm/` unless stated otherwise.

## Per-finding disposition

1. **RESOLVED — Shipped SD1 manifest compatibility.** `mac/k4s_logic.py:760–788` validates the actual nested SD1 schema, checkpoint/calibration, threshold/mode and complete eight-source inventory. `mac/test_measure_k4s.py:450–488` exercises the shipped schema and source pin mutations. The real network source must still be staged; tests correctly substitute a synthetic source in a temporary runtime.

2. **RESOLVED — END/Mac rate names.** `end_pool.py:176–180` emits the shared `deadline_cell_record` naming; `mac/k4s_logic.py:879–926` and `mac/measure_k4s.py:174–184` consume the same bare rates and integer count keys. `test_end_reference.py:748–813` covers pool → independent recheck → Mac admission → gate inputs across all five cells.

3. **RESOLVED — Frozen pooling statistic/direction.** `end_pool.py:132–146` computes the geometric mean of pooled per-state median / host per-state median on the documented K4S population. The frozen-statistic comparison and slow-subset tests at `test_end_reference.py:187–232` pass. Inclusive bounds remain an acceptable, explicitly disclosed application of K4S r3; see below.

4. **PARTIAL — Reporting provenance.** Committed completion/artifact bytes, complete counted membership, slot/priority/guard/warm-up evidence and signed full-occupancy MHz comparisons are now checked (`end_evidence.py:61–207`, `end_pool.py:296–356`). The producer and background adapter share the K4S evidence contract. However, `all_original_attempts_classified=True` is still only established for the caller-selected registry, not for all original attempts of this END job. Finding 19 keeps this item open.

5. **RESOLVED — Bundle/native/kernel and frozen measurement identity.** `end_reference.py:91–150` validates the fleet-reference bundle and qualified native/corpus, frozen K4S manifest, kernel/scorer, SD1 and complete END source inventory before backend construction at `:315`. It checks both runtime copies and executing END source files. `end_pool.py:308–315` and `mac/k4s_logic.py:840–873` compare the full frozen identity; Mac staging supplies its own manifest-derived identity at `mac/measure_k4s.py:373–383`. Real artifacts/execution remain END-time qualifications, not missing offline pin checks.

6. **RESOLVED — Per-state repeats, deadline rows and cells.** `end_pool.py:80–121` requires exact state membership, three finite positive non-Boolean observations per timing series, unique state/repeat rows with repeats 0–2, Boolean flags and registered budgets/charge scales. Explicit exceptions survive optimized Python. Negative/optimized tests at `test_end_reference.py:132–184` pass.

7. **RESOLVED — Committed TIERS receipts.** `mac/k4s_logic.py:517–601` checks a full ancestor commit, exact committed inventory and byte equality; `mac/measure_k4s.py:262–269` requires commitment arguments. The procedure commits the sealed copy under the held session lock before K4S admission. Uncommitted, divergent, re-sealed and inventory-mismatched receipt tests pass. This does not independently discover omitted TIERS sessions; the procedure still requires all valid inputs.

8. **RESOLVED — Classification seal contents.** `mac/classify_k4s_failure.py:195–207` verifies the complete classification seal, inclusion/hash of `classification.json`, source session seal/status, and inclusion of consumed summaries/preconditions. `mac/test_measure_k4s.py:912–950` covers the original tampering and omitted-summary cases. The new finding 18 concerns classification semantics, not the original classification-byte substitution defect.

9. **PARTIAL — Cleanup/status consistency.** The original completed-session → cleanup-exception scenario now seals failed and is excluded as technical (`mac/measure_k4s.py:726–738`; `mac/classify_k4s_failure.py:63–97`). Its test at `mac/test_measure_k4s.py:955–985` passes. END has the corresponding lifecycle protection (16), and thrown post-summary exactness failures are preserved (17). But normal gate-0 failures recorded in the summary/diagnostic receipts are not preserved when cleanup fails. Finding 18 keeps this broader item open.

10. **RESOLVED — Background worker rejects K4S schema/population.** `end_reference.py:355` uses the K4S-owned adapter. `end_background.py:70–87,106–126` validates K4S committed evidence and bundle plan/evidence pins, uses the frozen slot and reporting joins, and runs the frozen corpus work loop. The subclass at `:132–157` retains the frozen lifecycle. `test_end_background.py:94–181` exercises the actual worker chain with injected work/identity, negative admission cases, a real spawned successful worker and a spawned error. No TIERS file was changed. This resolves the schema/design incompatibility; real model-backed fleet operation is not claimed.

11. **RESOLVED — Per-host bundle SHA blocks multi-host pooling.** `end_reference.py:100–114` separates shared pins from each host's bundle/profile receipt. `end_pool.py:160–162` compares shared identity only and `:312–315` requires a correctly named per-host receipt. `test_end_reference.py:425–440,725–813` derives pins through real `frozen_identity()` for two different host-naming bundles and passes the pool/recheck/Mac chain. Differing shared identity and swapped host receipts are refused.

12. **RESOLVED — Membership/exits/ledger and health-only boundaries.** `end_evidence.py:61–138` ports the frozen completed/lost/replacement reconciliation, with only the registered K4S descriptor-field extension. Counted descriptors must appear verbatim in completed exits; losses bind to exit SHA; counted replacements match their bank descriptors except transport fields; failed blocks require losses; logical populations/owners must be complete. Phase and launch identity are checked at `:175–200`. Replacement and negative tests at `test_end_reference.py:561–625` pass.

13. **RESOLVED — END reads escape their seal/recheck inventory.** `end_evidence.py:217–262` requires the exact on-disk sealed inventory plus seal/sidecar, verifies every file and re-hashes bytes before parsing. `end_pool.py:240–257` requires all successful receipts and reconciles status. This also protects files directly opened by the frozen classifier. `:444–480` verifies the pool seal and requires every recorded consumed file in the unchanged recheck inventory. The unsealed raw, incomplete seal, planted classifier input and missing recheck-input tests at `test_end_reference.py:917–965` pass.

14. **PARTIAL — Caller's attempt list defines “all attempts.”** The new committed registry and exact ordered claim matching at `end_pool.py:260–293` detect omitted/reordered attempts within that registry, and enforce at most one repeat. Tests at `test_end_reference.py:879–912` demonstrate that improvement. However, `--attempt-registry` and the descriptor's registry path/commit remain independent caller choices, without a preregistered job-wide authority or finality check. Selecting another root or an earlier snapshot can still hide work. See finding 19.

15. **RESOLVED — Raw manifest/source pins not compared.** `mac/k4s_logic.py:840–873` requires the complete frozen/common key sets and exact manifest/source identity. Producer construction/checks at `end_reference.py:117–150,395`, pool expected-pins/admission at `end_pool.py:308–311,375–391`, and Mac admission at `mac/measure_k4s.py:373–383` use that identity. `test_end_reference.py:398–404,748–837` rejects stale source/manifest pins and incomplete Mac expectations. New adapter/evidence sources are in `build_manifest.END_FILES`.

16. **RESOLVED — END cleanup leaves a complete seal.** `end_reference.py:210–244` performs body and cleanup before writing completion; cleanup-only failure writes both cleanup evidence and typed crash failure, seals failed and re-raises. Primary exactness remains primary. `cleanup_steps` at `:247–274` stops/joins the monitor and closes pipes/backend even after an earlier cleanup error. Pool reconciliation refuses complete seals carrying failure evidence. Lifecycle/order/classifier/pooling tests at `test_end_reference.py:968–1082` pass.

17. **RESOLVED — Thrown post-summary exactness failure reduces as passing.** For the specific r2 scenario, `mac/classify_k4s_failure.py:74–85` preserves exactness as a valid no-repeat gate failure; `:223–235` re-reads its sealed trace and supersedes the passing summary with gate 0 false; `:155–175` prevents contradictory reduction. Tests at `mac/test_measure_k4s.py:1024–1091` exercise main → classify → reduce, including cleanup failure and combination with a good session. The distinct recorded-gate-failure case below remains open.

## New findings

18. **MAJOR — A normal recorded gate-0 failure is discarded if cleanup subsequently fails.**

    **Location:** `mac/classify_k4s_failure.py:113–135` (classification omits summary/corpus/agreement verdicts), `:57–85` (gate-failure detection depends on the exception text), `:209–210` (invalid classifications are returned without preserving a gate failure). Producer evidence: `mac/measure_k4s.py:52–65,536–547,578–603,726–738`.

    **Scenario:** K1 detects a corpus exactness mismatch, catches it and writes a failing diagnostic; alternatively SD1 agreement fails normally. `Session.run()` records `gate0.passes=False` and the failed part in its summary, completes, and then backend cleanup raises. Main correctly seals failed with `cleanup-failure.json`. `classify()` never inspects the failing summary or the K1 verdict. With no exactness exception in `failure.json`, it returns `technical-failure`, `valid=False`, `technical_repeat_candidate=True`. The session's gate-0 failure is excluded, and a permitted repeat can produce an eligible cell. This conflicts with r3 §5.4's gate-0 kill and the author's explicit exactness-before-cleanup/no-repeat treatment in finding 17.

    **Evidence:** An in-memory run through actual `measure_k4s.main` using a synthetic session and memory receipt store wrote a failed corpus trace, failing summary and completion, then raised a cleanup error. Actual `classify()` with the synthetic receipt reads returned the technical classification above. Actual `reduce_sessions()` combining that entry with a passing synthetic session returned `valid_sessions=1`, `excluded_sessions=1`, `c_M='0.9'`, `k4s_killed_on_mac=False`. Filesystem/pin reads were mocked for this in-memory probe; no on-disk receipt was altered. The checked source establishes the same producer path for a real caught K1 mismatch. The existing cleanup test supplies a passing summary, while the new exactness tests supply an exception trace; neither covers this combination.

    **Fix:** Derive exactness/agreement gate failures from verified sealed verdicts and summary parts as well as thrown exceptions. Preserve an established gate-0 failure as a no-repeat gate outcome through subsequent cleanup/harness failures, while retaining the technical diagnostics. Admission must accept authenticated recorded gate failures rather than requiring only `failure.json` exception keywords. Add main → classify → reduce regressions for caught corpus mismatch and ordinary agreement failure followed by cleanup failure, alone and alongside a good session. Preserve the separately intended TIERS-invalid-session rule.

19. **MAJOR — The attempt registry can be replaced or selected from an incomplete historical snapshot.**

    **Location:** `end_reference.py:300,420`; `end_evidence.py:270–285,288–315`; `end_pool.py:388–390,404–408`.

    **Scenario:** Run a failed END attempt against registry A. Run another attempt for the same host, frozen identity and committed END evidence against a fresh registry B; its sequence restarts at 00. Collect/commit B and name only B in the pool descriptor. Claims contain host/sequence/receipt name/time/pid/nonce, but no binding to a previously established canonical study/job registry. Pooling checks only the selected registry. Registry A's exactness failure or excess technical attempts are invisible. Even without changing roots, `committed_registry()` accepts any ancestor snapshot and never establishes that it contains the finalized current claim set. The new registry therefore moves the caller-controlled omission boundary instead of closing it.

    **Evidence:** Read-only use of the required suite's synthetic receipts in `test_pool_refuses_omitted_host_bad_mhz_slots_and_unrepeatable_attempts` found both `registries/repeat` and `registries/exact` committed in one temporary repository, with the same `end_evidence` path/SHA. Calling the actual committed-registry reader, `validate_host()` for both selected hosts and pure `pool()` on the `repeat` inputs passed (`pool_conforms=True`). The omitted `exact` receipt, verified through `SealedReceipt` and the real frozen classifier, had `exactness_failure=True` and `technical_repeat_candidate=False`. No fixture bytes were modified. This directly exercises the unrestricted registry selection; the existing omission test always keeps the same registry reference.

    **Fix:** Establish a canonical job/registry authority independently of the pool descriptor before the first attempt, bind it to reporting completion/END job identity, and enforce it in the producer and pool. Require a finalized complete append-only claim inventory, with an independent binding proving that alternate roots or older snapshots do not omit original attempts. Record and reconcile earlier pool rounds if rerunning under §4.5. Add negative tests for switching roots after an exactness failure, hiding excess attempts in a second registry, and choosing an older snapshot after additional claims. Keep all validation health-only.

## Frozen bytes and existing dependency

Run from the worktree root:

```text
git diff --exit-code HEAD -- reports/strategy_council_20260928/live-loop/v4/mac-e4-package reports/explore/t1 ':(glob)**/PREREG*'
```

**Exit 0, no output.** The matching `git diff --numstat HEAD` was empty. Thus the complete TIERS Mac package (including e4v3), T1 tree and PREREG files are untouched relative to HEAD. The requested implementation scope also had no worktree diff relative to HEAD at review time. The passing manifest-current test additionally compares every `reused_readonly` SHA with its committed blob.

PREREG-K4S r3 SHA: `9650972d362299d87f8b1084d450f9a2dbbad516a494e97da6ba33d60fb68b3a`. TIERS r3 SHA: `ef0db97ad509753ccf63c7376f800d6db7f0b82ee07f102476eafb939e2a4c77`. The Mac manifest is still correctly `frozen=false` (SHA `4c25d4543ff07b285662dbbc6c056ed144ca501c948aebc9ab6b990ae075309c`).

The inherited TIERS dependency remains: frozen `e4v3/measure_tiers.py:70` uses `math.isfinite` without importing `math`. Source inspection reconfirms it. Resolving that is a separate authorized TIERS decision; this review does not authorize changing frozen bytes. The Progress note that DELTA-MANIFEST lacks the new END files is stale at this HEAD: its file inventory now includes `end_background.py` and `end_evidence.py`. This observation is not an audit of the entire delta package.

The inclusive host-ratio distinction remains acceptable and tested: K4S uses `0.95 <= r <= 1.05`; frozen TIERS's floating `abs(r-1) <= .05` rejects those exact endpoint doubles. K4S r3 explicitly specifies an inclusive window. Do not change the frozen TIERS rule.

## Validation and what can only be qualified at END

Required command, from `reports/explore/k4s-confirm`:

```text
nice -n 19 /mpac/sdicks02/venvs/t1-verifier/bin/python -B -m pytest -q -p no:cacheprovider mac test_end_reference.py test_end_background.py
175 passed in 46.29s
```

The passing suite establishes offline logic, negative admission checks, synthetic producer-shaped receipts, the background adapter's spawned lifecycle with fake work, and deterministic pool/recheck/Mac-reader compatibility. The two additional probes above expose gaps outside that coverage. No real fleet END run was attempted or required for this review.

Only at END, after committed reporting completion, can the coordinator qualify the real per-host bundles and artifact staging, committed raw completion/exit/ledger/counting evidence, physical CPU topology/affinity and priority, actual guard admission and live census/checkpoint behavior, simultaneous model-backed background loops and slot-0 measurement, real 300-second warm-up and 1 Hz/full-occupancy MHz comparison, native/Torch K4-versus-K4S and cross-host exactness, charged deadline/pure-poll timings, and the complete production driver → seal → pool → independent recheck workflow. None is established by injected model/native work. Success requires every counted host and retained original attempt, or the registered coordinator ratio-unavailable path. Mac hardware execution and formal E4/T9 remain separate qualifications.

Absence of that future run is not the reason for rejection. The two reproducible offline integrity defects are.
