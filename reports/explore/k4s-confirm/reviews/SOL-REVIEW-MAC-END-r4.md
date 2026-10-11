# SOL independent re-review: K4S Mac measurement and END, r4

**Verdict: REJECT.** Finding 18 is resolved, and finding 9 can now be closed. Finding 19 remains **MAJOR / PARTIAL**: the authority's canonical location is derived from a caller-supplied completion-artifact location, so copying the same completion can establish another accepted authority. Two new major defects affect the stray-claim check: it searches the entire committed repository's contents, contrary to the health-only boundary, and silently skips valid indented JSON claims. Findings 4 and 14 remain partial. F-8 should remain unfrozen pending correction and independent re-review.

Reviewed worktree: `/mpac/sdicks02/repos/clasher-k4s-prep`, HEAD `962ecce2cf05223aada69746f2758bcf573c82f6`, 2026-10-11. I did not write the implementation. Reviewed the r1/r2/r3 Mac/END reviews, `mac/PROGRESS-MAC.md`'s “Round 4 (fixes for Sol r3)” mapping, the requested Mac/END code, procedures and tests, and relevant frozen dependency source. Governing contracts: PREREG-K4S r3 §1.4, §1.5, §4.4, §4.5, §5.4; CONFORMANCE-r2 N2/F-8; RECHECK-r3 R3/R5; TIERS r3 §6–§7 and frozen e4v3; K4S-SPEC §4/§8.

No network, SSH, Mac/fleet-host contact, model/native/corpus execution, or game outcome data was used. The worktree was read only. Additional probes ran in memory and read only synthetic health receipts from the required suite; mocked Git responses simulated additional committed health artifacts without creating them. I issued no Git commit or push. The explicitly requested existing suite internally creates commits in temporary synthetic repositories. This review file is my sole authored file. Existing worktree changes, including changes outside this scope, belong to other workers.

Locations below are relative to `reports/explore/k4s-confirm/` unless otherwise stated.

## Per-finding status

1. **RESOLVED — Shipped SD1 manifest compatibility.** `mac/k4s_logic.py:760` still validates the nested checkpoint/calibration schema, threshold/mode and complete inference-source inventory. The shipped-schema and negative pin tests pass. Real source staging remains a session prerequisite.

2. **RESOLVED — END/Mac rate names.** `end_pool.py:176`, `mac/measure_k4s.py:174` and `mac/k4s_logic.py:879` retain the shared bare rate and integer count names. The pool → recheck → Mac-reader → gate-input integration test passes across all five cells.

3. **RESOLVED — Frozen pooling statistic/direction.** `end_pool.py:133` retains geometric mean of pooled per-state median / host per-state median. Frozen-helper, slow-subset and endpoint tests pass. K4S's explicitly inclusive bounds remain documented; frozen TIERS bytes are unchanged.

4. **PARTIAL — Reporting provenance.** Committed completion/artifact bytes, counted membership, slots/priority, guard/warm-up and signed full-occupancy MHz checks remain intact (`end_evidence.py:158`, `end_pool.py:303`). The new authority is stronger than the r3 registry, but `all_original_attempts_classified=True` still rests on an authority that can be duplicated and a stray-claim check that can miss claims. See 19 and 21. The broader health-only guarantee also needs 20.

5. **RESOLVED — Bundle/native/kernel and frozen measurement identity.** `end_reference.py:91` validates identity before backend construction; executing END sources, full frozen common pins and separate per-host bundle pins remain checked. The negative identity and producer-shaped multi-host tests pass. Actual artifacts/execution are END-time qualifications.

6. **RESOLVED — Per-state repeats, deadline rows and cells.** `end_pool.py:83` still requires exact state membership, three finite positive non-Boolean observations, unique state/repeat rows, Boolean flags and registered budgets/charge scales. Negative and optimized-Python tests pass.

7. **RESOLVED — Committed TIERS receipts.** `mac/k4s_logic.py:517` retains ancestry, exact committed inventory and byte equality. `mac/measure_k4s.py:262` requires the commitment arguments. The held-lock procedure still commits the sealed TIERS copy before K4S admission; negative receipt tests pass. Complete collection of supplied TIERS sessions remains an operator duty.

8. **RESOLVED — Classification seal contents.** `mac/classify_k4s_failure.py:278` verifies the classification seal, inclusion/hash of `classification.json`, and source session seal/status; consumed summary/precondition bytes remain sealed. Tampering and omitted-summary tests pass.

9. **RESOLVED — Cleanup/status consistency.** Clean measurement followed by cleanup failure remains a technical failure. Established thrown or recorded gate-0 failure remains a valid no-repeat gate outcome through later cleanup/harness failure. The main → classify → reduce tests now cover the recorded corpus and SD1 cases as well as the prior thrown-failure case. See 18.

10. **RESOLVED — Background worker rejects K4S schema/population.** `end_reference.py:360` uses the K4S-owned adapter; `end_background.py:70` validates the K4S evidence, bundle plan/evidence, slots and reporting joins while retaining the frozen corpus loop and worker lifecycle. Actual spawned lifecycle/error tests with fake work pass. Real model-backed fleet operation is not established offline.

11. **RESOLVED — Per-host bundle SHA blocks multi-host pooling.** Shared identity and per-host bundle receipts remain separate (`end_reference.py:91`, `end_pool.py:164`, `:320`). Producer-shaped two-host integration and negative shared/swapped-host pin tests pass.

12. **RESOLVED — Membership/exits/ledger reconciliation.** `end_evidence.py:64` still checks verbatim completed membership, exit-SHA-bound losses, replacement descriptors, logical populations, counted owners and the registered descriptor extension. Phase/launch checks and negative membership/health-field tests pass. Finding 20 concerns the newly introduced whole-repository scan, rather than regression of this reconciliation.

13. **RESOLVED — END attempt reads escape their seal/recheck inventory.** `end_evidence.py:228` retains exact receipt-directory inventory and byte re-hashing; `end_pool.py:243` reconciles required completion/failure receipts before the frozen classifier reads them. Recheck still requires consumed local receipt inputs in its before/after inventory. Negative seal/classifier/recheck tests pass. Finding 20 is a new, separate read path through Git.

14. **PARTIAL — Caller's attempt list defines “all attempts.”** Exact ordered matching with finalized claims, maximum one repeat, and current-HEAD/finalization reconciliation now work within a chosen authority (`end_pool.py:263`, `end_evidence.py:483`). Omission/reordering/excess-attempt tests pass. Authority duplication and ignored stray claims still leave the global completeness claim unsupported: 19 and 21.

15. **RESOLVED — Raw manifest/source pins not compared.** `mac/k4s_logic.py:840` requires the complete common key set and frozen manifest/source identity. Producer, pool and Mac admission continue to use it. Stale/incomplete pin tests pass; adapter/evidence source pins remain in the manifest.

16. **RESOLVED — END cleanup leaves a complete seal.** `end_reference.py:213` runs cleanup before completion, seals cleanup-only failures failed with typed crash evidence, preserves primary exactness and re-raises. `cleanup_steps` stops the monitor first and attempts all cleanup operations. Lifecycle/order/classifier/pooling tests pass.

17. **RESOLVED — Thrown post-summary exactness reduces as passing.** `mac/classify_k4s_failure.py:300` re-derives thrown evidence and forces gate 0 false, superseding earlier measured summary inputs. `reduce_sessions:241` refuses a contradictory gate-failure summary. Existing thrown-failure/cleanup/combined-session regressions pass.

18. **RESOLVED — Recorded gate-0 failure discarded after cleanup failure.** `gate0_evidence:48` derives evidence from sealed K1, SD1, summary and committed TIERS preconditions, distinguishes tolerated corpus differences and SD1 disagreements, and rejects contradictory summaries. `classify_records:141` preserves the established failure without granting a repeat, retaining cleanup/harness diagnostics. `read_entry:300` independently re-derives that evidence for every classification and refuses a technical/valid classification that would discard it. Tests at `mac/test_measure_k4s.py:1173` exercise the actual measurement loops with fake work through main → classify → sealed admission → reduction, alone and alongside a good session; both recorded-failure kinds kill K4S, retain both valid sessions and refuse P7 repeat admission. Partial traces, tolerated disagreements, contradictions and TIERS-invalid precedence are also tested. This closes the reported defect without changing TIERS.

19. **PARTIAL / MAJOR STILL OPEN — Attempt authority can be duplicated through a copied completion location.** The direct registry-root switch and older-finalization cases are fixed, but the authority is not yet independent of descriptor-selected evidence. Details follow.

## Remaining finding 19

**Locations:** `end_evidence.py:327`, `:338`, `:158`, `:474`; `end_pool.py:390` and `:397`.

`job_path()` calls the supplied evidence document's `completion.repository_path` canonical and takes its parent. `end_evidence()` proves that the named artifact equals an ancestor blob; it does not prove that this path is the unique reporting job's authoritative completion location. The frozen `fleet_end.artifact()` likewise accepts any repository-relative blob path with matching bytes.

After an exactness failure under authority A, a byte-identical copy of that completion can be committed under another directory. A new END evidence document changes only that repository path, yielding evidence SHA B while retaining the same completion SHA, plan, counted membership and frozen K4S identity. A new, immutable `END-JOB.json` beside the copy can name registry B. New producer attempts bind to B. Each authority and finalization can satisfy its own immutable/current-HEAD checks. `stray_claims()` regards A's claims as unrelated because their job and evidence SHAs both differ from B, so it does not reconnect the original failure with the new authority. No original authority or claim needs to be modified or deleted.

**Evidence:** An in-memory probe ran the actual `end_evidence()` validator on the required suite's synthetic committed health evidence. It changed only `completion.repository_path` to `copied-reporting/completion.json`; the Git blob read for that copy was redirected to the original completion blob, simulating a committed byte-identical copy. All other membership/artifact/ancestry checks ran against the existing synthetic fixture. Validation passed, with identical completion SHA, plan SHA and membership, a new evidence SHA, and job paths `END-JOB.json` versus `copied-reporting/END-JOB.json`. A separate in-memory Git-transport model ran the unmodified `job_registry()` against two immutable authorities with the same completion/plan identity and distinct evidence SHAs/roots; both were accepted while both authorities' claims existed at HEAD. These are validator/authority probes, not claims that a full real producer or an on-disk copied job was executed.

**Fix:** Establish the reporting job and its sole completion/END authority location independently of the pool descriptor and END evidence artifact aliases, before the first attempt. Bind that authority to the registered reporting job; refuse a second declaration for the same reporting completion/job even when its evidence packaging differs. Make producer and pool consume that same binding. Add a regression that retains an original exactness failure, copies the completion to another committed directory, repackages the evidence and attempts a second job/registry. Direct root-rewrite tests alone do not cover this case.

## New findings

20. **MAJOR — Stray-claim detection crosses the health-only boundary by scanning every committed blob.**

    **Location:** `end_evidence.py:459–480`, called by `job_registry:547` during pooling and independent recheck.

    `git grep -l -F CLAIM_PREFIX HEAD -- .` searches contents throughout HEAD, including files that were never admitted as health receipts. `-l` restricts the output to names; it does not prevent Git from reading/searching those blobs. A matching file is subsequently opened with `git show` and parsed before its schema is checked. This cannot support the module/producer/pool's “never reads game or outcome bytes” contract or PREREG r3 §4.5's sealed pre-release boundary. It also extends the old consumed-input guarantees to an unbounded source that is not enumerated in `pool-inputs.json`.

    **Evidence:** Source inspection and the captured command arguments of the in-memory scanner probe. I deliberately did not run this whole-tree scan on the actual worktree or inspect any actual outcome blob. Existing synthetic tests have no game/outcome files and therefore do not exercise the boundary.

    **Fix:** Enumerate paths/tree metadata without opening arbitrary contents; inspect only an independently registered, health-only launch/claim namespace and authenticated inventory. Enforce that namespace in the producer and collector so completeness does not require searching game files. Check the read boundary with synthetic marker files or mocked subprocess reads; do not use real outcomes to test it.

21. **MAJOR — Valid indented JSON claims outside the registry are silently ignored.**

    **Location:** `end_evidence.py:467–470` (also affects receipt copies at `:476`).

    The scanner parses only `stdout.decode().splitlines()[0]`. Ordinary `json.dumps(claim, indent=2)` starts with `{`, so `json.loads('{')` raises and the `except` treats the claim as source/documentation text. A committed, correctly job/evidence-bound claim in another root can therefore be invisible while the selected canonical registry/finalization remains internally consistent. The same formatting bypass applies to an indented receipt copy containing `claim` and `claim_sha256`. Existing hidden-registry tests use single-line canonical JSON, so they miss it.

    **Evidence:** An in-memory probe called the actual `stray_claims()` with identical synthetic Git search results and identical bound claim fields. The compact JSON form raised `END attempt claim outside the canonical END-JOB registry: hidden/attempt-00.json`; the indented form returned successfully. Only Git transport was mocked; no fixture or repository bytes were changed.

    **Fix:** Parse complete JSON bytes for admissible health claim documents, or explicitly enforce the registered serialization and refuse violations. Do not silently equate a parse error in an admissible claim file with harmless documentation. Add compact/indented/malformed claim and receipt-copy cases, using the bounded health namespace required by 20. Until fixed, finalized inventory equality cannot establish that all original attempts were retained.

## Frozen bytes and dependencies

The following command was run and repeated before writing this review:

```text
git diff --exit-code HEAD -- reports/strategy_council_20260928/live-loop/v4/mac-e4-package reports/explore/t1 ':(glob)**/PREREG*'
```

**Exit 0, no output.** The matching `git diff --numstat HEAD` is empty. The entire TIERS Mac package, including frozen e4v3, the T1 tree and PREREG files are untouched relative to HEAD. The passing manifest-current test also compares reused-readonly source pins with committed blobs. The requested implementation scope has the pre-existing round-4 worktree changes; this review added none there.

PREREG-K4S r3 SHA: `9650972d362299d87f8b1084d450f9a2dbbad516a494e97da6ba33d60fb68b3a`. TIERS r3 SHA: `ef0db97ad509753ccf63c7376f800d6db7f0b82ee07f102476eafb939e2a4c77`. Mac manifest SHA: `0ea5312c42229343729495fdecf83b9d00cc12c670c618d9d104bbde25f2ee32`; it remains correctly `frozen=false`.

The inherited TIERS dependency still exists: frozen `e4v3/measure_tiers.py:70` uses `math.isfinite` without importing `math`. That requires its own authorized TIERS-side decision before the applicable real Mac path can run; this review neither changes nor authorizes changing frozen bytes. K4S's inclusive [0.95, 1.05] endpoint interpretation remains disclosed and tested, without altering TIERS's floating-point check.

## Tests and qualifications reserved for END / the Mac session

Required command, from `reports/explore/k4s-confirm`:

```text
nice -n 19 /mpac/sdicks02/venvs/t1-verifier/bin/python -B -m pytest -q -p no:cacheprovider mac test_end_reference.py test_end_background.py
186 passed in 67.42s (0:01:07)
```

The suite establishes offline gate/classification logic, synthetic committed evidence and authorities, receipt integrity checks, producer-shaped multi-host pool/recheck/Mac compatibility, and the background adapter's spawned lifecycle with injected work. It does not establish real model/native timings or fleet/Mac operation. The independent probes above expose cases outside the passing coverage.

**Only at END** can the coordinator qualify real per-host bundle/artifact staging; committed production completion, exits, losses and counted inventory; physical topology/affinity/priority; actual guard admission and live census/checkpoints; every simultaneous model-backed background slot and slot-0 measurement; the real ≥300 s warm-up and 1 Hz/full-occupancy MHz comparison; native/Torch K4S-versus-K4 and cross-host exactness; charged deadline and pure-poll timings; and the complete production producer → seal → finalization → pool → independent recheck flow. Every host's local claim directory and every attempt receipt must be collected before finalization. Offline pool code cannot observe claims omitted from an uncollected host or an unseen checkout; collection completeness and distribution of the finalization/current authority to every host remain explicit production qualifications. The registered ratio-unavailable route remains available when END cannot qualify.

**Only at the authorized Mac session** can the operator establish actual Darwin/arm64 identity, the same qualified native/scorer as the committed TIERS session, completion of TIERS's full §7 list, held-lock/session ordering, authentic TIERS final verdicts, real SD1 agreement and corpus exactness, replay load/FPS/processed coverage, measured speed/poll/deadline/GC inputs, census/thermal validity and cleanup behavior. Any post-release session needs the preregistered independent validity review. Replay remains provisional until formal E4/T9 re-measures the required inputs; activation still requires the registered coordinator/TIERS conditions.

Absence of those future hardware runs is not the reason for rejection. The remaining offline authority and read-boundary defects are.
