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
