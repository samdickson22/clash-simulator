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
