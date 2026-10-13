# X4S-3b (U2) progress (exploration, NEVER ADOPTABLE)

Owner: U2 Opus worker. Readout: [READOUT.md](READOUT.md). Host: 127x01 only. J2 =
`/mpac/sdicks02/jobs/clasher/x4s3b-fitseed-20261013`; J = `/mpac/sdicks02/jobs/clasher/x4s3-student-scale-20261012`
(read-only, never written).

**Never touch:** `t1-*`, `fleet-end-attempts*`, J (except reads), any X4S-4 prefix, the paused hub mirror
(PGID 516161), roader hosts. No `pkill -f`; no sealed outcome reads. Process checks are by PID only.

## STOP U2 (on the coordinator's "STOP U2", at the X4S-4 GO)
1. On 01: `touch J2/STOP J2/FIT.STOP`.
2. The supervisor drains in ≤ 2 min; the driver SIGTERMs the trainer PID (it checkpoints). Then SIGTERM the driver
   PID from `J2/driver/driver.pid` (it exits on SIGTERM).
3. Confirm by PID, never pgrep: every PID in `J2/driver/driver.pid`, `J2/receipts/*-launch.json` and each live
   phase's `launch.json` (supervisor and child PGID members via /proc stat) is gone; `nvidia-smi` shows no J2 PID.
4. Report to the coordinator. Resuming after X4S-4 needs a new STOP_AT constant, so a coordinator OK.

## Procedure after GO (on 01)
1. **Preflight (read-only):** `who` and `~/.local/bin/fleet-console-users`; MemAvailable ≥ 48 GiB; `nvidia-smi`
   idle; no X4S-3/X4S-4 processes by PID census; free disk on /mpac ≥ 20 GB; J2 absent; the R1, R2 held-out,
   clasher-gpu and repo-venv paths exist.
2. **Copy:** `mkdir J2 && cp -a J/base J/fit J/inputs J2/`; `mkdir -p J2/games J2/driver J2/rt-R3a-rep J2/x4s3b`;
   `cp -a J/games/R3a J/games/R3a-rep J2/games/`; `cp -a J/driver/retired.json J2/driver/`;
   `cp -a J/rt-R3a-rep/READY.json J2/rt-R3a-rep/` (for the reducer only; the driver never schedules R3a-rep).
   Then:
   - `find J2 -type l` census: any link that resolves into J is replaced by a plain copy (`cp -aL`) and recorded;
   - `grep -rIl x4s3-student-scale J2/base J2/fit` census: hits in executed code are reported before launch
     (base plan.json's policy/student paths are expected; the driver rewrites them for new students);
   - SHAs: `J2/fit/run_fit.sh` = a95aea44 before it is replaced; main02.pt d77005d5, R3a.pt 37509a43,
     the X4S-3 harness pins in `J2/base/repo/reports/explore/x4s3/`.
3. **Install:** x4s3b `run_fit.sh` → `J2/fit/run_fit.sh`; `driver.py`, `reduce.py` → `J2/x4s3b/`; SHA-check each
   against this commit.
4. **8-seed smoke + live STOP test:** supervisor on `--rt J2/base`, `--range smoke`, `idx-smoke.json`, both arms, with
   a config copy of the base plan whose two checkpoint paths point to J2/inputs (SHA pins unchanged). Then touch
   `J2/STOP` during a smoke phase and time the supervisor exit and an empty group; remove STOP.
5. **Launch:** `cd J2 && bash base/repo/reports/explore/x4s3/detach.sh logs/driver.log
   receipts/driver-launch-$(date -u +%H%M).json nice -n 10 taskset -c 56-61 python3 -u x4s3b/driver.py`, after
   `touch J2/REPORTING.GO`. Games use cores 0–49, the fit 56–61, loaders 120–125, nice 10.
6. **Mirror** finished fits/games to `05:J2/mirror/` (explicit copies, SHA-verified), then reduce and write RESULTS.

## Resume (after a session restart)
On 01: `cat J2/driver/heartbeat.json J2/driver/driver.pid`; `tail J2/driver/events.jsonl`; `ls J2/driver/ANOMALY-*`.
If the driver is not live (check the PID in driver.pid via /proc) and STOP is absent, relaunch with step 5.

## Log (date -u)
- **2026-10-13 01:16Z–01:24Z:** read Item 2, COORDINATOR (U1–U4, PR-1), X4S-3 PLAN/RESULTS/PROGRESS. Harness pins
  re-verified on origin/main (driver 0b0ee8b1, supervise 730b0527, run e7f90d76, runtime 5716149c, detach 23a5dfaa,
  calibrate 82a4d442, run_fit a95aea44, reduce 9ede397b).
- Drafted the constants-only diff and READOUT. Offline checks on 05 (scratch in /tmp only):
  - the edited reducer reproduces X4S-3 results.json byte-for-value (arms, contrasts, CIs, sensitivity, checks) on
    the 05 mirror;
  - the σ̂ formula matches a hand computation (on a test-only pair alias; the value is meaningless and not reported);
  - a scheduling simulation of the edited driver: 1,167 todo per phase, R3a never scheduled, no fit launch while
    S-200 is live or dispatchable, only K4S-120 dispatched while a replicate fit runs.
- No host contact. Waiting for the diff-only review and the coordinator's GO.
- **Review:** Sol diff r1 APPROVE_WITH_CONDITIONS (`x4s4-review/SOL-REVIEW-X4S3B-DIFF-r1.md`, 840c9733);
  coordinator GO. Conditions: (1) run_fit.sh mode restored to 100644, invoked via `bash` by the driver;
  (2) all writes under J2, reducer `--out J2/analysis/...`; (3) STOP_AT = **2026-10-13T09:35:00Z** (≤ launch + 8 h),
  assertion kept. The post-STOP counting rule is pre-declared in READOUT (Sol finding 5).
- **01:29:00Z preflight (01):** 0 console users; MemAvailable 122 GiB; PSI 0.00; GPU 107 MiB, 0%, no compute apps;
  /mpac 806 GB free; no X4S-3/X4S-4 processes (only the paused hub mirror PGID 516161, untouched); R1, R2 held-out,
  clasher-gpu and repo-venv paths present. J pins: run_fit a95aea44, main02 d77005d5, R3a 37509a43, native
  44874fd6, harness driver 0b0ee8b1 / supervise 730b0527 / run e7f90d76 / runtime 5716149c / detach 23a5dfaa /
  calibrate 82a4d442.
- **01:29:28Z copy:** `cp -a` of J/{base,fit,inputs}, games/{R3a,R3a-rep}, driver/retired.json,
  rt-R3a-rep/READY.json into J2 (590 MB). `diff -r` identical; 0 symlinks, 0 multi-link files. J-path references
  remain only in base plan.json (rewritten for new students), non-executed files (base driver/run_fit/pull_g08/
  mirror/PLAN, fit/ops union.py/verify_g.py, J2/fit/run_fit.sh before replacement), and run records in copied games
  and rt-R3a-rep/READY.json (reducer reads only its SHA).
- **Install:** J2/fit/run_fit.sh (a95aea44 → 7e9c57d1, mode 644), J2/x4s3b/reduce.py a670d2af, driver.py from the
  launch commit. Smoke runtime J2/rt-R3a = copy of J2/base with plan policy/student checkpoint paths → J2/inputs
  (SHA pins unchanged).
- **01:29:53–01:30:55Z smoke K4S-120:** 8/8 blocks, rc 0, reason null, 61 s, group empty; student R3a 37509a43,
  host 127x01, nice 10, student-default 4–22% of decisions.
- **01:31:08–01:32:41Z smoke S-200:** 8/8 blocks, rc 0, reason null, group empty.
- **Live STOP test (S-200 smoke phase):** STOP touched 01:33:26.144Z with 51 child-group members; supervisor gone
  01:33:28.690Z (2.5 s), reason owned_STOP, 0 members left in either group; STOP removed.
- **01:34:32Z** first driver launch refused by the STOP_AT assertion (28 s early); PID 2609188 confirmed gone.
- **01:35:06Z driver launched:** PID/PGID 2610986 (`receipts/driver-launch-0135.json`). R3a-rep2 fit PID/PGID
  2610994 on 56–61, loaders 120–125, nice 10. **01:37:09Z:** step 32, 1.8 s/step, GPU 2.5 GB, PSI 0.00; ETA about
  02:53Z. Launch receipts and smoke mirrored to `05:J2/mirror/launch/`.
- **02:51:57Z R3a-rep2 fit returned** 2,500/2,500 steps, stopped=false (~4,610 s); checkpoint 72d73375. Driver launched
  the R3a-rep3 fit (PID/PGID 2859387, 56–61) on the same tick, before rep2's runtime was READY (expected path).
- **02:52:02Z ANOMALY (staging omission, fixed):** rep2 calibration rc 1, `FileNotFoundError` writing
  `J2/calibration/R3a-rep2.json`: my J2 staging created no `calibration/` dir (J had one). No code change: at
  03:02:46Z I created `J2/{calibration,analysis,attempts}`, moved the anomaly and attempt-1 log to `J2/attempts/`
  (copies in receipts/fits/R3a-rep2/), and the driver retried. Cost: about 11 min of idle game cores.
- **03:02:54Z R3a-rep2 calibrated:** threshold 0.49848902225494385, play rate 0.345944609297725 (same count as R3a),
  seed 2026101204 in checkpoint meta; runtime plan points only at J2. **R3a-rep2 K4S-120 a1** launched, 1,167 todo,
  10 workers, beside the rep3 fit (PSI 0.00).
- **03:03:20Z mirror:** `05:J2/mirror/rep2-fit/` (checkpoint, calibration, READY, fit receipts, driver, logs);
  SHAs match.
- **STOP U2, amended (COORDINATOR 4b33d68d; X4S-4 GO):** let rep2 finish K4S-120 and S-200, start nothing after,
  then the STOP procedure; rep3 fit/games abandoned. **03:36:42Z** state: rep2 K4S-120 528/1,167; rep3 fit step 1,424.
  **03:36:52Z** owner holds `driver/ANOMALY-phase-R3a-rep3-{K4S-120,S-200}.json` placed (next_phase returns None at a
  held entry, so nothing dispatches after rep2 S-200). If the rep3 fit is still running when rep2 K4S-120 exits, it is
  stopped by owner hold `ANOMALY-fit-R3a-rep3.json` + `FIT.STOP` (trainer checkpoints) so rep2 S-200 can dispatch.
- **04:09:40Z** R3a-rep3 fit returned (2,500/2,500, stopped=false; checkpoint 43621ce4); **04:10:07Z** calibrated,
  threshold 0.49953630566596985, same play rate. Held: it plays no games (abandoned under the amended STOP).
- **04:16:08Z** rep2 K4S-120 a1 complete: 1,167/1,167, rc 0, reason null. **04:16:09Z** rep2 S-200 a1 dispatched (no
  fit live). **04:40:54Z** rep2 S-200 complete: 1,167/1,167, rc 0, reason null.
- **STOP U2 executed:** `touch J2/STOP J2/FIT.STOP` at 04:41:03.854Z; supervisor 3154215 already gone; driver
  2610986 SIGTERM 04:41:18Z, exited 04:41:19Z (`driver_exit SIGTERM`). PID census: 2610986, 2610994, 2859387,
  3154215 gone; all 14 owned PGIDs (smoke, stop test, driver, fits, phase supervisors and children) have 0 members;
  no process with cwd under J2 (the first census saw only my own census shell); GPU 107 MiB, no compute apps.
  **Abandoned (disclosed):** R3a-rep3's 2 × 1,167 games; its checkpoint and calibration are kept.
- **04:42:13Z** full J2 mirrored to `05:J2/mirror/final/` (21,456 files, 1.8 GB; aggregate SHA match).
- **04:42:38Z** interim reduction on the 05 mirror → `mirror/final/analysis/x4s3b-interim-r1.json` (00926d0d;
  copy at results-interim.json): rep2 − rep pooled +0.26 pp, V 1.108 pp², σ̂_fit = 0.0 pp (interim, 1 df).
  [RESULTS](RESULTS.md) written. U2 complete; no further 01 contact unless the coordinator OKs resuming rep3's games.
- **U2b GO (COORDINATOR d28ce370):** rep3 games on 03/04, STOP_AT 13:30:00Z, K4S not on 03/04 before 14:30Z.
  **11:50Z** constants commit 127dce775 (host tuples run.py:300, supervise.py:72, reduce.py:53; index split
  33–615 → 03, 616–1199 → 04; READOUT amendment U2b). Staging tree built on 05 at `J2/mirror/u2b-stage/` (296 MB,
  3,364 files, 0 links; rt-R3a-rep3, rt-R3a-rep2 with the edited run.py/supervise.py and J-free checkpoint paths;
  inputs main02/R3a-rep3/R3a-rep2/R3a; qual config).
- **11:50:56Z preflight** 03 and 04: 0 console users, MemAvailable ~122 GiB, PSI 0, idle; 3990X; venv python
  3.12.13, numpy 2.3.5, torch 2.10.0+cu128. **11:51:17Z** staged to `/mpac/sdicks02/jobs-x4s3b/rep3-20261013/`
  on both (aggregate SHA 9d178195 = 05).
- **11:51:25–11:52:19Z identity gate** K4S-none(R3a) on X4S qual indices [0,1]: `command_sha256` af630cf0 and
  d530982b MATCH on both hosts, rc 0.
- **11:52:28Z rep3 K4S-120 launched:** 03 `games/R3a-rep3/K4S-120/a03` PID/PGID 397636 (583 todo); 04 `…/a04`
  PID/PGID 3754093 (584 todo); `--stop-at 2026-10-13T13:30:00Z`.
- **Resume / STOP:** on each host `touch $P/STOP`; wait on supervisor PIDs from `$P/receipts/*-launch.json`; census
  PGIDs (supervisor + `child_pgid` in each phase `launch.json`).
- **12:03Z throughput:** 173 (03) / 174 (04) K4S-120 games in 10.5 min ≈ 16.4/min per host (guard 13). PSI 0.
- **Phases (all rc 0, reason null, full index sets):** 03 rep3 K4S-120 → 12:27:18Z, S-200 12:27:21–12:39:03Z,
  rep2′ S-200 12:39:11–12:50:49Z, rep2′ K4S-120 12:50:51–13:25:39Z; 04 rep3 K4S-120 → 12:27:42Z, S-200
  12:27:51–12:39:36Z, rep2′ S-200 12:39:41–12:51:28Z, rep2′ K4S-120 12:51:31–13:26:46Z.
- **STOP:** touched 13:27:02.914Z (03), 13:27:27.971Z (04). Census: all supervisor PIDs gone, all supervisor and
  child PGIDs 0 members, no cwd under the prefix, on both hosts.
- **13:28Z mirrors** `05:J2/mirror/u2b-03` (8,082 files), `u2b-04` (8,090) match by aggregate SHA. Reduction trees
  `J2/mirror/reduce-u2b-final` and `reduce-u2b-within` (plain copies).
- **13:28:56Z FINAL:** σ̂_fit = 0.58 pp (df 2; terms −0.52, +0.53, +0.99 pp²). Within-host σ̂_w = 0.78 pp.
  Host effect rep2′ − rep2 pooled +0.39 [−1.67, +2.49]. RESULTS updated. **U2/U2b complete; no live processes on
  01/03/04; prefixes left in place (03/04 `/mpac/sdicks02/jobs-x4s3b/rep3-20261013`, 296 MB + games).**
