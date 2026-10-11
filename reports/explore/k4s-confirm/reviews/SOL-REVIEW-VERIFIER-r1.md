# SOL review: PREREG-K4S independent verifier, r1

Verdict: **REJECT**.

Reviewed worktree: `/mpac/sdicks02/repos/clasher-k4s-prep`.
Scope: `reports/explore/k4s-confirm/verifier/{verify_k4s.py,test_verify_k4s.py,VERIFIER-NOTES.md}`.
All finding locations below are relative to this worktree. Review performed against PREREG-K4S r3 (governing) and K4S-SPEC §2, §3, §5, §6 and §7. No reporting game outcomes, SSH, network or worktree commits/pushes were used. Only this review artifact was authored. The requested test suite uses temporary synthetic trees and temporary Git repositories for its seal fixtures.

The statistical implementation is sound on inspected valid inputs: integer losses and draws; logical-index ordering and subsample selection; paired, cell-stratified bootstrap; P_full/G_full/P_sub/G_sub RNG order; exact rational linear percentiles; inclusive NI and strict SUP; H1–H7 with H4 omitted at c*=0.8; stop/admission/veto/usable-cell rules; inclusive validity window. The blockers are in access control and acceptance of invalid evidence, rather than the bootstrap formula.

No imports of the reducer or other study implementation modules, and no apparent copied reducer implementation, were found. The verifier uses standard-library modules and numpy, defines its own constants and validation, and has different control/data structures from reduce.py. Static review cannot establish the author's historical reading behavior; the notes' claim of independent authorship is consistent with the inspected implementation.

## Findings

1. **BLOCKER — The comparison input is opened after release refusal.**

   **Location:** `reports/explore/k4s-confirm/verifier/verify_k4s.py:897` and `verify_k4s.py:899`–906.

   **Scenario:** `run()` raises Refusal for a missing/invalid release, but `main()` catches it and then unconditionally reads `--compare`. That file contains aggregate outcomes, and the CLI does not restrict it to reducer output: passing a game file as `--compare` opens game bytes before any successful seal. A mocked read with `--root /__k4s_review_nonexistent_tree --compare /__k4s_review_sealed_reducer_result` and no release returned `status: REFUSED`, exit 2, while recording a read of the comparison path. No actual outcome file was opened in this reproduction. Returning a refusal after opening the file does not restore the r3 §4.5 seal.

   **Fix:** Skip all comparison reads when release/synthetic authorization fails. Make successful authorization explicit, or return immediately from the refusal branch before accessing `--compare`. Add a read-spy regression asserting that neither a game nor a comparison file is opened after every seal refusal.

   **Wrong/correct reducer effect:** This is an unauthorized outcome read, independent of numerical agreement. On the reproduced refusal there is no verifier_view, so it does not falsely report equality; it violates the barrier even when the reducer result would be correct.

2. **MAJOR — Non-hub blocks count without the required durable hub acknowledgement.**

   **Location:** `reports/explore/k4s-confirm/verifier/verify_k4s.py:550`–552.

   **Scenario:** The spec §6.1 and r3 §4.4 require hub-acknowledged/hash-verified completion for a non-127x01 host. The verifier merely flags a missing `hub_ack` key in complete.json and continues counting. Any value, including `hub_ack: false`, suppresses even that flag. It does not check the separate durable acknowledgement receipt. An entirely in-memory 100-primary/36-guard test tree with host `127x03` and no acknowledgement counted all 1,224 games with zero errors; adding `hub_ack: false` yielded zero errors and zero flags. Conversely, an actual separate `hub-ack.json` without an embedded key can receive the misleading warning. The current reducer checks for the separate receipt, corroborating the format disagreement; the governing requirement is the spec/r3 hub acknowledgement, not the reducer's code.

   **Fix:** Require the durable hub acknowledgement for every non-hub counted block, using the agreed receipt format (currently `<block>/hub-ack.json`), and fail counting when absent. Do not treat an arbitrary complete.json key as proof. Exercise remote-host blocks with missing, false and valid acknowledgement evidence.

   **Wrong/correct reducer effect:** Can agree with a wrong reducer that counts unacknowledged blocks. A correct reducer would reject that inventory; the verifier instead emits statistics. On valid separate-acknowledgement inputs it can also produce a false warning/flags-only exit, although counts remain correct.

3. **MAJOR — The ledger is not replayed as an allocation/loss chain in blind event order.**

   **Location:** `reports/explore/k4s-confirm/verifier/verify_k4s.py:294`–306 and `verify_k4s.py:308`–343.

   **Scenario:** All lost descriptors are installed before processing any event. The code checks bank indices, cell membership and total caps, but never requires a lost replacement to have been allocated by an earlier event, or to be the active replacement for that logical original. A concrete production-size example is:

   - Event 1: lose `primary-3053` (index 3053, cell 3, replaces `primary-0003`), allocate `primary-3003` (k=0, same original).
   - Event 2: lose `primary-0003`, allocate `primary-3053` (k=1, same original).
   - Count `primary-3003` and the other reporting originals.

   This loses the k=1 replacement before it was issued. All local bank/cell/cap checks pass, and the final lost-id set hides the chronology error. The analogous 100-primary test-size ledger (indices 153 and 103) was accepted by check_ledger, descriptor validation and a complete in-memory reduce_tree run with zero errors/flags; its counted survivor was primary-0103.

   **Fix:** Replay events sequentially. Originals start as active reporting blocks; replacements become eligible to be lost only after allocation in an earlier event. Require each loss to consume the active physical block, each allocation to advance its logical chain, and the counted block to be the resulting survivor. Retain bank and population-cap checks. Add future-loss and disconnected-chain regressions.

   **Wrong/correct reducer effect:** Can agree with a wrong reducer using only final-set validation, accepting a nonmechanical final inventory and therefore potentially different integer counts/admissions. A correct implementation rejects this ledger; valid chronological chains need not change.

4. **MAJOR — A missing outcome is silently classified as a draw.**

   **Location:** `reports/explore/k4s-confirm/verifier/verify_k4s.py:446`–447 and `verify_k4s.py:580`–583.

   **Scenario:** `meta.get("winner")` returns None both for an explicit JSON null and for an absent field. Deleting winner from a terminal synthetic game yields no check_game error and returns winner=None; reduce_tree then counts a draw/non-loss. A missing winner is not a recorded draw under spec §5–6.2. A truncated or schema-defective game whose SHA matches complete.json can consequently lower losses or inflate draws instead of invalidating the inventory.

   **Fix:** Require the winner key to exist before validating its value; only explicit null denotes a draw. Add missing-winner and explicit-null controls, including an end-to-end hash-consistent defective record.

   **Wrong/correct reducer effect:** Can agree with a wrong reducer that also defaults missing winners to null, including wrong losses, CIs and admissions. A correct reducer rejects the missing outcome, rather than reporting it as a draw.

5. **MAJOR — Population-cell deck assignments and paired decks are not verified.**

   **Location:** `reports/explore/k4s-confirm/verifier/verify_k4s.py:251`–274 and `verify_k4s.py:429`–471; fixture omissions in `reports/explore/k4s-confirm/verifier/test_verify_k4s.py:34`–59.

   **Scenario:** Descriptor validation never examines own_index/opponent_index, and game validation never examines own_deck/opponent_deck. A primary cell-3 descriptor with both deck indices set to 999, plus a game with both deck arrays set to ["WRONG"], passed both checks with no errors. Existing synthetic fixtures omit these fields altogether. Thus arms can play different decks while being labelled as the same paired cell, or the entire population can use the wrong deck mapping, without detection. These checks are part of the requested spec §2 populations/cells and §5 records; consistency of numeric cell/seat labels alone does not establish that pairing.

   **Fix:** Independently implement the primary and guard own/opponent index mappings from spec §2. Read and verify the pinned guard-decks.json SHA, and require each game's decks to equal the scheduled decks (using the intended card-order convention). Update fixtures to carry real synthetic deck identities and add wrong-index/wrong-deck/per-arm mismatch regressions.

   **Wrong/correct reducer effect:** Can agree with a wrong reducer that accepts mislabelled or unpaired games and produces invalid contrasts. A correct reducer rejects these inventories; the current reducer already rejects wrong frozen decks.

6. **MAJOR — A known c* disagreement still produces admissions under the CLI-selected sequence.**

   **Location:** `reports/explore/k4s-confirm/verifier/verify_k4s.py:589`–592, `verify_k4s.py:859`, `verify_k4s.py:872`–876 and `verify_k4s.py:885`; `test_verify_k4s.py:880`–886 currently accepts the mismatch.

   **Scenario:** All games can record frozen c_star=0.8 while the invocation defaults to 0.9. Counting reports only c_star_mismatch, then emits status OK, admissions and a verifier_view with H4 included, returning flags-only exit 1. An in-memory tree reproduced zero errors and this single flag. The sequence changes actual admission, not just metadata: with all other upper bounds -1 and dref(0.9)=6, the correct c*=0.8 sequence admits A at 0.8/0.7/0.6, while the CLI-default c*=0.9 sequence stops at H4 and leaves those cells at B. The exit-1 flag signals a problem, but does not make the published decisions satisfy the frozen rule.

   **Fix:** A missing, inconsistent or CLI-disagreeing recorded c_star should be an input error and prevent decision/view generation. Bind the CLI input to the frozen c* record when available; deriving c* from exploration is not requested. For the c*=0.8 positive test, generate games recording 0.8, and add a separate mismatch-refusal test.

   **Wrong/correct reducer effect:** Can agree numerically with a wrong reducer that also uses 0.9 for a 0.8 study, or disagree with a correct reducer that applies frozen 0.8. The example changes admitted A to B; other values can wrongly introduce usable 0.9.

7. **MINOR — Rational comparison accepts forms that spec §6.7 explicitly prohibits.**

   **Location:** `reports/explore/k4s-confirm/verifier/verify_k4s.py:717`–721; `test_verify_k4s.py:705`–709; `VERIFIER-NOTES.md:24`–25 and `VERIFIER-NOTES.md:117`–119.

   **Scenario:** Spec §6.7 requires lowest terms and a positive denominator, but same_rational accepts [14,2] and [-7,-1] as equal to [7,1]. Rewriting every one of the 24 bounds in the hand-built view with doubled numerator/denominator and negative denominators still yielded 169/169 matches, zero mismatches. The test explicitly requires noncanonical acceptance, and notes O4 incorrectly state that the present spec lacks the canonical-form requirement.

   **Fix:** Compare integer pairs exactly, or first require positive denominator and gcd(abs(num),den)=1 before equality. Reject noncanonical zero as well. Reverse the existing noncanonical-acceptance test and update O4/notes.

   **Wrong/correct reducer effect:** Can approve a reducer output whose verifier_view violates the contract, although its rational numbers and gate decisions are numerically correct. This does not by itself turn a correct numeric CI into a wrong CI, and canonical correct reducer output remains accepted.

8. **MINOR — usable_cells uses multiset equality instead of the specified set equality.**

   **Location:** `reports/explore/k4s-confirm/verifier/verify_k4s.py:787`–790 and `VERIFIER-NOTES.md:27`.

   **Scenario:** The spec §6.7 expressly says usable_cells is compared as a set. Sorting and comparing the lists makes multiplicity matter: ["0.8","0.7"] and ["0.8","0.7","0.7"] represent the same set but mismatch. Order-only differences are correctly accepted. This is a comparison-contract issue, not an admission arithmetic defect.

   **Fix:** After enforcing a list of valid cell strings, compare sets as specified. If uniqueness is to be a separate producer-schema requirement, document that separately rather than silently substituting multiset comparison. Update notes O6, which also incorrectly says the present spec does not prescribe output order.

   **Wrong/correct reducer effect:** Can disagree with the correct set-comparison result for equal usable-cell sets. Duplicate-producing output may merit separate schema feedback, but no different usable set or numeric decision is demonstrated by this finding.

## Validation and evidence limits

Requested command:

```text
cd /mpac/sdicks02/repos/clasher-k4s-prep && nice -n 19 /mpac/sdicks02/venvs/t1-verifier/bin/python -B -m pytest -q -p no:cacheprovider reports/explore/k4s-confirm/verifier
```

Result: **95 passed in 3.96s**. These passing tests do not exercise findings 1–5; tests intentionally tolerate the mismatched c* and noncanonical rational cases in findings 6–7.

Additional checks used only in-memory synthetic records, generated integer matrices and mocked file reads. No additional test/code file was written. A full-size independent paired-difference oracle matched all four analyses at n=3000/900/600/300, both exact percentile endpoints, and the final default_rng(2026101170) state. It computed paired differences directly rather than bootstrapped per-arm totals; percentile endpoints were independently formed with weights 1/40 and 39/40 at order statistics 249/250 and 9749/9750. The original-id chain, rotation, bank/population caps, strict SUP, inclusive margins and validity are otherwise correctly implemented on valid inputs.

The allowed `receipts/reducer-verifier-crosscheck.json` reports 169/169 comparisons in admit-all, stop-at-H2 and suspended synthetic scenarios. Its verifier SHA matches this reviewed verifier. Its reducer SHA is 79985929946c980256ec2c1ab4ea50ed33af55feb1a7a4c23899e81f498ffc11; the inspected current reducer hashed to a0ac06b98ba37533d23983207a5125e30c1025e71867a5f60bf21ec4bf92a686. Therefore the receipt proves agreement with the recorded reducer revision, not every current reducer path. The receipt shows seven-step sequences and does not establish a c*=0.8 cross-check. Current reduce.py renumbers later step labels when dropping H4, whereas the verifier correctly retains H5/H6/H7 as required by the spec. That is an expected rejection of a wrong reducer view, not a verifier finding.

Reviewed source SHA-256 values:

- verify_k4s.py: `62d292423df5fedf3976f8de017c0ba9aab6dfbd4bfe70d43180ca52af70ffaf`
- test_verify_k4s.py: `3191a46c3639906db8c382a007b495be4354f4becb1d070133de72bee281d45a`
- VERIFIER-NOTES.md: `b1f7e18702f93adc1e35bf7928eb7ff741f39a3dde86b859f85c3e08abfc8043`
- K4S-SPEC.md: `d1bfb11c73f744ace219008632db54d38e0a5ddb4a80a3257af51c3e91f3e2ec`
- PREREG-K4S-DRAFT-r3.md: `9650972d362299d87f8b1084d450f9a2dbbad516a494e97da6ba33d60fb68b3a`

Release-readiness requires resolving finding 1 and the evidence-validation gaps in findings 2–6. Findings 7–8 complete the requested exact comparison contract; corresponding test and notes changes are necessary.
