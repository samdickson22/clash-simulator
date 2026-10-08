# Body-threshold scoring preparation

Recorded 2026-10-08 16:33 UTC, before formal fitting or validation outcomes.
This specifies the implemented scorer, not a selection seal or a change to the
frozen split/evaluation gates. No actual body threshold has been selected.

`validation_body_score_v4.py` first runs the existing formal fit/replay admission.
It requires all validation episodes, authenticated producer completion, all24
epoch checkpoints and exact replay/source hashes. It then opens only those
validation episodes' ordinary/rich body payloads, checks their receipt hashes,
and applies the same amendment03 cleaner used for training. Labels never enter
inference. Its output is explicitly unsealed and cannot authorize heldout access.

For each original source frame, the scorer uses the latest past native body
snapshot, at most five ticks old. A missing/stale snapshot excludes the entire
frame and counts its predictions as ignored. Future snapshots cannot supply
truth. A positive requires a resolved HP-based identity, coherent same-tick rich
join, visible status and explicitly finished deployment. All such bodies count,
including known identities absent from the fitted model vocabulary. Both owners
are included.

Uncertain objects mask the same seven-by-seven half-tile region used in training;
trusted positive centre cells are restored. Matching precedes masking unmatched
predictions, so a known body overlapping an uncertain region remains measurable.
Identity and native owner must agree. Assignment maximizes valid one-to-one
matches and then minimizes tile distance, using the historical v3 body evaluator's
three-tile radius (`scripts/evaluate_l1_perception.py:match_entities`). Invalid
edges are removed before assignment. Duplicate tracks remain false positives.
Out-of-arena predictions cannot escape the denominator through an edge mask.

Micro F1 pools frame-level counts across the complete validation population.
Phantom rate is unmatched unmasked predictions divided by scored predictions;
drop rate is unmatched truth divided by scored truth. Zero denominators are
reported as null. Also report ignored predictions and unscorable frames, so
visibility uncertainty cannot disappear from the report. These are source-frame
body diagnostics, not event availability, backdated-time error, or Mac latency.

Verification so far:31 pure synthetic cases and14 file-backed guard cases passed
on01 under the fleet wrapper. The file-backed fixtures mock producer/fit admission
and the cleaner only after testing early refusal; they do not certify a real fit.
Receipts: `v4-body-scorer-test-20261008-01r1` and
`v4-validation-body-score-test-20261008-01r1` under `l1/receipts/formal-20261008/`.

Still pending: the complete registered0.1–0.9 body-threshold replay grid,
authenticated F1/precision/higher-threshold selection, consistent event/checkpoint
selection with the chosen body configuration, final calibration verification,
and the complete selection seal. The current event-grid verifier still requires
one common body threshold across its216 cells; a body score alone does not satisfy
that requirement or replace the missing body-selection provenance.

2026-10-08 16:45 UTC: `body_selection_v4.py` now recomputes all nine authenticated
body cells for a specified epoch, validates constant truth/coverage/provenance,
and proposes the exact-F1/precision/higher-threshold winner.29 synthetic ranking
and file-backed proposal checks passed on01. This does not choose the epoch or
resolve consistency with the event grid; the proposal remains unsealed.

2026-10-08 17:26 UTC, before any formal T7 validation outcomes: select a body
threshold separately for every checkpoint using all nine registered body values
and a fixed event default0.5. Event thresholds do not alter body tracking; body
tracking does alter temporal birth inputs. Therefore each checkpoint's nine event
cells must use its selected body threshold. Rank global event threshold within
epoch, then epoch using the frozen opponent F1/precision/earlier-epoch rule, then
fit per-card event thresholds and calibrate the selected combined configuration.
This specifies ordering within the frozen validation-only selection, not new
gates, a split change, or permission to inspect heldout.

The event-grid input optionally supplies `body_grids`, a map of all24 epoch
strings to distinct body-grid JSON paths. The selector recomputes nine full body
replays per epoch before ranking the216 event cells. The verifier recomputes all
432 cells and verifies the original body score/manifest/proposal/completion pins.
A wrong per-epoch body setting, missing epoch, mixed fit, changed outcomes or
altered stored body evidence fails closed. Calibration carries authenticated body
selection only when this full chain passes; it still grants no selection seal.
Legacy common-body grids remain usable as unsealed intermediate diagnostics.
114 synthetic checks passed on01 (v4-joint-selection-test-20261008-01r1,exit0).
Real grids, calibration, final seal and heldout execution remain pending.
