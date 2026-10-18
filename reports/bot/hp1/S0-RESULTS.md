# HP1 S0 results

Exploratory screen; source `1e933ddc3eda1005d00182be429e79c125712260`; protocol and banks follow S0-PREREG.md. Smoke and calibration games are excluded from scored estimates.

## Calibration

Target E = 42.937500 candidate plays/game (SE 1.866964), score 0.703125, n=64 vs R3a.

| Round | Exact τ string | n | Plays/game | SE | Score |
|---|---|---:|---:|---:|---:|
| cal-0 | `0.1` | 64 | 13.218750 | 1.330814 | 0.109375 |
| cal-1 | `0.06666666666666667` | 64 | 28.468750 | 1.966859 | 0.734375 |
| cal-2 | `0.044444444444444446` | 64 | 37.140625 | 2.016778 | 0.875000 |
| cal-3 | `0.02962962962962963` | 64 | 38.140625 | 1.749272 | 0.937500 |
| cal-4 | `0.019753086419753086` | 64 | 41.968750 | 2.010633 | 0.734375 |

τ* = `0.019753086419753086`; frozen before H launch (within 1.5 plays/game).

## Status

Last checked: 2026-10-18T02:52:26Z (from `date -u`).
Games run only on 127x04, through env.sh → detach.sh → cpu_job.sh, nice 15, BOT_CPU_CAP=70. At most 16 S0 game workers; no source/env/run changes.

- cal-t: valid; workers=8; PGID=3453513; launch 2026-10-17T23:49:40Z; admitted 2026-10-18T00:00:57Z; ended 2026-10-18T00:09:42Z; exit=0.
- ef: valid; workers=8; PGID=3453624; launch 2026-10-17T23:49:40Z; admitted 2026-10-18T00:00:59Z; ended 2026-10-18T00:57:44Z; exit=0.
- cal-0: valid; workers=8; PGID=3924616; launch 2026-10-18T00:09:56Z; admitted 2026-10-18T00:18:58Z; ended 2026-10-18T00:26:02Z; exit=0.
- cal-1: valid; workers=8; PGID=3938517; launch 2026-10-18T02:36:13Z; admitted 2026-10-18T02:36:14Z; ended 2026-10-18T02:39:51Z; exit=0.
- cal-2: valid; workers=8; PGID=3973448; launch 2026-10-18T02:40:17Z; admitted 2026-10-18T02:40:17Z; ended 2026-10-18T02:43:40Z; exit=0.
- cal-3: valid; workers=8; PGID=4008613; launch 2026-10-18T02:44:20Z; admitted 2026-10-18T02:44:20Z; ended 2026-10-18T02:47:44Z; exit=0.
- cal-4: valid; workers=8; PGID=4043455; launch 2026-10-18T02:48:24Z; admitted 2026-10-18T02:48:24Z; ended 2026-10-18T02:51:50Z; exit=0.

Status log:

- 2026-10-17T23:51:42Z: cal-t launched with 8 workers; receipt PGID 3453513.
- 2026-10-17T23:51:42Z: ef launched with 8 workers; receipt PGID 3453624.
- 2026-10-18T00:09:55Z: cal-t validated: 64 rows, 0 errors; R3a score=0.703125 plays=42.937500
- 2026-10-18T00:09:56Z: cal-0 launched: τ=0.1, workers=8, PGID=3924616.
- 2026-10-18T00:13:00Z: SIGSTOP own ef PGID 3453624; load=81.30; higher-priority running=True.
- 2026-10-18T00:14:01Z: SIGCONT own ef PGID 3453624; load=64.91; higher-priority running=True.
- 2026-10-18T02:36:08Z: cal-t validated: 64 rows, 0 errors; R3a score=0.703125 plays=42.937500
- 2026-10-18T02:36:08Z: cal-0 validated: 64 rows, 0 errors; R3a score=0.109375 plays=13.218750
- 2026-10-18T02:36:08Z: ef validated: 400 rows, 0 errors; K4C-r16 score=0.450000 plays=44.000000; R3a score=0.630000 plays=43.110000; K4C-r16 score=0.150000 plays=26.310000; R3a score=0.250000 plays=28.420000
- 2026-10-18T02:36:08Z: Resumed under coordinator ownership; finished cal-t, cal-0 and ef revalidated without rerunning seeds. Reset stale load timer; no S0 game jobs active.
- 2026-10-18T02:36:13Z: cal-1 launched: τ=0.06666666666666667, workers=8, PGID=3938517.
- 2026-10-18T02:40:16Z: cal-1 validated: 64 rows, 0 errors; R3a score=0.734375 plays=28.468750
- 2026-10-18T02:40:17Z: cal-2 launched: τ=0.044444444444444446, workers=8, PGID=3973448.
- 2026-10-18T02:44:19Z: cal-2 validated: 64 rows, 0 errors; R3a score=0.875000 plays=37.140625
- 2026-10-18T02:44:20Z: cal-3 launched: τ=0.02962962962962963, workers=8, PGID=4008613.
- 2026-10-18T02:48:22Z: cal-3 validated: 64 rows, 0 errors; R3a score=0.937500 plays=38.140625
- 2026-10-18T02:48:24Z: cal-4 launched: τ=0.019753086419753086, workers=8, PGID=4043455.
- 2026-10-18T02:52:26Z: cal-4 validated: 64 rows, 0 errors; R3a score=0.734375 plays=41.968750
- 2026-10-18T02:52:26Z: Calibration frozen: τ*=0.019753086419753086 from cal-4; target=42.937500.

## Validity and resources

7 completed runs validated, 784 rows, 0 validation errors. Smoke: 12/12 valid (prior completed run), excluded from estimates and the totals below.
CPU total for validated calibration and scored runs: 9.769907 CPU-h (sum of game cpu_seconds).
Wall elapsed since first helper launch, including admission and pauses: 3.046111 h.
- cal-t admitted-to-end wall: 0.145833 h (includes any STOP time).
- ef admitted-to-end wall: 0.945833 h (includes any STOP time).
- cal-0 admitted-to-end wall: 0.117778 h (includes any STOP time).
- cal-1 admitted-to-end wall: 0.060278 h (includes any STOP time).
- cal-2 admitted-to-end wall: 0.056389 h (includes any STOP time).
- cal-3 admitted-to-end wall: 0.056667 h (includes any STOP time).
- cal-4 admitted-to-end wall: 0.057222 h (includes any STOP time).

Analysis and orchestration scripts retained only on 127x05 in `/tmp/sdicks02-hp1-work/s0helper/`:

- `controller.py` SHA256 `b059d4657eddd5628a15cd055a230c3041a8c855bc2472f0dc59b65fa944c7b9`.
- `readout.py` SHA256 `dcd77ddea17f1b23dca0fa877b81a2229bafff038d0abb288988f77a6d19787c`.
- Provided validator `s0/s0_validate.py` SHA256 `6a862b3f6cf8ede2431290d8bdb0a891ca0d5f55229765010f0856b2798e7809`.

Secret scan runs in a scratch worktree detached at the fetched origin/main, using the report-only temporary index. Raw rows and models remain outside git. Only this report is published.
