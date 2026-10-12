# Mac registration inputs builder: progress

The builder is a worker for coordinator thread 0523ae6f, assigned at 22:25Z on 2026-10-11. It runs on 127x05 as T1's corpus-owner delegate; T1 keeps merge and seal authority. Design: `reports/strategy_council_20260928/live-loop/v4/MAC-REGISTRATION-INPUTS-PROPOSAL-20261011.md`. Record: `PREREG-SEARCH-TIERS-AMENDMENT-4-20261011.{md,json}`.

Work directory on 05: `/mpac/sdicks02/jobs/clasher/mac-registration-20261011/`. It holds the pinned e4v3 extraction `e4v3-<origin/main commit>`. Later it will hold the captures and outputs. None of that is committed.

## Phase 1 (05 only; no 03)

- **22:25Z** Assignment read. I read the proposal and the frozen e4v3/T1 code (corpus, contract, converter, tier_backend, prepare_bundle, measure_tiers, fleet_pool).
- **22:30–22:44Z** Wrote `selection.py`, `macreg_io.py`, `build_sets.py`, `assemble_states.py`, `student_reference.py`, `memory_check.py`, `seal_receipt.py`, `stage_nocopy.py` and the tests.
  - Found that T1 reuses seeds 3–10 across tiers, so every game key is (tier, seed). This is now in the code, the tests and the A4 clarifications.
  - 30 tests pass on Python 3.8.10 and on 3.12.12 (torch 2.10.0+cpu). Receipts are in `receipts/unit-tests*.{json,log}`.
- **22:31Z ruling picked up from COORDINATOR.md:** no-copy Mac staging is added to the A4 builder's scope. `stage_nocopy.py` lives outside e4v3, so the END↔Mac pins are unchanged.
- **22:44Z** Drafted the A4 note and generated the JSON (`make_amendment_record.py`). Next: Sol review.

- **22:46Z** Sol round 1 requested (`macreg-a4-sol-review-r1`). Meanwhile:
  - preflight on 05: 300/300 real K0c published rows reproduce the committed END canonical digests under my bootstrap;
  - added `fetch_captures.sh` and `verify_captures.py` for Phase 2.
- **22:30:53Z coordinator scope message (no-copy Mac staging; first labelled 22:33Z, corrected by the coordinator)**, handled at 22:48–22:51Z:
  - `prepare_bundle.py` a1c59fa3 is in END `measurement_files`, so it is not edited;
  - it refuses pre-placed files, so a pre-staging step is impossible;
  - `stage_nocopy.py` runs the unmodified frozen module with `copy_file` substituted for the three fixture files (clone → hard link → space-checked copy, SHA-verified);
  - an integration test shows `tiers-pins.json` is byte-identical with and without it;
  - no re-pins.
- **22:52Z Sol round 1: REJECT** (2 blocking, 4 major, 1 minor). Record: `reviews/SOL-REVIEW-A4-r1.md`. All findings fixed by 22:59Z:
  - single bootstrap, with a real-runtime smoke that passes;
  - direct `clonefile`;
  - receipt chain plus artifact re-hash;
  - memory workload bound;
  - END-A3 runtime copy `runtime-a3`, verified against bd9804c3 (3,785 files), plus the native SHA;
  - the B.4 uncovered case now stops;
  - empty games handled.

  38/38 tests pass on 3.8 and on 3.12.
- **23:00Z** Sol round 2 requested (`macreg-a4-sol-review-r2`).
- **23:03Z Sol round 2: REJECT.**
  - All 7 round-1 findings are resolved.
  - Finding 8 (blocking): the runtime `copy_file` substitution needs an explicit coordinator ruling. I reported the stop at 23:03Z.
  - Finding 9 (minor): text fix, done.
- **23:04Z coordinator ruling** (COORDINATOR `684195b3`, recorded 23:04:25Z; git time 23:04:29Z; first labelled 23:07Z, corrected by the coordinator): `stage_nocopy.py` APPROVED under 6 conditions.
  - Implemented the read-only protection (condition 3) and `--verify-bundle` (condition 5).
  - The ruling is recorded in the A4 md and json.
  - 38/38 tests pass on both Pythons.
- **About 23:06Z** Sol round 3 requested on the whole amendment (`macreg-a4-sol-review-r3`). One round is held in reserve.
- **23:10Z Sol round 3: APPROVE_WITH_CONDITIONS.** The single condition was finding 10 (minor): the "every stage" runtime-check wording. Fixed at 23:11Z.
- **23:14Z Sol round 4 (confirmation): APPROVE.** Committing A4 and the builder through a temp index.

- **23:15Z** Committed and pushed `94df513d` (32 files, temp index on origin/main, secret scan clean).
- **Coordinator: A4 ADOPTED** (COORDINATOR `16d431b4`).

- **23:19–23:24Z Erratum E1 (test only).** The Mac operator (`27faac2c`, `44040cd3`) found that `test_stage_nocopy.py` assumed a hard-link inode, while on Darwin the helper correctly clones.
  - The test now asserts the placement method recorded in the receipt.
  - Test SHA `f75cd3a3` → `b540df82`. The helper `96abd847` is unchanged.
  - Recorded in the A4 md and json. Sol diff check: APPROVE (`reviews/SOL-REVIEW-A4-E1.md`).

- **04:45Z Oct 12: Erratum E2.** TIERS A5 was adopted (COORDINATOR `46ab6923`, main `8799a0d6`), changing `fleet_validity.py` `94d0e7f2` → `0775b704`.
  - The `stage_nocopy.py` pin was updated (one line). Helper `96abd847` → `166a1636`.
  - 38/38 tests pass against the A5 e4v3 extraction `e4v3-a5-8799a0d6`.
  - Removed a duplicated PROGRESS block, caused by a repeated edit on 10-11.
  - **Open for Phase 3:** the builder runtime `runtime-a3` and `verify_runtime` bind END-A3 (`bd9804c3`, holding `fleet_validity` `94d0e7f2`). To build on A5 bytes, the binding must move to the END-A5 manifest once T1 commits it. That needs a separate narrow change, raised with the coordinator.

## Phase 2 / Phase 3

Waiting for an explicit 03 read-window declaration from the coordinator (expected at about 08:47Z Oct 12, when K4S 03's apt-daily timer stops its phase). The coordinator will wake this thread with `t3_thread_send`.
- No host contact and no Phase 3 before then.
- **On wake:**
  1. Check `date -u`.
  2. Run `fetch_captures.sh` (one session).
  3. Run `verify_captures.py`.
  4. Post "released" to the coordinator immediately.
  5. Run `run_phase3.sh build`, then `reference`, then `memory`, detached with setsid nohup.
  6. Start the independent Haiku 5.5 reproduction (max effort, without the selection code).
  7. Run the cross-check and the seal once T1's pooled END S forwards exist.
