# K4S END A4 — preflights (S5 via S7), 03 then 04 — GO request

Prepared 2026-10-13T23:16:07Z by the K4S runner on 127x05 after A2 completed on both hosts (03 43fac268, 04 61b5a98e). No host contact since A2 (last login 04 23:13:51Z).

## Prepared on 05 (no host contact)

- Gate/S5/tools: s5s6s7-r6 (SHA256SUMS 2b4b6f215514103e97542012d4f314438d7969cd1da33503ffd22f20cade2cb6); RC-6 declaration 872ced5028db256e3b587f7fd5f2a9a4f6a5247f0b1a0548adb3e7accb628a40.
- Receive dirs created (S7 `prepare-preflight-receive`): `run-r1/preflight-received/127x03/preflight-127x03-l00/` and `…/127x04/preflight-127x04-l00/` (empty, 0700).
- Argv built (S7 `build-argv --kind preflight`), attempt bundle pf00, compare bundle rd00-a00, native/corpus under each base's end-inputs-r1:
  - 03 `end-launch/127x03/preflight-127x03-l00/launch-argv.json` 31b40ec828cc22946d6a0b974b270692f791afafcb4be7f47baf7867cbc6d0d7; argv SHA (NUL-joined) 12404bca046ccd6b81fd52f4dccf3ef674293305e43a512887c309535c7725a3; `--hold-seconds 600` (min 120).
  - 04 `end-launch/127x04/preflight-127x04-l00/launch-argv.json` 3a91417bcd098756b0552c64c12ae3144f06fb027623e1d45c8e1c484c5555c9; argv SHA 24f9c0ba48415ebe4e932bba7591bae78e728a291577dd5640c9318987a36575; `--hold-seconds 1200` (min 900; the binding mode needs a measured loaded span >= 900 s).
- S7 `launch --dry-run` for both: rc 0 (every 05-side check incl. RC-6, argv structure/pins, receive dir; no ssh). Composed host programs: 03 8f42683cbd3fc27175310d6f369d74a5e2ef4e63eb2d02c212bf6f32f4d27a74, 04 e14933533627edf16ae6c0f9d9079e262ef30059f29b7832535d1c6f231a320f.

## Host steps requested (each one S7 session; 03 first, then 04 after 03's result is verified on 05)

```
B=/mpac/sdicks02/k4s-runner/run-r1/end-prep/s5s6s7-r6
cd /tmp && umask 022 && env -i PATH=/usr/bin:/bin HOME=/home/sdicks02 LANG=C.UTF-8 nice -n 19 /usr/bin/python3 -I -B $B/k4s_end_launch_gate.py \
  launch --host 127x03 --kind preflight --attempt preflight-127x03-l00 --argv-sha256 12404bca046ccd6b81fd52f4dccf3ef674293305e43a512887c309535c7725a3 --roots-sha256 872ced5028db256e3b587f7fd5f2a9a4f6a5247f0b1a0548adb3e7accb628a40
# after 03's push has arrived:
… /usr/bin/python3 -I -B $B/k4s_end_preflight.py verify-received --receive /mpac/sdicks02/k4s-runner/run-r1/preflight-received/127x03/preflight-127x03-l00
# then 04 (same form): --host 127x04 --attempt preflight-127x04-l00 --argv-sha256 24f9c0ba48415ebe4e932bba7591bae78e728a291577dd5640c9318987a36575, then verify-received for 04
```

The one S7 session per host (1 login from 05) does: rc-checked hostname; quiet-read v3 #1, 30 s, #2 (apt/maint/who must be quiet); unfiltered `systemctl list-timers --all` with every timer >= 7200 s clearance (default; a per-timer `--allow-timer` exception needs your ruling); stamps (release-upgrade-available age <= 24 h minus the 7200 s window; updates-available newer than the apt lists); `who` zero lines; ps: no other sshd session; staged tool SHAs; base/parent/job; frozen-reader checks of the repository and guard repo; C5 pre-exec gate; then launches the detached preflight wrapper (`<tools>/detach.sh` + `k4s_preflight_push.sh`, S5 under `nice -n 10 taskset -c 61`) and closes. S5 runs the full non-claiming preflight (backend construction, guard admission, >= 60 1 Hz samples, background slots, hold), never `measure()`, never claims. After exit the wrapper pushes the sealed result to the 05 receive dir; `verify-received` (05) writes `PREFLIGHT-VERIFIED.json` (the RC-9 input).

Expected duration: 03 ~15–20 min, 04 ~25–35 min (1200 s loaded hold + setup).

## Preconditions / conditions

1. Your A4 GO (per host or both; 04 only after 03's verify-received result is reported).
2. No SSH to the host being preflighted from any thread for the whole S7 session + S5 run (04: S5 records any login/sshd increase during the hold and fails); FSC/perception/other K4S or T1 work off 03/04.
3. Any S7 refusal (exit 3: nothing launched) stops for your ruling — in particular stale stamps (would need the A5 pre-trigger login) or a timer inside 2 h. No retry without a new GO. Preflights do not consume END attempts.
4. Gate after both: both pass; 04 loaded cumulative bus <= ~0.3 % proceed (between: your BUS-DECISION; >= 0.7 %: STOP and re-ruling before any claim).

## After

Commit an outcome-blind disclosure (S7 receipts, PREFLIGHT-VERIFIED.json, mode/load/duration/bus band) to main; report; then the END-JOB (A6) request.
