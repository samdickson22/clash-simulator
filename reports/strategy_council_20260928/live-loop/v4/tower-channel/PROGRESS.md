# Public tower channel progress

Task owner: worker for coordinator 0523ae6f. Work began 2026-10-09 UTC.

## Boundaries

- Edit only this report directory, new tower channel/tests, and necessary live adapters/model contracts.
- Training-only data on 127x03; nice 10, CPU only, at most 24 processes. No formal validation or sealed payload access. Existing jobs untouched.
- Frozen split SHA256: `3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258` (`../split.json`).
- Source pixels/cache read-only: 127x03 `clasher-v4-cpu/matches`, `clasher-v4-cache`. Generated data stays in our ignored `runtime/` directory, never committed.
- Existing checkout has many unrelated modifications; stage explicit owned files only. Scan staged diff before commit; push main with rebase as necessary.

## Read / decisions

- Read tower_model.py, perception_adapter.py and public_root.py first; then diagnostic code/report, l1 PREREG, replay, cleaner and cache code.
- Native diagnostic truth: ordinary `hp`, `max_hp`, `owner`, ground anchor joined coherently to same-tick rich `hp`, `maxHp`, `visibilityState`, `deployRemainingMs`. Absent truth is unknown, never destroyed.
- Capture calibration affine ground anchors found in historical calibration receipt, SHA256 `af06e029c50c3e2932f829a8891d6f6bdca654912d6beff512ab5864cc8c60d8`.
- Native/public ABI: opponent owner 0 at y=3/6.5, own owner 1 at y=29/25.5. Existing model SLOTS already preserves this order despite TileGrid BLUE/RED naming.
- Plan: fixed sprite/HP crops, small CPU visual templates/rules, typed per-frame observations, persistent model destruction latch only on positive visual evidence. Preserve raw body output and existing strict public-frame serialization contract.

## Next

1. Pin training-only fit/dev episode manifest before pixels.
2. Extract training crops on 03 and inspect fit-only sprite/HP signals.
3. Implement and freeze recognizer, evaluate disjoint dev matches, timing and tests.
4. REPORT, staged secret scan, commit and push owned files only.

## 2026-10-09 implementation / fitting

- Pinned 24 fit + 8 dev training matches by SHA256 episode ranking, before extraction (`study-manifest.json`). No validation payloads opened.
- Detached one-process fit crop extraction on 03: initial PID 857690; corrected crop extraction PID 862630. Own fitting PID 876200 was stopped by exact PID after finding repeated NPZ decompression; corrected fitter PID 884411. Existing jobs untouched.
- Current crops: calibrated 96x150 sprite; 110x80 HP panel with side-specific offsets. Opponent HUD remains sanitized.
- Manually annotated 15 fit-only rubble crops: collapsed stone and crossed broken timbers. No destroyed King examples; King destruction must remain unmeasured/abstaining with current artifact, never inferred from absence.
- Implemented typed channel, optional backwards-compatible public-frame field, adapter, model destruction latch and six safety/transport/identity tests. Default runtime templates still fitting.
- Generated crops/sheets are only in ignored `runtime/`; no images staged.

## 2026-10-09 dev / verification complete

- Frozen recognizer source `84abdf95dd72e1f9b77f2849763026c973735243c96d9337930b8ef4cacb6410`, model `9d7f21fb7ee3ab53774056208e352a59d3f5fa5bcb42ebfe2309449bd8d7f014`, before opening dev pixels. No post-dev tuning.
- Detached dev extraction PID 893985, replay PID 897033: complete, 8 matches / 11,019 frames. Mean 1.376 ms/frame, p95 1.556, p99 1.773. False destroyed 0/1,844 eligible alive; alive 1,813/1,844. Numbers 499/500 exact; 287/287 accepted bars within five percentage points.
- Visual audit of 48 independently labelled dev crops: all matched (46 upright alive, one rubble destroyed, one obscured unknown). Native missing truth remains masked. No destroyed King support and no King HP reading; report explicitly leaves these coverage blockers open.
- Independent join audit of all 32 study matches found no repeated rich ticks or duplicate ordinary tower candidates, so diagnostic-style truth joins agree.
- Final regression on isolated snapshot on 03: **75 passed, 6 subtests passed, 34.19s**, including eight new tests. Five native S6 parity tests were excluded. Earlier environment failures were resolved by isolated OpenCV/SciPy dependencies, not source changes. Final PID 929554 exited.
- Channel now activates the persistent packet model automatically; legacy producers without the channel keep existing behavior. Visible integer HP uses public tournament stat normalization; bar fraction is fallback. Numerical model ~496 KiB is packaged and hashed in runtime provenance.
- REPORT.md and small provenance/dev/test receipts are complete or being finalized. Next: stage only owned files, secret scan, commit, push main; preserve all unrelated dirty files.

## Final handoff

Implementation, REPORT and receipts are complete; all owned detached compute has exited. No further fitting or dev tuning is authorized by this study. Publication uses only this directory, the new test/channel/artifact and the necessary live integration/contract/package files; staged credential scan is required immediately before commit. The published commit can be located with `git log -- reports/strategy_council_20260928/live-loop/v4/tower-channel/REPORT.md` and compared with `origin/main`.

Remaining coverage question: training-only King rubble and active King HP examples, and a larger independent princess destruction/occlusion audit. Current conservative channel is useful, but these gaps remain L2 blockers. No validation/heldout access, owner jobs, formal files or unrelated working changes were needed.

## Round 2 — in progress

- Round 1 and source read. Fresh membership will use the original SHA ranking, exclude all 32 round-1 matches from dev, take eight fresh dev matches and augment the original 24 fit with the next 24 fresh matches.
- Native ordinary snapshots are complete fenced collections; rich snapshots are sparser. Derive permanent princess disappearance only after a positive witness and at least two continuing snapshots with both Kings alive; mask terminal teardown and capture-start absence. Death tick is interval-censored between the last positive and first absent snapshots.
- Native HUD and rich player fields inspected on fit data have no crown/score fields. Collector receipt records an explicit native `terminal.ended` and tick; these are scoring-only inputs.
- Public pixel runtime has no demonstrated result-screen producer; packet construction accepts a terminal flag. Checking how to connect that public flag while retaining King rubble abstention.
- All extraction and fitting will run detached on 127x03, nice 10, eight CPU workers with single-thread libraries. Formal/perception-owner files remain read-only.

## Round 2 — frozen dev completed

- Pinned manifest SHA256 `6f74fdf6cf189c7f268dc9d1f73090eb7724c306d3cf68b858df2807d90bffae`: 48 fit, eight fresh dev. Eight-worker extraction complete. Twenty fit disappearance events supplied 1,575 stable rubble samples; no manual rubble labels needed.
- Freeze at 2026-10-09T02:22:02Z pins recognizer `6070598b…`, candidate artifact `8946523c…`, manifest, truth and scoring source before any fresh-dev pixel decoding. Four-worker CPU replay completed 22,059 frames.
- Seven of seven dev princess events confirmed; persistent destroyed recall 13,212/13,581 (97.28%); raw current-frame recall 8,906/13,581 (65.58%). Mean interval-censored confirmation 2.629–2.786s. False destruction 0/74,179 living princess frames and zero affected matches out of eight. One-sided 95% frame bound 0.00404%; match-level bound 31.23% acknowledges correlation/small match count.
- New opponent numbers fail predeclared dev gate: 247/250 exact (98.8%); disabled with no source/template/threshold tuning. Own-King numbers pass: 136/136 exact, 30.43% eligible coverage. Opponent King numbers stay absent outside sanitized arena. Original own-princess reader: 673/673 exact.
- King activation: 40,392/40,393 accepted exact (99.9975%), 92.04% coverage. Native wake-rule labels use princess fall or positive King HP loss. A dev King disappears exactly at native `terminal.ended=True` tick 4554; there is no continuing King-rubble truth and no stored crown count.
- Added a typed public result input, connected adapter → packet terminal → planner no-op. Three crowns establish only the opposing King death; two-crown/time results end planning without inventing King death. Result terminal state persists through later frames and resets with episode. Existing live source has no result-screen producer: upstream public capture/runtime owner must supply that observation. No formal runtime/perception-owner source edits.
- Regression tests in progress on the prior isolated round-1 snapshot plus owned source changes. Initial synthetic fixtures were corrected for crop padding and distinct OCR glyphs; no dev-informed recognizer tuning occurred. Candidate six-slot timing 2.223ms/frame; final opponent-disabled artifact timing still to measure.

## Round 2 — verification complete / publication

- Final regression: **85 tests passed, six subtests passed, 28.73s**, including all 75 round-1 tests plus ten new tests. Same five unrelated native S6 parity tests excluded. Isolated snapshot excludes concurrent runtime/perception worker edits.
- Final deployed artifact (`09850226…`, 1.10 MiB) timing: 551 fit-only reconstructed six-slot frames, mean **1.474ms**, p95 **1.716ms**, p99 **1.753ms**. Candidate full-dev replay timing remains separately reported at 2.223ms.
- Post-scoring corrected HP coverage denominators by recomputing family eligibility from frozen native labels: unread opponent-King observations are excluded from own-princess coverage. No predictions, model, thresholds or HP acceptance policy changed.
- Coordinator instruction received: never edit selection.py/runtime.py; stage only owned hunks with `git add -p` in shared perception_adapter.py, decision.py and public_root.py. No changes to worker-owned files are needed. No checkout/stash or broad staging used.
- All task compute has completed. REPORT and small reproducibility receipts are ready. Publication uses explicit tower/report files and owned shared hunks only. Staged secret scan and whitespace checks passed. Exact publication commit is available with `git log -- tower-channel/REPORT.md` from the v4 directory. Open issue: public result-screen producer must be supplied by the capture/runtime owner; opponent numbers remain disabled after failing the fresh-dev gate.
