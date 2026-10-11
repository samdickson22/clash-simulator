# SOL independent re-review: PREREG-K4S verifier, r2

Verdict: **REJECT**.

Worktree: `/mpac/sdicks02/repos/clasher-k4s-prep`.
Scope: `reports/explore/k4s-confirm/verifier/{verify_k4s.py,test_verify_k4s.py,VERIFIER-NOTES.md}`.
Governing sources: PREREG-K4S-DRAFT-r3.md and the current K4S-SPEC.md, especially §3, §6.1–6.2, §6.5, §6.7 and §7. Locations below are relative to this worktree.

Seven round-1 findings are resolved. Finding 6 is **PARTIAL**: disagreement between game metadata and the CLI now blocks decisions, but the CLI remains unbound to the frozen `plan.json` c*. The updated contract expressly requires that binding. A mutually consistent wrong CLI/game value can still yield an apparently clean result under the wrong sequence. That remaining major issue prevents approval. Two new minor findings concern regression coverage and contradictory notes.

This was an independent read-only review. No SSH, network, actual game outcome data, worktree commits or pushes were used. The only review-authored file is this report. The explicitly requested pytest suite creates temporary synthetic trees and temporary Git seal fixtures; additional reproductions used mocked paths and in-memory synthetic records only.

## Round-1 finding dispositions

### 1. Comparison file opened after release refusal — RESOLVED

Evidence: `verify_k4s.py:979–986` now writes the refusal result and returns immediately. The comparison read at lines 987–989 is unreachable after a `Refusal`. `run()` checks authorization before `reduce_tree()` (lines 874–904).

The requested read-spy tests exist at `test_verify_k4s.py:981–1025`, although the three named release cases have the coverage defect in new finding 9. I independently exercised an unmarked, fully mocked tree with no release, bad coordinator and non-JSON receipt. All three returned exit 2 with their appropriate refusal reason; none read the comparison or any block/game path. Only the supplied receipt was read in the latter two cases.

Remaining wrong/correct reducer effect from this finding: none found. The original unauthorized comparison read is fixed.

### 2. Non-hub blocks counted without durable acknowledgement — RESOLVED

Evidence: `verify_k4s.py:590–593` requires `<id>/hub-ack.json` to be a file whenever host is not `127x01`, appends an error and skips counting otherwise. It ignores the former embedded `hub_ack` field. This matches the updated §6.1 existence requirement; acknowledgement-content validation is not specified by that contract.

Tests at `test_verify_k4s.py:1028–1058` cover missing acknowledgement, an embedded key without the file, and a valid separate file. The first two block the result; the last counts the remote block.

Remaining wrong/correct reducer effect from this finding: none found under the agreed file-existence contract.

### 3. Ledger not replayed in event order — RESOLVED

Evidence: `verify_k4s.py:325–401` now replays events sequentially. A replacement loss requires prior allocation and descriptor equality (359–364); every loss must consume the current active physical block (365–368). Allocation advances the active chain (398–400). `reduce_tree()` requires the counted block to be its final survivor (585–589). Ledger descriptors also undergo independent layout/deck validation (565–568); bank and population caps remain checked.

Tests at `test_verify_k4s.py:1150–1203` cover future loss, a disconnected chain, a repeated original loss, a valid two-step chain and an unlisted replacement. Existing end-to-end replacement and cap tests also pass.

Remaining wrong/correct reducer effect from this finding: none found. The original future-loss ledger now errors, and valid chronological chains retain their logical rotation and subsample membership.

### 4. Missing winner silently treated as a draw — RESOLVED

Evidence: `verify_k4s.py:504–507` requires the winner key and validates its value. Line 539 returns no counted outcome when the key is absent. Explicit null still becomes a draw at 656–657. Any accumulated error stops decisions/view generation at 916–918.

Tests at `test_verify_k4s.py:1061–1088` include missing-key, explicit-null and hash-consistent end-to-end defective-game cases.

Remaining wrong/correct reducer effect from this finding: none found; missing outcomes cannot produce an accepted draw count.

### 5. Scheduled and paired decks not verified — RESOLVED

Evidence: `verify_k4s.py:257–275` verifies the pinned deck-file SHA and independently implements both §2 index mappings. Descriptor deck indices are checked at 301–305. Each arm's game decks must equal the scheduled decks as sorted lists at 529–535, using the predicate at 278–280. Comparing every arm against the same frozen mapping establishes the required paired identities while accepting runner shuffles.

Fixtures at `test_verify_k4s.py:33–59` now contain the indices and real frozen deck identities. Tests at 1091–1147 exercise wrong primary index, guard opponent index, wrong game deck, an opponent swap in one arm, shuffled order and a bad pinned hash.

Remaining wrong/correct reducer effect from this finding: none found.

### 6. c* disagreement still produces CLI-selected admissions — PARTIAL; MAJOR remains

Resolved portion: `verify_k4s.py:514` now treats absent or CLI-disagreeing game c* as an error; `run()` suppresses decisions/view on errors at 916–918. Tests at `test_verify_k4s.py:912–940` verify a positive recorded-0.8 run, CLI/game mismatch and mixed game values. H4 removal retains H1/H2/H3/H5/H6/H7 labels (`verify_k4s.py:699`).

Unresolved portion: §6.2 requires `metadata.c_star` to equal the **frozen plan.json c***, not merely an operator-selected value. There is no plan input/read/hash in `run()` (874–954) or the parser (957–968). The CLI defaults to 0.9 (963), and both validation and sequencing use it (904, 937). `VERIFIER-NOTES.md:137–140,166–168` explicitly acknowledges the missing binding as O11. Delegating this check to the coordinator does not implement the current contract.

Independent reproduction: an entirely in-memory 100-primary/36-guard tree had 1,224 hash-consistent synthetic games, a modeled frozen plan c*=0.8, and every game c*=0.9. With CLI c*=0.9, the actual `run()` performed **zero plan reads**, returned **exit 0 / status OK**, emitted H1–H7 and admitted B at 0.8/0.7/0.6. Its view compared against an identical wrong-branch output with **169/169 matches**. This last comparison demonstrates that the comparison routine cannot detect shared use of the wrong frozen branch; it is not a claim that I ran the current reducer on this invalid fixture.

The synthetic outcomes deliberately pass H1–H3 and fail H4. Applying the frozen 0.8 sequence to those same contrast bounds removes H4 and admits A at 0.8/0.7/0.6. A correct reducer must reject the reproduced inventory because its recorded 0.9 differs from frozen 0.8; the A result is an illustration of sequence sensitivity, not the required output for that invalid inventory. The current reducer's `reduce.py:161` checks metadata against `plan()['c_star']`, corroborating the implementation difference without governing the review.

Fix: load and validate the authoritative frozen plan c* independently, record its source/hash, and use that value for metadata checks and sequencing. An explicit `--c-star`, if retained, must agree with the plan. Preserve an explicit synthetic override/fixture mechanism without allowing it on production inputs. Add regressions for (a) frozen 0.8 versus mutually consistent CLI/game 0.9 and (b) frozen 0.8 with correctly recorded 0.8 games using the normal invocation. No exploration outcomes need to be read or c* derived.

**Wrong/correct reducer effect:** yes. This gap can make the verifier agree with a wrong reducer that also trusts the wrong CLI/recorded value, accepting an inventory a correct reducer rejects. On a correct 0.8 inventory, leaving the CLI at its default also makes the verifier refuse a study a correct plan-bound reducer can process. The sequence difference can change admission levels and potentially usable 0.9.

### 7. Noncanonical rational representations accepted — RESOLVED

Evidence: `verify_k4s.py:789–798` requires a two-integer list, positive denominator, gcd 1 and exact canonical-pair equality. This rejects doubled pairs, negative denominators and noncanonical zero. Tests at `test_verify_k4s.py:718–728` now reject the prohibited forms. Notes O4 at 160–161 correct the prior misreading.

Remaining wrong/correct reducer effect from this finding: none found; canonical correct outputs remain accepted.

### 8. usable_cells compared as a multiset — RESOLVED

Evidence: `verify_k4s.py:864–867` validates cell strings and compares sets. Tests at `test_verify_k4s.py:731–742` accept reordered/duplicate representations of the same set and reject invalid entries. The emitted order at `verify_k4s.py:774` and notes O6 at 164–165 match §6.7.

Remaining wrong/correct reducer effect from this finding: none found.

## New findings

### 9. MINOR — Release-refusal read-spy cases all exercise the earlier marker refusal

Location: `test_verify_k4s.py:981–994`, with fixture `build_scenario()` at 834–850 and `synthetic_root()` at 107–111.

`build_scenario()` leaves the SYNTHETIC marker present, but this parametrized test invokes `main()` without `--synthetic`. Consequently its “no release”, “bad coordinator” and “unreadable receipt” cases all return at `verify_k4s.py:884–885`. They never reach missing-release handling, receipt parsing or `check_seal()`; the test only asserts REFUSED, not the expected reason. An in-memory reproduction confirmed the same marker-refusal reason and zero receipt reads for all three marked cases. Removing the modeled marker exercised the three intended refusal paths successfully.

Fix: remove the fixture's marker before these production-refusal invocations, assert the specific reason for each case, and extend the read-spy coverage to actual post-parse seal failures such as missing committed items or bad SHA/working-tree bytes. The original finding 1 is resolved by the inspected code and independent checks, despite this regression-test gap.

Wrong/correct reducer effect: no present output defect demonstrated; this coverage gap can conceal a future seal regression.

### 10. MINOR — Notes contradict the implemented c* error and the updated sequence contract

Location: `VERIFIER-NOTES.md:93–94,162–163`.

The exit-code description still lists c* mismatch under “1 flags only”, although the implementation now returns 2 and suppresses the decision/view. O5 still says §6.7 does not specify untested steps or their `passed` value, although the current spec at line 308 expressly requires every step and `tested: false, passed: null` after failure.

Fix: remove c* mismatch from the flags-only description and mark O5 resolved against the updated contract. Keep the separate O11 issue visible until frozen-plan binding is implemented.

Wrong/correct reducer effect: no numerical defect; the notes misdescribe operational behavior and a settled contract.

## Verification, cross-check and independence

Requested command:

```text
cd /mpac/sdicks02/repos/clasher-k4s-prep && nice -n 19 /mpac/sdicks02/venvs/t1-verifier/bin/python -B -m pytest -q -p no:cacheprovider reports/explore/k4s-confirm/verifier
```

Result: **132 passed in 7.49s**.

An additional full-size in-memory integer-matrix oracle independently bootstrapped paired differences directly, rather than per-arm totals. It checked all 12 decision contrasts and all 24 exact endpoints at analysis sizes 3000/900/600/300, using explicit order-statistic weights 1/40 and 39/40 at positions 249/250 and 9749/9750. All resampled contrast arrays/endpoints matched, and the final RNG states matched after all four analyses. No arithmetic, RNG-order, inclusive-margin, strict-SUP, H-label or valid-input counting regression was found.

The allowed `receipts/reducer-verifier-crosscheck.json` records **169/169 matches** for each of admit-all, stop-at-H2 and suspended, with four ledger events per scenario. Its recorded current reducer SHA and verifier SHA both match the files reviewed here (below), correcting the stale-reducer limitation in r1. It supports agreement on those synthetic scenarios. All three contain H1–H7; the receipt does **not** establish c*=0.8 agreement or frozen-plan mismatch detection. Passing comparison scenarios cannot replace validation of the authoritative frozen inputs.

The verifier imports standard-library modules and numpy only, and does not import the reducer, schedule, common or other study code. Inspection of the permitted reducer source found different structures/validation organization and no apparent copied reducer implementation. Shared bootstrap mathematics follow the same explicit contract. Static inspection cannot certify the author's historical reading behavior; the source and notes are consistent with independent authorship.

Reviewed SHA-256 values:

- verify_k4s.py: `47e59142fcafb6fdae68943402ceb3129e31d317cabc42c8d07e0e766412738e`
- test_verify_k4s.py: `4ec0b98e44ee639b4d5cbb478a5013ae3b349b151253de1302ef39f4ea0ba71b`
- VERIFIER-NOTES.md: `6115481a433b149f5b5c619ea56ce790f1f5469b003a4287154401e26be974cf`
- reduce.py: `9c2e5ac00aac65827daa7596c93b5f7993d748976e405202d09e1e1bc24706c8`
- K4S-SPEC.md: `e80652d4859504eaf6a9256a3b3672a247a3f1993160ab17378587e7cdd93e53`
- PREREG-K4S-DRAFT-r3.md: `9650972d362299d87f8b1084d450f9a2dbbad516a494e97da6ba33d60fb68b3a`

Release readiness requires completing finding 6's frozen c* binding. Findings 9–10 should be corrected with that revision. The remaining major issue **can make the verifier agree with a wrong reducer result or reject an otherwise correct plan-bound result**; no additional valid-input numerical disagreement was found.
