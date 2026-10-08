# Report rendering implementation addendum

2026-10-08, before v2 training or any v2 held-out scoring. The original PREREG,
executable manifest, store, roles, extractor, T4/T5 code and scoring functions
remain unchanged. This adds only `imitation/t11/report.py`, a standard-library
renderer of completed, sealed artifacts. It performs no model inference,
calibration, bootstrap or gate calculation. Existing gate booleans, estimates,
intervals and N/A labels are copied without changing their values. Decimal
display uses nine significant digits; authoritative JSON retains full values.
OOD-minus-eval differences are descriptive subtraction, as already registered.

The renderer requires both completed runs, all four analysis JSON files and
their statistics completion receipts, matching selected checkpoint/log hashes,
the registered dev-only primary, and the unchanged published v1 report hash.
It reports both seeds and both cohorts, dev curves, recorded CPU/wall time,
loader-inclusive throughput, selected hashes, temperatures, all metric means
and intervals, all gate details, missing-card counts and descriptive OOD gaps.
Per-card/arena/flag tables and calibration bins remain in the linked, hashed
analysis artifacts. Report writing is exclusive; it will not overwrite a
published file. Training/checkpoint inputs and rendering run on compute hosts.

Validation used only synthetic JSON and dummy checkpoint bytes on127x01.
It verifies a failing primary remains failing despite a passing secondary,
empty-P16 N/A is preserved, paired values/CIs are unchanged, descriptive gaps
are correct, and a changed v1 report hash is rejected. Fixtures are retained.
This is reporting completion, not a scientific amendment or permission to
score held-out data. The release embargo and once-only scoring are unchanged.

The separately frozen `report-renderer-freeze.json` binds renderer, validation
code, synthetic PASS receipt and this addendum, alongside the original PREREG
and executable-manifest hashes. No original frozen file is replaced.
