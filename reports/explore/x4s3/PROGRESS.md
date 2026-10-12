# X4S-3 progress (exploration, NEVER ADOPTABLE)

The job root is on 127x01 at `/mpac/sdicks02/jobs/clasher/x4s3-student-scale-20261012` (J below); see [PLAN](PLAN.md).
Hard stop is 2026-10-12T23:30:00Z.

- **STOP:** `touch J/STOP`. The supervisor drains within about 2 min, and the driver SIGTERMs the fit (the trainer
  checkpoints, then resumes on the next driver tick after STOP is removed). After a STOP, games resume only once
  `J/driver/RESUME-AFTER-STOP` exists.
- **Owner:** the X4S-3 Opus worker. **Coordinator:** thread 0523ae6f.

## Resume (after a session restart)
1. On 01:
   - `cat J/driver/heartbeat.json J/driver/driver.pid`;
   - `tail J/driver/events.jsonl`;
   - `ls J/driver/ANOMALY-*`.
2. **Driver** (if it isn't live): `cd J && bash base/repo/reports/explore/x4s3/detach.sh logs/driver.log receipts/driver-launch-$(date -u +%H%M).json nice -n 10 taskset -c 56-61 python3 -u base/repo/reports/explore/x4s3/driver.py`.
   It's stateless across restarts: fits, calibrations, runtimes and phases are all derived from disk. Never reuse a
   phase directory.
3. **Fits:** `J/fit/run_fit.sh ID [resume.pt]`; the logs are at `J/logs/fit-ID.log` and `J/fits/ID/train.jsonl`.
4. **Games:** phases are in `J/games/<ID>/<arm>/a<k>/` (`progress.json`, `supervisor-exit.json`). Retired seeds are
   in `J/driver/retired.json`.
5. **G-08 pull:** only after a relayed APPROVE of the reviewed version. On 01, run
   `bash J/base/repo/reports/explore/x4s3/pull_g08.sh`, detached. Then run `verify_g.py --mode g08 --concat
   J/data/six-million-concat-manifest.json` with the clasher-gpu python. Finally write `J/data/G-UNION-VERIFIED.json`,
   which requires both the g01 and the g08 receipts to have passed.
6. **Reduce:** `python3 reduce.py --job J --students R3a R4-D … --out …` (fixed N: every non-retired index must be
   terminal for each student).

## Log (date -u)
- **2026-10-12 11:21Z:** received the assignment and read the plan, the COORDINATOR entry 52f901c1, and the X4S, S1
  and R3 code.
- **11:2xZ:** sent the G-08 pull r1 to the coordinator for a Sol review. The review came back REQUEST_CHANGES on
  P1–P6. **11:40Z:** r2 sent (pull_g08.sh 9c612569, verify_g.py 80ace209, 17 + 9 fixture cases ok, verifier also
  under -O/-OO). The pull has NOT been run.
- **11:30Z:** seed audit clean:
  - an origin/main export (288 prior ranges, 10,633 literals, none in the window);
  - the shared working tree (also clean);
  - a generic base/count scan of every repo JSON (no overlap).
- **11:31Z:** runtime staged on 01 from read-only copies of s1-20261010-r1 {repo, native, inputs, corpus}. All 1,557
  S1 runtime-pin-r2 files match. Overlays: x4s (origin/main) and x4s3. Pins: native 44874fd6, v1 d77005d5, R3a
  37509a43.
- **11:32Z:** R3a-rep fit attempt 1 failed at load: `inputs/assets.npz.json` was missing. It's in `J/attempts/`.
  **11:33:17Z:** R3a-rep fit launched (attempt 2) on cores 56–61 at nice 10: about 1.85 s/step and 2.6 GB of GPU
  memory; ETA about 12:57Z. The trainer source matches R3a's 24 recorded source pins.
- **11:35Z:** the R3a calibration recheck reproduces the play rate exactly (0.345944609297725). The threshold
  differs by 3e-8 (GPU float midpoint); same played set, and R3a keeps its frozen threshold.
- **11:41–11:48Z:** qualification passed ([receipts/qualification.json](receipts/qualification.json)):
  - unit tests: 31 passed;
  - 125-state corpus: counts equal X4S's receipt;
  - K4S-none(R3a) on X4S's qualification seeds reproduces X4S's recorded hashes af630cf0 and d530982b;
  - K4-none equals K4S-none on 8/8 X4S-3 qualification seeds;
  - x4s3 S-none equals S1's own run.py S-none on 8/8.
- **11:47Z:** G-01 local copy verified and sealed with `verify_g.py --mode g01`: 149,385 roots, 144 files.
- **11:48Z:** smoke (8 seeds) launched through the supervisor, starting with K4S-120.
- **11:49:56Z:** freeze commit 12db49a1: PLAN, harness, seed audit and qualification receipts, pushed before any
  reporting game.
- **11:49–11:51Z:** smoke R3a: 8 K4S-120 games (about 32 s/game; student-default 10–23% of decisions) and 8 S-200
  games (one-core lanes, about 43 s/game), both rc 0. Live STOP test: STOP at 11:51:31.9Z, supervisor exit
  11:51:33.97Z, 0 group processes left.
- **11:52:39Z:** REPORTING.GO written and driver launched. R3a K4S-120 phase a1 started.
- **ANOMALY, 11:52:50–11:54:06Z:** attempts a1 and a2 were stopped by the supervisor's memory-PSI kill guard (some
  avg10 > 10%). This was a page-cache burst while 10 workers started alongside the fit's corpus streaming;
  MemAvailable was about 105 GiB. I halted the driver and a3 by hand at 11:54Z.
  - Fix (guard-only, with no game-code change): the supervisor kills only on MemAvailable < 24 GiB or owned PSS
    > 50 GiB. The driver withholds new dispatch while memory PSI some avg10 > 10%, which is the plan's "stop
    dispatching".
  - The declared rule retired 33 seeds (indices 0–32) for every student; none of those games had finished. 1,167
    paired seeds remain.
  - Driver relaunched at 11:55:37Z; a3's exit acknowledged; R3a K4S-120 a4 started at 11:56:37Z with PSI 0.0.
- **11:59Z:** G-08 pull r3 sent for the narrow delta check (pull_g08.sh 834d1598, verify_g.py eef8cdfd; tests 14/14
  and 28/28 × 3 optimization levels). The coordinator ruling accepts R2-1, R2-2 and R2-3 as residuals, on
  condition that the pull runs in the foreground, attended. mirror.sh was also sent for review. Not run yet.
- **12:11Z:** throughput check on R3a K4S-120 a4: about 980 games/h over the last 10 min (target about 1,000).
  Memory PSI peaked at 20.9 during the phase; it is logged only and is not a kill condition. MemAvailable ≥ 105.6
  GiB, no console users.
- **G-08 pull (coordinator APPROVE of r3; mirror.sh withdrawn):** deployed `pull_g08.sh` SHA 834d1598 and
  `verify_g.py` SHA eef8cdfd on 01 (SHA-checked).
  - Ran once, in the foreground and attended, from an ssh session: 12:11:09Z → exit **0** at 12:21:23Z.
    stdout/stderr were empty ([receipts/g08-pull-run.log](receipts/g08-pull-run.log)).
  - Stamps: start 12:11:10Z, end 12:21:21Z.
  - Preflight: all 17 source paths were `directory`
    ([receipts/g08-source-stat.txt](receipts/g08-source-stat.txt)).
  - During the transfer, timeout, rsync and ssh were in owned PGID 2108760 at nice 19. After exit, no process
    remained in that PGID. 24 GB copied.
- **12:21:29–12:22:46Z:** `verify_g.py --mode g08` exit **0**: passed, sealed, 2,645,689 roots, 11 shards, 792
  files read-only ([receipts/g08-verify.json](receipts/g08-verify.json)).
- **12:22:50Z:** union gate written ([receipts/G-UNION-VERIFIED.json](receipts/G-UNION-VERIFIED.json)): r1 + G-01
  + G-08 = 8,804,755 roots. The R4-D fit starts when R3a-rep frees the GPU (about 13:00Z).
