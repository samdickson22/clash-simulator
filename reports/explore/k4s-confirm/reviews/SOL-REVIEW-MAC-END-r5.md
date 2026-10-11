# SOL independent re-review: K4S Mac measurement and END, r5

**Verdict: REJECT.** Round 5 resolves findings **19, 20 and 21**: authority paths are fixed independently of completion/evidence packaging, enumeration uses path names instead of searching arbitrary blobs, and admissible authority documents use full-JSON parsing. A new **MAJOR finding 22** remains: a later round accepts an earlier pool's asserted `nonconforming` status without validating or classifying that earlier round's attempts. A retained earlier exactness failure can therefore be bypassed. Findings **4 and 14 remain PARTIAL** through 22. F-8 should remain unfrozen pending correction and independent re-review.

Reviewed worktree: `/mpac/sdicks02/repos/clasher-k4s-prep`, HEAD `962ecce2cf05223aada69746f2758bcf573c82f6`, 2026-10-11. I did not write the implementation. Reviewed the r1–r4 Mac/END findings, the “Round 5 (fixes for Sol r4)” mapping in `mac/PROGRESS-MAC.md`, the requested Mac/END implementation, procedures and tests, and relevant frozen dependency source. Governing contracts: PREREG-K4S r3 §1.4, §1.5, §4.4, §4.5, §5.4; CONFORMANCE-r2 N2/F-8; RECHECK-r3 R3/R5; TIERS r3 §6–§7 and frozen e4v3; K4S-SPEC §4/§8.

No network, SSH, Mac/fleet-host contact, model/native/corpus execution, or game outcome data was used. The implementation worktree was read only. The required test suite internally creates commits in temporary synthetic repositories; I issued no commit or push. My additional probe used existing synthetic health fixtures from that suite and in-memory transport/output substitutions, with no file edits or additional commits. This review file is my sole authored file. Existing worktree modifications belong to the implementation workers.

Locations below are relative to `reports/explore/k4s-confirm/` unless otherwise stated.

## Per-finding status

1. **RESOLVED — Shipped SD1 manifest compatibility.** `mac/k4s_logic.py:760` retains validation of the nested checkpoint/calibration schema, threshold, inference mode and complete eight-source inventory. Shipped-schema and negative source-pin tests pass. Actual inference-source staging remains a session prerequisite.

2. **RESOLVED — END/Mac rate names.** `end_pool.py:179`, `mac/measure_k4s.py:174` and `mac/k4s_logic.py:879` retain the shared bare rate and integer count names. Pool → independent recheck → Mac admission → gate-input integration passes across all five cells.

3. **RESOLVED — Frozen pooling statistic/direction.** `end_pool.py:135` retains the geometric mean of pooled per-state median / host per-state median. Frozen-helper, slow-subset and endpoint regressions pass. K4S's inclusive [0.95, 1.05] interpretation is explicitly documented and tested without editing TIERS.

4. **PARTIAL — Reporting provenance.** Committed completion/artifact bytes, complete counted membership, masks/priority, guard/warm-up and signed full-occupancy MHz checks remain at `end_evidence.py:164` and `end_pool.py:302`. Unique job authority and bounded reads now work. However, `all_original_attempts_classified=True` is still unsupported for earlier rounds: see 22.

5. **RESOLVED — Bundle/native/kernel and frozen measurement identity.** `end_reference.py:94` checks the bundle, native/corpus, frozen manifest, kernel/scorer, SD1 and runtime/executing END sources before backend construction. Producer-shaped multi-host identity and negative pin tests pass. Real staged bytes and execution remain END-time qualifications.

6. **RESOLVED — Per-state repeats, deadline rows and cells.** `end_pool.py:83` retains exact state membership, three finite positive non-Boolean observations, unique state/repeat rows, Boolean flags and registered budgets/charge scales. Negative and optimized-Python regressions pass.

7. **RESOLVED — Committed TIERS receipts.** `mac/k4s_logic.py:517` retains full-commit ancestry, exact committed inventory and byte equality; `mac/measure_k4s.py:262` requires the commitment arguments. The held-lock procedure commits the sealed copy before K4S admission. Negative commitment tests pass. Supplying every valid TIERS session remains an operator duty.

8. **RESOLVED — Classification seal contents.** `mac/classify_k4s_failure.py:278` still verifies the complete classification seal, inclusion/hash of `classification.json`, and source-session seal/status. Summary/precondition inputs remain sealed. Tampering and omitted-input regressions pass.

9. **RESOLVED — Cleanup/status consistency.** A clean measurement followed by cleanup failure remains technical; an established thrown or recorded gate-0 failure remains a valid no-repeat gate outcome through later cleanup/harness failure. Actual measurement-loop → classify → reduce tests pass for the recorded corpus and SD1 cases and the thrown-failure case.

10. **RESOLVED — Background worker rejects K4S schema/population.** `end_reference.py:360` uses the K4S adapter. `end_background.py:70` validates K4S evidence and bundle plan/evidence, masks and reporting joins while retaining the frozen corpus loop and worker lifecycle. Real spawned lifecycle/error tests with injected work pass. Real model-backed fleet operation remains unqualified offline.

11. **RESOLVED — Per-host bundle SHA blocks multi-host pooling.** `end_reference.py:94` separates common identity from per-host bundle/profile receipts; `end_pool.py:164` compares common pins and `:320` binds host-specific pins. Producer-shaped two-host integration and negative common/swapped-host pin tests pass.

12. **RESOLVED — Membership/exits/ledger reconciliation.** `end_evidence.py:76` retains verbatim completed membership, exit-SHA-bound losses, replacement matching, logical populations, counted owners and the registered descriptor extension. Phase/launch and negative membership/health-field tests pass.

13. **RESOLVED for the original defect — Attempt reads escape their seal/recheck inventory.** `end_evidence.SealedReceipt:234` retains exact directory inventory and re-hashing of consumed receipt bytes. `end_pool.py:242` reconciles completion/failure evidence before the frozen classifier reads it; `:459` checks the consumed local inputs in recheck. Unsealed raw/classifier input, incomplete seal and missing recheck-input tests pass. The new prior-round admission path in 22 does not apply these protections to earlier attempt receipts.

14. **PARTIAL — Caller's attempt list defines “all attempts.”** `end_pool.py:262` requires exact ordered receipt/claim matching and at most one repeat for the current round. Fixed authority, append-only claims and finalization prevent omission by root switching, completion aliasing or selecting an older snapshot. But `run_pool` selects only `authority['claims'][round_]` at `:398`; prior-round claims are retained as digests without their attempts being classified. See 22.

15. **RESOLVED — Raw manifest/source pins not compared.** `mac/k4s_logic.py:840` requires the complete frozen/common key set and exact manifest/source identity. Producer, pool and Mac admission retain that binding. Stale/incomplete identity tests pass; the adapter/evidence sources remain manifest-pinned.

16. **RESOLVED — END cleanup leaves a complete seal.** `end_reference.py:213` performs cleanup before completion, seals cleanup-only failures failed with typed crash evidence, preserves primary exactness and re-raises. `cleanup_steps:250` stops the monitor first and attempts all cleanup operations. Lifecycle, ordering, classifier and pool reconciliation tests pass.

17. **RESOLVED — Thrown post-summary exactness reduces as passing.** `mac/classify_k4s_failure.py:300` re-derives thrown evidence and forces gate 0 false, superseding measured inputs. The reducer refuses a contradictory gate-failure summary. Thrown-failure, cleanup and combined-session regressions pass.

18. **RESOLVED — Recorded gate-0 failure discarded after cleanup failure.** `gate0_evidence:50` derives failures from sealed K1, SD1, summary and committed TIERS inputs; contradictions are refused. `classify_records:141` preserves the gate failure and diagnostics without repeat permission. `read_entry:300` independently derives the evidence for every classification. Tests exercise actual fake-work measurement loops through classification/admission/reduction, alone and alongside a good session, plus partial traces, tolerated disagreements, contradictory summaries and TIERS-invalid precedence. No regression found.

19. **RESOLVED — Authority duplicated through copied completion/evidence packaging.** `end_evidence.py:285` fixes `END_DIR`, `END_JOB_PATH`, `REGISTRY_ROOT`, pool and receipt roots in source. `job_path:367` takes no descriptor/evidence argument. `end_job:410` reads the one fixed immutable declaration and binds completion/evidence/plan/counting/manifest. `declarations:380` refuses other job-like names under the study by path name. Producer and pool consume the same authority. `test_copied_completion_and_repackaged_evidence_cannot_open_a_second_authority:1237` retains an exactness failure, commits a byte-identical completion copy, successfully validates repackaged evidence, then refuses every second-authority route. The root-switch, deletion/re-addition and older-finalization regressions also pass. New finding 22 concerns later-round admission under this same unique job, not a remaining completion-alias bypass.

20. **RESOLVED — Stray-claim search crosses the health-only boundary.** `tree_names:333` uses `git ls-tree -r -z --name-only`; `declarations` and `namespace:391` inspect names, not arbitrary contents. The authority's `namespace_blob:339` confines blob reads to `END_DIR`; no `git grep` remains in this authority. The path-only mock and synthetic outside-namespace marker test at `test_end_reference.py:1303` and `:1333` pass. Names outside the END namespace cannot confer authority. This closes the whole-repository content-search defect; operator placement of health-only artifacts and collection of uncommitted host claims remain operational requirements.

21. **RESOLVED — Indented claims silently skipped.** `document:316` parses complete JSON bytes and refuses malformed/non-object input. END job, registry claims, receipt copies, finalizations and earlier pool documents use it; `end_pool.load_json:215` does too. Receipt-copy claims/digests and round/host/directory binding are checked at `receipt_copies:527`. Compact, indented and malformed cases at `test_end_reference.py:1389` and `:1408` pass: registered indented documents are accepted, hidden receipt copies are rejected, malformed documents are rejected, and second-root claim names are rejected independently of serialization.

## New finding 22 — MAJOR: prior rounds are not mechanically validated

**Locations:** `end_evidence.py:581` (especially `:594`–`:606`), `end_pool.py:398`–`:407`, `end_pool.py:423`. Related producer admission: `end_evidence.py:463`.

The fixed authority records all rounds' claim digests, but this does not classify all their attempts. For every earlier round, `job_registry` checks only:

- earlier finalization job/round/claim bindings;
- a caller-finalization-bound SHA of the earlier pool seal;
- that the seal says `scope=K4S-END-POOL` and `status=nonconforming`;
- one `end-reference.json` hash and four provenance bindings.

It does not verify a complete earlier pool inventory/sidecar, require the fleet-reference schema or timing/rate/pin fields, recompute an out-of-window ratio, inspect the earlier host classifications, or validate the earlier attempts from their seals. A reference containing **only `provenance`**, under a seal listing **only `end-reference.json`**, is accepted as evidence that the earlier round failed exclusively on ratios.

The later `run_pool` then validates/classifies **only the latest round** and unconditionally asserts every `REPORTING_EVIDENCE_KEYS` item true. Keeping an earlier claim in the finalized digest list therefore does not keep its exactness/other unrepeatable verdict operative. Receipt-copy checking proves the retained claim is registered, but reads neither that attempt's seal nor its failure. `producer_registry` also permits the next round from existence of a previous finalization alone; it does not require a validated nonconforming pool before launching new work.

**Consequence:** after an unrepeatable round-00 failure, an internally hash-consistent, committed earlier “nonconforming pool” shell with the required provenance fields can permit a good round 01 to produce a conforming reference, while retaining the original failure/claim. No END-JOB rewrite, claim omission, alternate root, copied completion, or first-line JSON bypass is necessary. This contradicts the runbook's rule that an unrepeatable failure can never be followed by a re-run round and fails the job-wide “all original attempts classified” claim. The fresh-interpreter recheck uses the same latest-round-only path, so its re-execution does not independently close this omission.

**Read-only evidence:** I ran actual `end_pool.run_pool` against the required suite's existing two-round synthetic health fixture at `/tmp/pytest-of-sdicks02/pytest-125/test_rerun_rounds_record_and_r0`. Only the descriptor read, selected Git blob/tree responses and output store were substituted in memory. All current-round seal/classification, membership, pins, slots, guard, warm-up, MHz and timing checks executed unchanged. Actual Git history/ancestry/claim/finalization-path checks ran read-only against the fixture. The transport modeled these committed health artifacts:

1. Round 00's earlier reference replaced by `{provenance: {end_job: {sha256: JOB_SHA}, round: 0, finalization: {sha256: FINAL_00_SHA}, claims: FINAL_00.claims}}` — no schema, hosts, measurements, ratios, pins or attempt classifications.
2. Its pool seal replaced by `{scope: 'K4S-END-POOL', status: 'nonconforming', files: {'end-reference.json': SHA(reference)}}` — no other pool artifacts or verified inventory.
3. Round 01's finalization/descriptor adjusted only to bind those modeled bytes' SHAs.
4. A failed round-00 receipt under `RECEIPTS_ROOT/round-00/b/<registered receipt directory>/`, containing the exact registered claim copy, identity and `failure.json` with `Exactness mismatch: retained original round-00 attempt`, and an internally hash-consistent failed seal/sidecar. These are modeled synthetic committed health documents, not a claim that a new on-disk producer attempt was executed.

The authority read the original claim copy but never opened its failed seal or failure. Output:

```json
{
  "pool_conforms": true,
  "all_original_attempts_classified": true,
  "prior_reference_only_has_provenance": ["provenance"],
  "prior_seal_only_lists": ["end-reference.json"],
  "retained_prior_failed_receipt_seal_read": false,
  "retained_prior_exactness_failure_read": false,
  "retained_prior_claim_copy_checked": true
}
```

This is a full current-pool validator probe with modeled Git artifacts and memory-only output, not a real END run or an executed forged recheck. Source inspection establishes that recheck repeats the same omission. The existing `test_rerun_rounds_record_and_reconcile_the_earlier_nonconforming_pool:1467` tests a genuine nonconforming predecessor, missing prior entries and wrong seal SHA, but not this false predecessor certificate.

**Required correction:** authenticate and mechanically validate every earlier round's complete pool and original attempt receipts under the same frozen identity. Re-derive the earlier ratio nonconformance and classifications; refuse absent/malformed prior pool evidence, unrepeatable failures, unauthorized repeats and earlier conforming pools. Preserve the unique fixed namespace and bounded health-only reads. Do not fix this solely by adding required reference fields or trusting stored classification Booleans. Producer admission should require the validated nonconforming predecessor before running the next round. A historical-round audit must work without weakening the current latest-finalization rule.

Add regressions retaining a sealed exactness failure and its claim, attempting a next round with a provenance-only or otherwise falsely nonconforming predecessor, and asserting refusal by producer/pool/recheck. Also cover missing prior attempt receipts, a conforming predecessor relabeled nonconforming, and invalid excess prior repeats. Retain the legitimate ratio-failure → re-run success case.

## Frozen bytes and dependency status

Ran and repeated during the review:

```text
git diff --exit-code HEAD -- reports/strategy_council_20260928/live-loop/v4/mac-e4-package reports/explore/t1 ':(glob)**/PREREG*'
git diff --numstat HEAD -- reports/strategy_council_20260928/live-loop/v4/mac-e4-package reports/explore/t1 ':(glob)**/PREREG*'
```

**Exit 0 / no output.** The entire TIERS Mac package, including frozen e4v3, T1 tree and PREREG files are untouched relative to HEAD. The manifest-current regression passes, including reused-readonly source pins against committed bytes.

- PREREG-K4S r3 SHA: `9650972d362299d87f8b1084d450f9a2dbbad516a494e97da6ba33d60fb68b3a`.
- TIERS r3 SHA: `ef0db97ad509753ccf63c7376f800d6db7f0b82ee07f102476eafb939e2a4c77`.
- K4S Mac manifest SHA: `570f6a6def2d13d8f79a28bb4f3cd799011cc58003c6c3df72cb5d62d969620c`; still correctly `frozen=false`.
- The current prep-owned `DELTA-MANIFEST.json` includes and correctly pins all four END source files. The round-5 progress note saying those pins remain stale is outdated in this worktree.

The inherited TIERS issue remains: frozen `e4v3/measure_tiers.py:70` calls `math.isfinite` without importing `math`. It requires an authorized TIERS-side decision before that applicable real Mac path runs. This review neither edits nor authorizes changing frozen bytes.

## Validation and qualifications reserved for END / the Mac session

Required command, from `reports/explore/k4s-confirm`:

```text
nice -n 19 /mpac/sdicks02/venvs/t1-verifier/bin/python -B -m pytest -q -p no:cacheprovider mac test_end_reference.py test_end_background.py
```

**194 passed in 87.84s.** This verifies offline logic, producer-shaped synthetic receipts, temporary committed health evidence, and spawned workers with fake work. The additional read-only in-memory probe above exposes a case not covered by that suite.

Only END can qualify the actual SHA-verified, authorized T1 corpus copy, SD1/runtime/model/native bundles and executing frozen sources; real every-host background occupancy, warm-up, guard and 1 Hz signed MHz joins; every counted host and every original attempt; complete collection/commitment of each host's uncommitted claims; correct finalizations and legitimate prior-round evidence; actual timing/deadline populations and conforming pooled reference with independent recheck. Offline checks cannot discover claims never collected from a host or validate a host's actual execution from synthetic fixtures.

Only the authorized Mac session can qualify Darwin/arm64 execution, the same-Mac TIERS native/scorer binding and committed final TIERS verdicts, completion of TIERS §7 before K4S, lock/session ordering, real SD1 agreement/backend choice, replay perception load, thermal behavior, GC/poll timing, loaded speed/p10/p99 and deadline gates. All supplied valid sessions must enter the prescribed minimum/worst-input reduction, and post-release admission needs the independent classification review. Replay-only evidence remains PROVISIONAL until formal E4/T9 re-measures every required input. This review grants no freeze, release or live-play authorization.
