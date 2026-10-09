# Confirmation review: Amendment 12 (measured-dominance selection), 2026-10-09

The independent reviewer worked read-only. Files were read on 127x05. Tests ran on 127x01 under `nice -n 19` with `-B`, with scratch only in `/tmp/sdicks02-a12cr`, which was removed afterwards. The only file written in the repo is this review. No body seal, bound, measurement, selection or heldout data was computed or opened.

## Inputs (SHA256 recomputed by the reviewer)

| File | SHA256 | Status |
|---|---|---|
| `amendments/12-measured-dominance-20261009.md` | `cc2357df357b889a306cfc3d472048aae7234374e3463c7137cdef231ace6bf2` | matches the claim |
| `amendments/12-measured-dominance-draft-pins.json` | `60f0cb4eddd6885218bd2de16d54f73547d6cf542d241c755c9181f7490968c5` | matches the claim |
| `amendments/.12-draft-9e575ba1.reconstructed.md` | `9e575ba1bcd67e8069a022d952cf873b957ea80a410f30c1e1376422b608dc23` | equals the reviewed draft, so the reconstruction is exact |
| `amendments/.12-draft-1bde5c55.preserved.md` | `1bde5c55…2867` | — |
| `reviews/AMENDMENT-12-DELTA-REVIEW-20261009.md` | `5b8a9ed5…97d4` | equals HEAD and the pins `delta_review` |
| `CLOCK-OPTIONS.md` | `5cb308d6ede472a4af51345c81bae8cc622ac8172cc3aecfb6fd6ae62f335d62` | — |

All 20 `source_sha256` pins match the files on disk. The `d4_test_receipt_sha256` matches the receipt. The reviewer's own scripts were not taken from the owner's receipt `12-delta-mechanical-check.json`.

## 1. Mechanical check

- **The 01:32 edits.** A line diff of reconstructed 9e575ba1 → 1bde5c55 contains exactly changelog (a): one added table row plus a blank line, and one replaced sentence at the end of the test paragraph. Nothing else changed.
- **Rebuilding the new draft.** Starting from 1bde5c55, the reviewer applied D1–D5 programmatically. Each quotation was extracted from delta review §A and §C rather than from the owner's text. D2 replaces the "The30-cell Tier1 budget" paragraph. D3 replaces "Additional coordinator restriction". D1 replaces the heading, the quotation and the issue paragraph, and adds the supersession line. D4 goes after "At closure…". D5 goes at the top of "Required review wording". The reviewer then swapped the single N1 pin `eea1759b…64bf4` → `63e87b15…34ed`.
  - Result: `re.sub(r'\s','',rebuilt) == re.sub(r'\s','',cc2357df)` is **TRUE**.
  - D1–D5, the D1 supersession line and the D1 heading each occur byte for byte in the new draft.
  - Nothing outside these changes is unlisted.
- **Pins JSON against the reviewed table.**
  - The 16 reviewed pins are unchanged.
  - `test_measured_dominance_v4.py` changed for N1, and nothing else changed among the reviewed pins.
  - Added: `test_record_capture_admission_v4.py` (change a1), `dominance_file_verifier_v4.py`, `test_dominance_file_verifier_v4.py`, `delta_review` (D5), the D4 receipt and PYTHONPATH SHA.
  - Scalar policy fields are unchanged: tier2 false, 127x08, driver and UUID, 05:00Z, all seals null, heldout false.
- **CLOCK-OPTIONS (D6 and N4).** Compared with the owner's snapshot `.12-clock-options-before-delta.md` (a7666c6c), the whitespace-normalized diff is only the label "WITHDRAWN (engineering history): " on the measurement heading, plus the new heading "### WITHDRAWN (engineering history): A/B cost projections". No number changed. That baseline is the owner's snapshot; the delta review did not pin a CLOCK-OPTIONS SHA.

## 2. Changelog (a): substance

- **(a1) Admission-test pin row.** This adds a pin and weakens nothing. The pinned `record_capture_admission_v4.py` is the reviewed byte-identical file. Its test `test_clock_files_never_opened` passes, as recorded below.
- **(a2) Report of the 6 admission tests and 4 decoder-view tests, replacing "orchestration and tests remain required" with "still require integration verification".**
  - The new wording is softer in isolation. It is not a weakening, because three things still require full file-backed admission and orchestration to be finalized, tested and pinned before execution: the unchanged freeze-blocker paragraph (last paragraph of the draft), D5, and delta review §E.
  - It opens no path for clocks or modeled availability.
  - It does not change seal-before-bound ordering, the 95/95 or 90/90 gates, or `noise-measured.json`.
  - It gives no heldout access.
  - It does not conflict with RC1–RC8 or D1–D5.

## 3. D4 implementation and tests

All 30 tests pass on 127x01 with clasher-gpu, Python 3.12: 11 dominance, 9 D4 file-verifier, 4 clock-free and 6 admission. Every input file SHA matches the pins.

**`verify_d4` enforces each D4 condition in code.**

- **(a) Seal binding.**
  - The file SHA must equal the `body_seal_sha256` argument and the bound's `body_seal_sha256`.
  - The seal must have the complete 24-epoch schema.
  - The bound's `body_threshold` must equal the seal's b*(e).
  - Any failure raises VoidRecord.
- **(b) Fidelity.**
  - The multisets keyed by (episode, source_seq, card, side), for side 0 card-play, are recomputed from the records (`event_predictions`) and from the measured outputs (`completed_predictions`), and must be equal as Counters.
  - The two truth files must be byte-identical, and the bound's `truth_rows_sha256` must equal the file SHA.
  - The mapping source must be pinned.
  - On failure, the suspension receipt is written with `open('x')`, then the notifier is called, then RecordFidelityFailure is raised. A notifier exception propagates. A notifier that is not callable aborts at entry.
- **(c) Availability.**
  - The completion `timestamp_ms` must equal the frame stamp, with `available ≥ stamp` exactly, finite, and no epsilon. The check runs per frame and again per prediction.
  - The production stamp of each recomputed bound must equal the frame stamp.
  - The bound counts are recomputed from those stamps and the pinned truth.
  - Failures raise VoidRecord. The verifier never deletes inputs, so the record is retained.

**Mutation probes.** Each of these was caught by at least one test:

- a 1e-6 tolerance in (c);
- comparing (b) by count only;
- skipping the seal hash or the body-threshold check;
- dropping the truth byte comparison;
- routing (b) to void instead of suspension;
- swallowing notifier errors;
- not writing the suspension file.

Two mutants survived: removing the check that the completion `timestamp_ms` equals the frame stamp, and removing the production-stamp check. Both are defence in depth; (c) itself stays enforced against the frame times.

**N1.** `test_equal_metrics_worse_tiebreak_eliminated` is meaningful. Cells (2,.9) and (1,.8) have the same bound (F1, precision) as the measured incumbent (1,.9). They are eliminated by the tie-break, and the state closes. Together with `test_ties_earlier_epoch_higher_threshold`, which covers the better tie-break staying pending, this covers both directions. `measured_dominance_v4.py` is unchanged.

**N2.**

- The receipt pins all 17 snapshot files. The 16 present locally match the disk; `pin_test_runner.py` is not in the repo.
- The receipt lists 380 PYTHONPATH files. `pythonpath_tree_sha256` reproduces as the SHA256 of the listing as compact JSON with sorted keys.
- `l1_v4.py` in that tree equals the pin.
- Six `clasher/rl/*` files in that snapshot differ from the current repo `src`. None is imported by these tests.

## Conditions carried forward (non-blocking; they bind the orchestration review, not this freeze)

1. `verify_d4` needs measured outputs, so it checks D4(a) only on bounds of measured cells. The persisted orchestration must apply D4(a) to all 216 bound records before the first `next_step`.
2. Neither `next_step` nor `verify_certificate` consults suspension receipts yet. The controller must refuse elimination and selection while any `record-fidelity-suspension` exists. A VoidRecord must be logged durably as void-but-retained.
3. Tests to add:
   - completion `timestamp_ms` ≠ frame stamp;
   - production-stamp mismatch;
   - a notifier that is not callable.

   Also fsync the suspension receipt, and pin the `spells` input. A wrong `spells` value only causes a spurious, conservative suspension.
4. Editorial items that need no change to the frozen bytes:
   - The "Ten…/Total 20" paragraph describes the pre-N1 15r1 runs. The current evidence is the D4 receipt: 20 tests, 11+9.
   - The blank line at draft line 167 splits the pin table.
   - The two verifier files are pinned only in the JSON, which governs.
   - CLOCK-OPTIONS lines 45–73 still fuse some words; this is outside D6's scope.
5. Do not edit the draft or the pins to change "DRAFT … awaiting" or `status`. Record the freeze in a separate coordinator record that cites these two SHAs. Any byte change requires re-confirmation.

**FREEZE APPROVED at draft cc2357df357b889a306cfc3d472048aae7234374e3463c7137cdef231ace6bf2 / pins 60f0cb4eddd6885218bd2de16d54f73547d6cf542d241c755c9181f7490968c5**
