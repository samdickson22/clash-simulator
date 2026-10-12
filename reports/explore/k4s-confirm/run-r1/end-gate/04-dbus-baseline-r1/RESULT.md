# R4: read-only baseline of 127x04's system bus (coordinator DBus ruling R4)

- **Recorded:** 2026-10-12T15:15:56Z (`date -u`).

## Conditions
- **Reporting:** fully drained. The r4 supervisors exited at 14:43:51Z (03) and 14:40:39Z (04).
- **Copiers:** off. Both finished at 14:44:54Z; `ps -p` returned rc 1 at 14:45:02Z.
- **Activity on 04:** no K4S process and no console user (`who` 0 at start and end). The GDM greeter was still resident: 45 uid-125 processes at start and end.
- **Logins:** none on 04 during the window except the probe's own single session.

## Method
- One long-lived SSH session (`ssh -o BatchMode=yes -o ServerAliveInterval=30 127x04 'nice -n 19 bash -s' < probe.sh`), with no other login to 04 for the whole window.
- `probe.sh` (sha256 `6fc64392…`) reads `/proc/2005/stat` (the pinned system dbus-daemon) once a second, 1,800 times.
- **Window:** 2026-10-12T14:45:20.208Z to 15:15:32.988Z, 1,811.7 s. ssh rc 0, no GONE.
- **Identity:** PID 2005 with start_ticks 1032 in every sample (the reporting-time pin).
- **Core %:** 100 × Δ(utime + stime) / (CLK_TCK 100 × Δwall). Computed by `analyze.py` (`0eb90739…`) over `samples.txt` (`b80bf1cd…`), giving `analysis.json` (`9652b8ea…`).

## Result

**Whole window: 0.0359% of one core.**

| Rolling window | n | p50 % | p95 % | max % | > 0.7% | > 1% |
|---|---|---|---|---|---|---|
| 30 s | 1770 | 0.0331 | 0.0662 | **0.0993** | 0 | 0 |
| 60 s | 1740 | 0.0331 | 0.0497 | 0.0662 | 0 | 0 |
| 120 s | 1680 | 0.0331 | 0.0414 | 0.0497 | 0 | 0 |
| 300 s | 1502 | 0.0367 | 0.0400 | 0.0433 | 0 | 0 |
| 600 s | 1204 | 0.0367 | 0.0383 | 0.0400 | 0 | 0 |

## Reading

**Against the threshold:** the baseline is clearly below 1%. Every window is at most 0.1%, about 10× under the investigation's 0.7% bar. The R4 criterion "clearly under 1% → END as frozen" is met for the idle-host baseline.

**Inference, not a measurement:**
- The resident GDM greeter alone puts about 0.04% on the bus.
- The ~1.47% during reporting therefore came mostly from session churn: the copier's SSH logins (and logind and broadcast fan-out to the greeter's subscribers) while reporting ran.

**Caveat: this is not a measurement under END load.**
- END runs the reporting load profile on all slots, plus a launch SSH.
- The plan should keep the END attempt free of extra logins to 04: one launch SSH, closed before admission, and no copier during the attempt (C5).
