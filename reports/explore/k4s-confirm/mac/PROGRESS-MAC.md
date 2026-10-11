# K4S Mac script (freeze checklist F-8 / r3 N2): progress

Worker: Opus 5.5 (1M), implementation sub-agent on 127x05, 2026-10-11. Design, code and offline tests only.
No Mac or ssh contact, no git commit, no game outcome or sealed result read. Everything written is under this
directory.

## Log
- Read r3 §1.4–1.5, §2.3–2.4, §4.5, §5.4, Q5; CONFORMANCE-r2 (N2, N3(b), F-8); RECHECK-r3 (R3, R5); TIERS r3 §6–§7;
  addendum r3 §B–§G; the e4v3 package (measure_tiers, tier_backend, replay_load, telemetry, receipts,
  classify_failure, corpus_contract, README, spec-pins); K4S-SPEC §1, §4, §8; T1 inventory `81f2483e`
  (corpora.json/publication.json); the linux05 Linux-smoke receipts (schema only).
- Wrote `k4s_logic.py` (pure logic), `k4s_backend.py` (K4S work unit on TIERS's TierBackend, read-only subclass),
  `measure_k4s.py` (CLI, K0 preconditions, K1–K7), `classify_k4s_failure.py` (classify + reduce),
  `build_manifest.py`, `K4S-MAC-MANIFEST.json`, `K4S-MAC-PROCEDURE.md` and `test_measure_k4s.py`.
- Tests: `nice -n 19 /mpac/sdicks02/venvs/t1-verifier/bin/python3 -m pytest -q reports/explore/k4s-confirm/mac`
  gives **73 passed**. The interpreter named in the assignment (`/mpac/sdicks02/repos/clasher/.venv/bin/python`)
  does not exist on 127x05, so the t1-verifier venv was used (Python 3.12.12, pytest 9.1.1).

## Open at the freeze
- The K4S kernel port (`k4s_kernel.files`) and the SD1 manifest SHA must be filled with
  `build_manifest.py --kernel KERNEL --kernel SCORER --freeze`.
- The END pooling script must emit `clasher.k4s.mac-fleet-reference.v1` (procedure §3), including integer deadline
  counts and the per-state no-deadline K4S result.
- Independent review of these files (they are not reviewed yet).
- **TIERS blocker found:** `E4V3/measure_tiers.py` uses `math.isfinite` in the Mac-only branch of `validate_counts`
  but never imports `math`. A Mac session would therefore end in a NameError, which classifies as a harness
  exception. K4S cannot fix this (the file is frozen); it needs a TIERS-side decision.
