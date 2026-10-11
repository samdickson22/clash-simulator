# PREREG-K4S confirmatory run r1: progress (resumable)

Runner: Claude Opus 5.5 (1M), 127x05, for coordinator thread 0523ae6f; assigned 2026-10-11 ~18:00Z.
Job name: clasher-k4s-confirm-run-20261011-r1. Outcomes: **SEALED** (no loss/win/contrast is computed, viewed or logged).

## Fixed facts
- Freeze commit `391d2006` (2026-10-11T17:45:00Z), fill `fab6e03f`. All 32 freeze-record SHAs re-verified at 391d2006 (18:00Z).
- Frozen overlay = `git archive 391d2006 reports/explore/k4s-confirm` (175 files; no k4s-confirm diff 391d2006..0d600fe4).
- Runner worktree (detached at 391d2006): `/mpac/sdicks02/repos/clasher-k4s-run`. Runner scratch: `/mpac/sdicks02/k4s-runner/`.
- Jobs: 03 `/mpac/sdicks02/jobs/clasher/k4s-confirm-r1` (STOP -> `…/k4s-confirm-r1.STOP`);
  04 `/mpac/sdicks02/jobs-k4s/k4s-confirm-r1` (STOP -> `…/k4s-confirm-r1.STOP`). Stage files in `<job>-stage/`.
- Never: ssh 01/08; touch 03 T1 corpus copy; touch 04 `/mpac/sdicks02/jobs/clasher/` or `clasher-v4-cache`.

## Log (UTC, `date -u`)
- 17:59Z: vacancy 03/04: who empty, load 0.00, no foreign compute, MemAvailable ~121 GiB. SSH from 05 arrives over LAN 129.65.221.15.
- 18:00Z: LAUNCH BLOCKERS sent to coordinator (msg k4s-run-r1-blockers-20261011-1): B1 hub/ACK (frozen mirror.py is 01-only
  and 8-game-only; no frozen path writes hub-ack for 03/04), B2 job manifest FROZEN-K4S.json never produced at the freeze,
  B3 REPORTING-AUTHORIZATION.json needs a coordinator message id. Proposed OA-1 `mirror_k4s.py` (hub 05) + B2 builder, Sol-reviewed.
- 18:00:58Z: staged both jobs (pin f81f3655: 1557 inherited + 77 native-source verified; native 44874fd6; corpus 8b188918);
  overlay 175/175 byte-identical to 391d2006 on both hosts.
- 18:01:15Z: launch-time qualification driver started detached, NICE=10: 03 pid/pgid 707325, 04 pid/pgid 3949214.

- 18:00:17Z: coordinator rulings (3badf70d): **B1 approved as K4S OA-1** (new mirror_k4s.py, hub 127x05; Sol must approve
  before use; tests for 8/10-game blocks, hub-ack write-back, guard classifies copier children as owned); **B2 approved**
  (FROZEN-K4S.json from 391d2006; Sol reviews builder + output; commit as receipt); B3 after smoke PASS; a K4S freeze
  addendum (OA-1 SHA, Sol verdicts, B2 manifest SHA) must be committed before any reporting game.
- 18:05Z: authored `oa1/mirror_k4s.py`, `oa1/build_job_manifest.py`, `oa1/test_mirror_k4s.py` (8 pass vs frozen
  ssh_transport.copier_activity). Builder dry run sha 426fe4c5…, 176 files; frozen barrier.reporting_release dry run PASS
  (dummy auth, test only, deleted).
- B4 (found 18:04Z; operational, no frozen bytes): barrier needs `git show 391d2006:…` in /mpac/sdicks02/repos/clasher on
  03/04 (object absent; checkouts at db1d17a01) -> fetch commit objects only (FETCH_HEAD; no ref/worktree change);
  barrier needs PREREG r3 bytes at $J/repo/<path> -> copy byte-verified from 391d2006 after qualification.

- 18:16:57Z / 18:17:24Z: **launch-time qualification PASS** 03 / 04, 28/28 checks each, 299 tests pass, STOP drain 0.60 s /
  0.65 s, K4==T1 and K4S==K4 no-deadline hashes equal, injected-clock 0 mismatches. Receipts `receipts/launch-qualification-127x03.json`
  (f985a32c…) and `-127x04.json` (a11c978c…). Runtime pins 03 65e5beae…, 04 a99ca55b…. Only source diffs vs prep r3: the
  approved audit_seeds.py fix + its test (not runtime).
- 18:19Z: B4 done: 391d2006 objects fetched by SHA into /mpac/sdicks02/repos/clasher on 03/04 (FETCH_HEAD only; HEAD db1d17a0
  unchanged); PREREG r3 (9650972d) copied byte-verified into both staged repos.
- 18:21–18:25Z: OA-1 live integration (synthetic random-byte fixtures, test job dirs removed afterwards): 8- and 10-game blocks
  acked on 05 and written back on 03 and 04; corrupt block refused; frozen census classified copier children
  `ssh_family_budget` (never foreign/active). First run exposed a stall (one bad block aborted the pass) -> fixed (per-block isolation).
- 18:24Z: **03 admission ruling requested**: perception v4 validation cache service PID 2180947 (frozen SERVICE_PIDS['127x03'])
  is foreign unless pinned via frozen idle_services.py. Recommended (a) pin it. Waiting.
- 18:26Z: final B2 manifest FROZEN-K4S.json sha cecb2f59… (176 files, binds both launch receipts). Sol review r1 of OA-1 + B2
  delegated (task k4s-run-r1-sol-oa1-b2-review-r1; review file reviews/SOL-REVIEW-OA1-B2-r1.md).
- 18:27Z: dispatches generated with frozen schedule.py (canonical() on every row): smoke 16 blocks (8/host, 10 arms, 80 games/host)
  sha 5ff0b681…; reporting 3900 blocks / 33000 games, 16500 per host, cell imbalance 0, sha 78335dc4….

## Running (owned PGIDs only)
- none on 03/04 (qualification drivers exited 0).

## Next
1. Qualification receipts (03/04) -> commit under run-r1/receipts/.
2. Coordinator ruling on B1/B2/B3; author + Sol-review `mirror_k4s.py` and the manifest builder.
3. Excluded smoke (8 blocks/host, all 10 arms) -> SMOKE-PASS -> coordinator go -> reporting dispatch.
