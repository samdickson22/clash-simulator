# Amendment 12 changelog since reviewed 9e575ba1

The reviewed draft was reconstructed by reversing the two recorded 01:32 edits. File `.12-draft-9e575ba1.reconstructed.md` hashes **exactly** to `9e575ba1bcd67e8069a022d952cf873b957ea80a410f30c1e1376422b608dc23`. The 01:32 draft and pins are preserved as `.12-draft-1bde5c55.preserved.md` and `.12-pins-3e7f1504.preserved.json`. This reconstruction is verified, not an assumed historical copy.

## (a) 01:32 non-whitespace edits

1. Added the `test_record_capture_admission_v4.py` source/SHA row (`65ef6c73b4e0476b468f8f5170d9a2ac5460c999613cab033fe47a97251426eb`) to the draft table. Reason: record the new file-backed non-clock admission tests. An extra blank line accompanied the row.
2. Replaced “Their file-backed orchestration and tests remain required before real execution.” with the paragraph reporting six admission tests, four decoder-view tests and 20 total preparation tests, while retaining the full integration requirement. Reason: those tests had completed successfully. Exact inserted text is preserved in the 1bde5c55 version and the diff below.

These were the only non-whitespace draft edits at 01:32. The accompanying pins JSON added that test SHA and refreshed its UTC; no scientific input or production artifact changed.

## (b) Required delta insertions and replacements

- D1: replaced the disclosure heading, quotation and issue paragraph with the corrected full-selection-key disclosure and explicit supersession line, verbatim.
- D2: replaced the entire 30-cell paragraph with the reporting-checkpoint/continued-measurement paragraph, verbatim.
- D3: replaced the unresolved 1975100708 paragraph with the Tier 2-disabled resolution, verbatim.
- D4: inserted the bound-validity preconditions after the pure-verifier paragraph, verbatim.
- D5: inserted normative adoption/governance text, verbatim, and added top-level `delta_review` to the pins JSON.
- Required step 3/N1 pin maintenance: updated the existing `test_measured_dominance_v4.py` table SHA after adding the explicit worse-tie-break elimination test. This is the only further non-whitespace draft change beyond (a) and D1–D5. Its exact old/new hash is listed below; implementation and test pins are in the companion JSON.

D6 changes elsewhere in the draft are whitespace only. CLOCK-OPTIONS originally numbered lines 37–43 received spacing repair only; N4 adds “WITHDRAWN (engineering history)” to the measurement-table heading and adds that heading above the A/B projection table. No historical numeric cost or measured value was changed.

## Code and evidence for required step 3

New `dominance_file_verifier_v4.py` reads externally pinned body seal, actual decoder records, frame times, measured output/completion files and both truth files. It enforces seal embedding/body choice; recomputes exact opponent prediction multisets; compares truth bytes and mapping-source SHA; requires availability >= production with no tolerance; and recomputes the bound counts from those production stamps and truth. A fidelity failure writes a durable elimination-suspension receipt and invokes a required coordinator-notification callback; notification failure also aborts. Inputs are retained. This is the D4 file-check layer, not the complete selection controller: producer admission, controlled-host telemetry and final selection/seal integration remain explicit blockers. No real bound or measurement was executed.

Twenty tests pass on 15: 11 dominance tests (including N1), 9 D4 file tests. The receipt pins every test/helper file and the recursively enumerated PYTHONPATH tree before and after the run, excluding documented volatile Python bytecode. `receipts/inference-sharing-20261008/dominance-d4-tests-15r1.json` holds the full pins; the exit and log are adjacent.

## Mechanical comparison

A direct `re.sub(r'\s','', old) == re.sub(r'\s','', new)` is **false**, as expected because (a), D1–D5 and the required N1 test-pin update change non-whitespace text. After applying exactly those enumerated changes to the reconstructed reviewed draft, the same comparison is **true**. D1–D5 verbatim checks pass. The machine receipt is `12-delta-mechanical-check.json`. This supports the requested narrow confirmation review; it is not a freeze.

Old N1 test pin: `eea1759b4a753366db6877dfe070ef6c42377943e85cf8d72c19919ce9e64bf4`. New N1 test pin: `63e87b1535332a2f2fe6dd8d04a122f2991b230b75a0af6fdac05ffedf8c34ed`.

### Exact 01:32 draft diff

```diff
--- 9e575ba1
+++ 1bde5c55
@@ -161,6 +161,8 @@
 | clock_free_body_ranking_v4.py | `3967be357835a6b0fbe5a2b9b7c301ba9594b2061aba124fc8ca9cdf704d374d` |
 | test_clock_free_records_v4.py | `9e8e996eb13b2f3e85f925c7b62f01209231330327e6aeee36a025a696ecaed9` |
 
-Ten new purebound/selector/verifier synthetic tests PASS15 (`v4-measured-dominance-tests-20261009-15r1`,exit0): prematurepredictions, exhaustivemaximumcardinality, measurededge-subsetproperty, rejectedclockfields, side/kindisolation, exacttie/earlierepoch, termination,30-cellnonclosure, counts/boundtampering, missing/duplicatecells and reorderedhistory. No real bound was computed. Separate record-only admission and body scorer modules are prepared; they skip completion files entirely and compute only source-frame body metrics. Their file-backed orchestration and tests remain required before real execution.
+| test_record_capture_admission_v4.py | `65ef6c73b4e0476b468f8f5170d9a2ac5460c999613cab033fe47a97251426eb` |
+
+Ten new purebound/selector/verifier synthetic tests PASS15 (`v4-measured-dominance-tests-20261009-15r1`,exit0): prematurepredictions, exhaustivemaximumcardinality, measurededge-subsetproperty, rejectedclockfields, side/kindisolation, exacttie/earlierepoch, termination,30-cellnonclosure, counts/boundtampering, missing/duplicatecells and reorderedhistory. No real bound was computed. Separate record-only admission and body scorer modules are prepared; they skip completion files entirely and compute only source-frame body metrics. Six file-backed admission tests PASS15 (record-admission-tests-15r1): completion journals deliberately absent; changed/missing decoder files, wrong completion pin, changed validation split and wrong epoch assignment are rejected. Four clock-free decoder-view tests also PASS15. Total20 new preparation tests pass. Full body-scoring/seal and bound/measurement orchestration still require integration verification before real execution.
 
 Draft freeze blockers: coordinator/reviewer delta approval including disclosure inequality and30-cell operatinginterpretation; file-backed clock-freebody/nonclockadmission and persistedbound/selector/seal orchestration must be finalized, tested and appended tosourcepins before their execution; intermediatebodyseal doesnotyetexist; controlled08celllauncher/telemetry lifecycle must be implemented/tested/pinned before05measurement. The puretools and thisdraft do not bypass those requirements. Tier2 remains disabled and needs separate reviewedimplementation and test-role resolution if everconsidered. No decidingmeasurement, winner, finalseal or heldoutresult exists.
```
