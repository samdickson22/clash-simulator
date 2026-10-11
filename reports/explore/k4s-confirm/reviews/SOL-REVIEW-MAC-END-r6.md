# SOL independent code re-review: K4S Mac measurement and END, round 6

**Verdict: APPROVE.** Finding **22 is RESOLVED**, including the round-5 forged-certificate scenario. Findings **4 and 14 are now RESOLVED** at the offline implementation boundary: every finalized prior round is mechanically re-validated and recomputed, and an earlier unrepeatable failure prevents later producer admission and pooling. No new blocking or major issue was found; no regression of the earlier resolutions was found. This approves the reviewed code, not a production END reference, Mac qualification, freeze, outcome release or live deployment.

Reviewed worktree: `/mpac/sdicks02/repos/clasher-k4s-prep`, HEAD `962ecce2cf05223aada69746f2758bcf573c82f6`, 2026-10-11. I did not implement this code. Read the r1–r5 Mac/END reviews, the “Round 6 (fix for Sol r5)” mapping in `mac/PROGRESS-MAC.md`, the requested Mac/END implementation, procedures and tests, and relevant frozen dependency source. Governing contracts: PREREG-K4S r3 §1.4, §1.5, §4.4, §4.5, §5.4; CONFORMANCE-r2 N2/F-8; RECHECK-r3 R3/R5; TIERS r3 §6–§7 and frozen e4v3; K4S-SPEC §4/§8.

No network, SSH, Mac/fleet-host contact, real model/native/corpus execution, or game outcome data was used. The implementation worktree was read only. The specified tests internally create synthetic receipts and commits in temporary fixture repositories; I issued no commit or push. Additional probes read those synthetic fixtures and substituted the temporary-copy transport in memory, creating no files. This review is my sole authored file. Pre-existing worktree edits belong to the implementation workers.

Locations below are relative to `reports/explore/k4s-confirm/`.

## Finding 22: prior-round certificates and failures

**RESOLVED.** The fix validates earlier rounds using the same substantive path as the current round, rather than trusting a stored status or classification:

- `end_pool.py:392` builds a shared context from the frozen manifest/helper pins, corpus inventory, committed reporting evidence and expected identity.
- `end_evidence.py:570` checks every round's finalization through one function: fixed path, immutable committed bytes, job/round binding, complete claims at HEAD and at the finalization commit, launch ordering and fixed prior-pool seal bindings. `rounds_authority` and `round_finals` authenticate the inventory without treating it as proof of measurement validity.
- `end_evidence.py:646` obtains the committed prior pool and every original receipt at the fixed namespace paths. Each file must be append-only; each host's receipt directories must exactly equal its claimed directories. Pool files must precede later committed claims.
- `end_pool.py:471` verifies the complete prior pool seal, sidecar and exact inventory, including the sealed descriptor. The descriptor must bind the same job, historical round/finalization, common frozen inputs and exactly the committed receipts. Historical local paths are replaced with the verified committed receipt copies.
- It calls **the same `pool_round` at `end_pool.py:414`** used for the current round. This runs claim matching, seal/status reconciliation, the frozen attempt classifier, repeat limits, passing-host pins, slot/priority/guard/warm-up/MHz checks, complete timing/deadline validation, cross-host exactness, pooling and provenance construction. A retained exactness failure, excess repeat, missing passing attempt or other refusal raises before a later pool can be emitted.
- The recomputed predecessor must be `pool_conforms=False`. At that point the remaining failure is a host ratio outside the inclusive window. The reference, descriptor and ratio record must match the committed bytes; seal status/inventory must match; consumed-input records must match by digest, permitting relocation of local paths. Prior rounds are validated in order, so historical provenance includes the same already-validated predecessors.
- `end_evidence.py:468` requires context and calls `end_pool.predecessors` before a later producer claim. `end_reference.py:305` supplies that context before creating the claim or constructing the measurement backend. The pool independently invokes `validated_priors` at `end_pool.py:563`; forcing a claim around producer admission does not bypass pooling.
- `end_pool.py:589` rechecks in a fresh isolated interpreter, which repeats prior-round validation. In-memory bypasses in the original pooler do not carry into that process.

The specified regressions exercise the exact r5 certificate: a retained sealed exactness failure, a reference containing only provenance, and a seal listing only that reference. Producer and pool refuse it; a pooler monkeypatched to trust it can emit a false conforming round-01 artifact, but the fresh-interpreter recheck refuses it and emits no success receipt. Separate regressions retain exactness or excess repeats under a complete, internally hash-consistent false pool inventory. They fail during classification/repeat validation, not merely for missing reference fields. Missing prior receipts, absent pools, missing context, genuine conforming predecessors and conforming pools relabeled nonconforming are refused. The genuine ratio-only round-00 failure → valid round-01 → successful independent recheck path passes.

I additionally called the actual `validate_prior_round` against retained synthetic fixture repositories. Only scratch-directory creation and committed-directory copying were replaced: the probe read the committed directories in place, verified their bytes against namespace-bound Git blobs and their immutable histories, and checked pool-before-later-claim ancestry. Actual job/finalization authority, seals, descriptor binding and validation ran unchanged; output writing was forbidden. Results:

```text
provenance-only certificate:
  Earlier END pool round 00 is not a complete sealed nonconforming pool
complete false pool retaining exactness failure:
  Unrepeatable END failure (exactness never earns a repeat)
complete false pool retaining three attempts:
  Each host may have at most one repeat (registry lists 3): b
```

These are offline validator probes on synthetic health evidence, not executed fleet END runs.

## Per-finding status

1. **RESOLVED — SD1 schema compatibility.** Nested checkpoint/calibration, artifact identity, threshold/inference mode and the exact eight-source inventory remain validated by `mac/k4s_logic.py:760`. Shipped-schema and source-pin regressions pass; real source staging remains a session prerequisite.

2. **RESOLVED — END/Mac rate names.** `end_pool.py:185` emits the shared bare rate/integer count convention. Pool → recheck → Mac admission → gate-input integration passes across all five registered cells.

3. **RESOLVED — Pool statistic and direction.** `end_pool.py:140` retains the frozen geometric pooled-median/host-median statistic. Frozen-helper, slow-subset and inclusive endpoint regressions pass. K4S's documented inclusive window does not change TIERS bytes.

4. **RESOLVED — Reporting provenance.** `end_evidence.py:169` authenticates committed completion, reporting artifacts and counted membership. `end_pool.py:307` validates reporting slots/priority, guards, warm-up and signed full-occupancy MHz comparisons. Findings 19–21 retain their unique-authority and bounded-read fixes. Finding 22 now establishes classification of every claimed attempt in every earlier round before the job-wide evidence flag can be emitted. Collection completeness on real hosts remains an END-time qualification.

5. **RESOLVED — Frozen bundle/native/kernel identity.** `end_reference.py:96` validates bundle/runtime, native/corpus, manifest, kernel/scorer, SD1 and executing END sources before backend construction. Producer-shaped multi-host and negative identity regressions pass.

6. **RESOLVED — Complete repeats and registered cells.** `end_pool.py:88` requires exact corpus membership, three finite positive non-Boolean observations per timing series, unique state/repeat rows, Boolean rate flags and registered budgets/charges. Negative and optimized-interpreter regressions pass.

7. **RESOLVED — Committed TIERS receipts.** `mac/k4s_logic.py:517` retains full-commit ancestry, exact committed inventory and blob equality. Mac admission requires commitment arguments; the held-lock procedure commits the sealed copy before K4S admission. Negative commitment tests pass.

8. **RESOLVED — Classification seal contents.** `mac/classify_k4s_failure.py:278` authenticates classification contents, inclusion/hash of the classification file and its session seal/status binding. Consumed summary/precondition inputs remain sealed. Tampering and omitted-input regressions pass.

9. **RESOLVED — Cleanup/status consistency.** Cleanup-only failure remains technical. Established thrown or recorded gate-0 failure remains a valid no-repeat gate outcome through later cleanup/harness failure. Measurement → classify → reduce regressions pass.

10. **RESOLVED — Background schema/population incompatibility.** The K4S-owned adapter validates K4S evidence and uses the frozen worker loop/lifecycle. Inline and actually spawned workers with injected work pass; real model-backed operation remains unqualified offline.

11. **RESOLVED — Per-host bundle SHA blocks pooling.** Common identity and host-specific bundle/profile receipts remain separate, with each host receipt bound to its host. Two-host producer-shaped integration and negative swapped/shared-pin tests pass.

12. **RESOLVED — Membership/exits/ledger reconciliation.** The frozen health-only reconciliation port requires verbatim completed membership, exit-bound losses, valid replacements and complete logical population/owner coverage. Only registered K4S descriptor extensions are added. Negative membership/phase/health-field tests pass.

13. **RESOLVED — Attempt reads escape seals/recheck inventory.** `end_evidence.SealedReceipt` requires exact inventory and hashes every consumed file before the frozen classifier reads it. Recheck covers recorded current local inputs. Prior-round reads now receive that same seal/attempt protection and committed immutable-byte validation. Negative seal and inventory tests pass.

14. **RESOLVED — Caller defines all attempts.** Fixed job/registry authority, HEAD/finalization equality, append-only claims and exact ordered attempt matching remain enforced. With finding 22 fixed, prior-round digests are accompanied by actual reclassification of every original receipt, including technical and unrepeatable failures. The caller cannot offer only the latest round's successful evidence to erase an earlier failure.

15. **RESOLVED — Manifest/source pins not compared.** Producer, pool and Mac reader retain the exact frozen/common identity key set and equality to the session's manifest-derived identity. Stale/incomplete manifest/source and host-binding regressions pass; both adapter and evidence sources remain pinned.

16. **RESOLVED — END cleanup leaves complete seal.** `end_reference.py:215` cleans up before completion, seals cleanup-only failure as failed with typed crash evidence, preserves primary exactness and re-raises. All cleanup steps run. Lifecycle/order/reconciliation tests pass.

17. **RESOLVED — Post-summary thrown exactness passes reduction.** The reducer re-derives thrown evidence and forces gate 0 false, superseding earlier measurements. Contradictory admission/reduction and combined-session tests pass.

18. **RESOLVED — Recorded gate-0 failure discarded by cleanup.** Sealed K1, SD1, summary and committed TIERS evidence are independently re-derived at admission. Contradictions and classifications that discard established failure are refused. Actual fake-work loop/classification/reduction tests pass; TIERS-invalid-session precedence remains intact.

19. **RESOLVED — Duplicable or historical authority.** Source-fixed END-JOB/registry paths and unique declaration-name checks remain independent of completion aliases/evidence packaging. Copied-completion, root-switch, deletion/re-addition and older-finalization regressions pass. The shared historical audit preserves latest-finalized-round enforcement for the current pool.

20. **RESOLVED — Whole-repository blob search.** The authority enumerates tree names and reads blobs only in the fixed END namespace; no whole-tree content scan is reintroduced. Bounded-read/path-only regressions pass. Additional probes likewise read only synthetic health inputs.

21. **RESOLVED — Indented claims skipped.** Complete JSON parsing remains in END authority and sealed documents. Compact/indented/malformed claims and receipt-copy regressions pass; forbidden second-root names are refused independently of serialization.

22. **RESOLVED — Asserted predecessor nonconformance.** Full mechanical historical validation, deterministic recomputation, producer admission and fresh-interpreter recheck are verified above.

## New findings

**None.** No blocking or major issue remains in the reviewed scope.

## Tests, frozen bytes and dependency status

Ran the requested command from `reports/explore/k4s-confirm`:

```text
nice -n 19 /mpac/sdicks02/venvs/t1-verifier/bin/python -B -m pytest -q -p no:cacheprovider mac test_end_reference.py test_end_background.py
198 passed in 106.49s (0:01:46)
```

No tests or implementation files were added or changed by this review. This covers offline gates/classifications, synthetic committed authorities and producer-shaped receipts, deterministic pooling/rechecking/Mac admission and spawned fake-work background lifecycle.

Repeated the frozen-byte check:

```text
git diff --exit-code HEAD -- reports/strategy_council_20260928/live-loop/v4/mac-e4-package reports/explore/t1 ':(glob)**/PREREG*'
```

**Exit 0, no output.** The whole TIERS Mac package, including frozen e4v3, T1 tree and PREREG files are untouched relative to HEAD. The manifest-current regression also passes its reused-readonly committed-byte checks.

- PREREG-K4S r3 SHA: `9650972d362299d87f8b1084d450f9a2dbbad516a494e97da6ba33d60fb68b3a`.
- TIERS r3 SHA: `ef0db97ad509753ccf63c7376f800d6db7f0b82ee07f102476eafb939e2a4c77`.
- K4S Mac manifest SHA: `781d25bafac6057253939b8f4f8c99480e2a226c938253f2ab9f8efdd0f775f6`; correctly still `frozen=false`.
- The current prep-owned `DELTA-MANIFEST.json` correctly pins all four END source files. The Round 6 progress note describing those pins as stale is outdated in this worktree. This is not an audit of the rest of the prep/verifier package.

The inherited TIERS dependency remains: frozen `e4v3/measure_tiers.py:70` calls `math.isfinite` without importing `math`. It requires a separate authorized TIERS-side decision before the applicable real Mac path runs. This review neither changes nor authorizes changing frozen bytes; scoped code approval does not qualify that dependency for execution.

## Qualifications reserved for END / the Mac session

**Only END** can qualify the actual authorized SHA-verified T1 corpus and staged SD1/model/runtime/native bundles; executing frozen sources; real committed completion, supervisor exits, blind losses and counted membership; physical topology/affinity/priority; every simultaneous background slot and slot-0 work; real guard admission/census/checkpoints, ≥300 s warm-up and 1 Hz signed full-occupancy MHz joins; K4S-versus-K4 and cross-host native exactness; real charged deadline and pure-poll timings; and the production seal → finalization → pool → independent recheck flow. Every counted host and original attempt must be retained. Every host's local claims must be collected before finalization, and every prior round's complete receipts and nonconforming pool must be collected and committed before a re-run. Offline checks cannot discover work never collected from a host or a host running an unseen/stale checkout. Missing prior committed receipts now refuse the re-run instead of being silently skipped. The registered coordinator ratio-unavailable route remains available.

**Only an authorized Mac session** can qualify Darwin/arm64 execution, same-Mac TIERS native/scorer identity, final committed TIERS verdicts and full §7 ordering, held-lock/session ordering, real SD1 agreement/backend choice, replay perception load and thermal behavior, GC/poll scheduling, loaded speed/p10/p99 and deadline gates. All valid TIERS/K4S sessions must be supplied to their prescribed reductions; a post-release K4S session requires independent mechanical-classification review. Replay-only evidence remains PROVISIONAL until formal E4/T9 re-measures every required input. Coordinator freeze/release/deployment decisions remain separate from this code review.
