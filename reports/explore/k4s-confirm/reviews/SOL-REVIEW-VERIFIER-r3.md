# SOL independent code re-review: PREREG-K4S verifier, r3

Verdict: **APPROVE**.

Worktree: `/mpac/sdicks02/repos/clasher-k4s-prep`.
Scope: `reports/explore/k4s-confirm/verifier/{verify_k4s.py,test_verify_k4s.py,VERIFIER-NOTES.md}`.
Governing sources: PREREG-K4S-DRAFT-r3.md and K4S-SPEC.md. Prior reviews: SOL-REVIEW-VERIFIER-r1.md and SOL-REVIEW-VERIFIER-r2.md. Source locations below are relative to the scoped verifier directory unless otherwise stated.

The round-4 changes resolve the remaining major finding 6 and minor findings 9–10. Findings 1–5 and 7–8 remain resolved. No blocking, major, or new actionable defect was found in this review. The verifier now uses the plan's c* for both game validation and the fixed sequence; mutually consistent but wrong CLI/game values cannot select a different branch from the plan.

This was an independent read-only review. I did not author or modify the implementation. No SSH, network, reporting game outcome data, or worktree commits/pushes were used. The only review-authored file is this report. The expressly requested pytest suite created its temporary synthetic trees and temporary Git seal fixtures. Additional checks used generated integer matrices and entirely in-memory synthetic records with mocked reads, without writing additional fixtures or changing the real plan. The reducer was hashed only to identify the supplied cross-check revision; its implementation was not read for this round.

## Per-finding dispositions

### 1. Comparison file opened after release refusal — RESOLVED

`verify_k4s.py:1029–1032` writes the refusal result and returns immediately; the comparison read at line 1035 is unreachable after a refusal. Authorization checks at lines 912–934 precede plan loading, ledger loading and counting. The corrected read-spy tests at `test_verify_k4s.py:1091–1181` cover missing release, wrong coordinator, malformed JSON receipt, missing committed item, wrong declared SHA, differing working-tree bytes, and synthetic/test-count flag refusals. They assert the specific refusal and no block/game/comparison reads. Seal-failure cases also assert no plan read. My canonical-plan/CLI-disagreement check independently confirmed no block/game/comparison reads after that new refusal path.

### 2. Non-hub completion without durable acknowledgement — RESOLVED

`verify_k4s.py:628–631` requires `<id>/hub-ack.json` to be a file for every non-127x01 block and skips counting otherwise. An embedded `hub_ack` key is not accepted as evidence. Tests at `test_verify_k4s.py:1186–1214` retain missing-file, embedded-key-only and separate-file positive coverage. This implements the contract's acknowledgement-file existence requirement; the contract does not prescribe acknowledgement-content validation.

### 3. Ledger not replayed in blind event order — RESOLVED

`verify_k4s.py:363–439` retains sequential allocation/loss replay: replacements must have been allocated earlier, their lost descriptors must match the allocation, and each loss must consume the current active physical block. Allocation advances that original's active survivor. `reduce_tree()` independently validates ledger descriptors at lines 603–606 and requires the counted final survivor at lines 623–627. Bank indices, same-cell/population constraints, original-id `replaces`, and per-population caps remain checked. Tests at `test_verify_k4s.py:359–441,1308–1359` cover valid chains, premature loss, disconnected chains, repeated original loss, unlisted replacements and caps. No chronology/counting regression was found.

### 4. Missing winner classified as draw — RESOLVED

`verify_k4s.py:542–545,577` requires the winner key and distinguishes its absence from explicit null. Only explicit null is counted as a draw at lines 694–695. Missing, malformed or non-terminal outcomes accumulate input errors, which stop analysis, admissions and view generation at lines 959–961. Direct and hash-consistent end-to-end missing-winner tests remain at `test_verify_k4s.py:1219–1246`; the explicit-null control passes.

### 5. Scheduled and paired decks not checked — RESOLVED

`verify_k4s.py:262–271` checks the pinned guard-decks SHA. Lines 307–318 independently implement the primary and guard mappings and compare sorted card lists. Descriptor indices are checked at lines 338–343, and every arm's own/opponent decks are checked against that same scheduled identity at lines 567–573. Tests at `test_verify_k4s.py:1249–1303` retain wrong-index, guard mapping, wrong-game-deck, one-arm opponent-swap, shuffled-order and bad-pin coverage. Arm pairing cannot be established merely by a numeric cell label anymore.

### 6. c* unbound to frozen plan / wrong CLI-selected admissions — RESOLVED

The remaining r2 major issue is fixed. `PLAN_PATH` at `verify_k4s.py:84` names the study's canonical `plan.json`. `load_plan()` at lines 274–304 reads its bytes, validates c*, and returns source path, SHA-256 and normalized value. A different plan requires synthetic authorization and its own marker; a marked canonical plan is refused. The parser no longer defaults `--c-star` to 0.9 (lines 1006–1009).

`run()` loads the plan after authorization, uses its c*, and refuses an explicitly disagreeing CLI value before any counting (lines 937–940). That same plan value reaches per-game validation at lines 946 and 552 and sequencing at line 980. A game's missing or disagreeing c* is an input error; lines 959–961 prevent decisions/view generation. Output records `plan` and `c_star` at lines 951–953. This satisfies K4S-SPEC §6.2 without reading exploration results or deriving c* again.

Tests at `test_verify_k4s.py:922–1042` cover default-plan provenance, both positive branches, consistent wrong CLI/games versus a 0.8 plan, game disagreement without a CLI override, alternate-plan restrictions, invalid c* and non-JSON plans. The 0.8 tests use expressly marked test plans. To independently check the canonical path too, I mocked the bytes returned by the actual default `PLAN_PATH`, leaving the real file unchanged, and ran the real CLI/counting path against 1,224 entirely in-memory hash-consistent synthetic games:

- Plan 0.8, games 0.8, no `--c-star`: exit 0 / status OK, recorded correct plan path/hash, labels H1/H2/H3/H5/H6/H7, A at 0.8/0.7/0.6, and no 0.9 admission.
- Plan 0.8, CLI 0.9 and games 0.9: exit 2 / REFUSED, with zero block/game/comparison reads.
- Plan 0.8, games 0.9, no CLI override: exit 2 / ERRORS, 1,224 c* errors, no hypotheses/admissions/view.
- Canonical plan carrying a SYNTHETIC marker: exit 2 / REFUSED, with zero block/game/comparison reads.

The original shared-wrong-branch acceptance is therefore no longer possible through the reviewed CLI behavior.

### 7. Noncanonical rational forms accepted — RESOLVED

`verify_k4s.py:827–836` requires exactly two integer components, positive denominator, gcd 1 and exact canonical-pair equality. Negative denominators, reducible forms, noncanonical zero, zero denominators and float components fail. Tests at `test_verify_k4s.py:717–728` retain the noncanonical rejection and canonical acceptance controls. The comparison still checks every contrast bound.

### 8. usable_cells compared as multiset — RESOLVED

`verify_k4s.py:902–905` validates a list of valid cell strings and compares sets. The emitted list follows the required 0.9/0.8/0.7/0.6 order at line 812. Reordering/invalid-entry tests remain at `test_verify_k4s.py:731–741`. Inspection confirms duplicate multiplicity does not affect equality, as §6.7 requires.

### 9. Release read-spy tests stopped at the earlier marker refusal — RESOLVED

`production_tree()` at `test_verify_k4s.py:1072–1076` removes the synthetic marker before production-refusal invocations. The three cases at lines 1091–1107 now assert their distinct reason, preventing the original false coverage. New post-parse seal cases at lines 1110–1146 exercise missing committed bytes, digest mismatch and working-tree disagreement using temporary Git fixtures. The read spies establish no block/game/comparison or plan reads for each seal failure. Separate marker/test-count cases also assert their intended reasons.

### 10. Notes contradicted c* errors and the sequence contract — RESOLVED

The current exit-code description at `VERIFIER-NOTES.md:120–121` distinguishes CLI/plan refusal from game/plan input errors, both exit 2. Current interpretation 10 at lines 164–166 states the plan binding and decision suppression. O5 at lines 188–189 recognizes the complete sequence with `tested: false, passed: null` after failure; O11 at lines 192–193 is correctly marked resolved. The round-4 section at lines 19–44 documents the implementation and regressions. Earlier round sections describe historical behavior; the current operational statements resolve r2's contradictions.

## New findings

None. No additional fix is required for approval of the reviewed verifier scope.

## Validation and evidence limits

Requested command:

```text
cd /mpac/sdicks02/repos/clasher-k4s-prep && nice -n 19 /mpac/sdicks02/venvs/t1-verifier/bin/python -B -m pytest -q -p no:cacheprovider reports/explore/k4s-confirm/verifier
```

Result: **149 passed in 8.82s**.

An additional full-size generated-integer-matrix oracle independently resampled paired differences directly, rather than computing differences of bootstrapped arm totals. It matched the complete resampled arrays for all 12 decision contrasts, all 24 exact endpoints and the final RNG state after P_full/G_full/P_sub/G_sub at n=3000/900/600/300. The independently formed endpoints used `(v[249] + 39*v[250])/40` and `(39*v[9749] + v[9750])/40`, followed by multiplication by 100/n. No arithmetic, RNG consumption, inclusive-margin, strict-SUP, H-label, admission, veto, usable-cell or inclusive-validity regression was found. An initial version of this review-only oracle reversed the interpolation weights; correcting the oracle to the contract's positions produced the stated agreement, without changing verifier code.

The allowed `receipts/reducer-verifier-crosscheck.json` reports **169/169 matches in each of admit-all, stop-at-H2 and suspended**, with four ledger events per scenario. Its recorded verifier, reducer and plan SHA-256 values all match the current files below. This supports current-revision agreement on those three synthetic scenarios. All three use c*=0.9; the receipt alone does not prove 0.8 agreement, malformed-input handling, or a production release. The separate tests and canonical-path in-memory checks above establish the reviewed 0.8 branch and mismatch behavior.

The verifier imports standard-library modules and numpy only, with no reducer or other study implementation imports. Static inspection cannot certify the author's historical reading behavior. Approval covers this independent verifier's contract and comparison behavior; it does not authorize outcome release or replace the coordinator's freeze/release prerequisites. The explicitly documented secondary outputs remain outside this verifier task's scope.

## Reviewed SHA-256 values

- `verify_k4s.py`: `43c4a574a48a245fa844a4b0fa69ec1be1d482bd1b1be56b9acf242a3a1b4947`
- `test_verify_k4s.py`: `4da5a62f3865255528919d90f4fb1a13d6907bd28e029cac115bee2c1ac0a4e9`
- `VERIFIER-NOTES.md`: `b1b269198d3fbdbf8dc46fcd45b476013f852706bf9694ecb14d8d1a4b112066`
- `K4S-SPEC.md`: `e80652d4859504eaf6a9256a3b3672a247a3f1993160ab17378587e7cdd93e53`
- `PREREG-K4S-DRAFT-r3.md`: `9650972d362299d87f8b1084d450f9a2dbbad516a494e97da6ba33d60fb68b3a`
- `plan.json`: `38064dcdeff96fb006f6e261c246a458f423d97cc53278c3921888241c8d22cf`
- `reduce.py` (hash only): `9c2e5ac00aac65827daa7596c93b5f7993d748976e405202d09e1e1bc24706c8`
