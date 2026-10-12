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
- **E2 accepted** by the coordinator (COORDINATOR `8bbb0908`); the Sol check was waived.
- **06:18–06:21Z Erratum E3: the builder's runtime binding moves to A5.**
  - `verify_runtime` binds END-A3 `bd9804c3` plus T1's committed END-A5 inventory diff `900bae16`, in which only `fleet_validity` changes, to `0775b704`.
  - `runtime-a5` was built and verified (3,785 + 18 files equal; native `44874fd6`).
  - The real smoke on `runtime-a5` passes. 40/40 tests pass on both Pythons.
  - Phase 3 now runs on `runtime-a5`.

## Phase 2 / Phase 3

- **08:48Z Oct 12: coordinator Phase 2 GO** (03 quiet).
  - One read-only ssh session 05 → 03 (no ControlMaster), 08:49:03–08:51:29Z.
  - Ran a remote sha256sum (the "before" check), then a tar stream of exactly the 32 pinned captures. Remote side ran at nice 19 on core 63, with a 32 MiB/s local cap; 4,891,842,873 bytes.
  - All 32 SHAs equal `corpora.json`, both before (on 03) and after (on 05). Nothing was written on 03, and `games/` was never touched.
  - Receipt commit `fa8e700a`. "released" posted at 08:51:50Z.
- **Coordinator note:** `fetch_captures_stream.sh` was new and unreviewed; it was accepted after the fact. Rule from now on: any new script that touches a host is reviewed before it runs.
- **Phase 3 GO** (05 only, `runtime-a5`, nice 19, `PYTHONDONTWRITEBYTECODE=1`).
  - 08:52Z: `run_phase3.sh build` launched detached (setsid).
  - 08:53Z: independent Haiku 5.5 (max effort) reproduction delegated (`macreg-phase3-repro-haiku-r1`, core 62, own code, no access to the builder's code or outputs).
- **Selection (08:52–08:57Z):**
  - 4,242 pool rows, 0 invalid, lineage 1,200/1,200, counts and health equal.
  - 9 packet games; the last (K0c-6) is truncated at 43 rows.
  - Agreement: 1,931 + fill 69. Schedule last offset 1,459.5 s.
- **Assembly:** 2,125 rows; the END prefix equals `c09142b9`. Fingerprint **`0de69958…`**.
- **Conversion:** PASS at 09:03:35Z, `--expect-fingerprint`, `source_verified`; maxrss 20.2 GiB.
- **Haiku reproduction:** identical on every output (packets, schedule, agreement, fixture ids, 800 extra digests, quotas, fingerprint).
- **Student reference:** 2,000 states (`7a90fa7a`), finished about 09:25Z.
  - My wait loop's `pgrep -f` matched itself and hung, costing about 1 h. Waits now go on the PID.
- **B.6 cross-check vs T1's pooled A5 END S forwards** (`fe534ec0`): PASS, 300/300 bit-exact.
- **Memory check:** PASS. Conservative 2.88 GiB vs the 6 GiB cap; concurrent 1.60 GiB.
- **Seal:** `mac-sets-selection.json` `f3b87ce5`, all checks true.
- **Hand-off package:** `receipts/phase3-20261012/` (`HANDOFF.md`).
