# BN1 board-noise knockout: PROGRESS (resume here)

Owner: cycle-model owner (Opus), for the BOT LEAD; readout to the BOT LEAD and the LIVE LEAD. Pre-registration and
results: RESULTS.md. Code: bot/livediag/board_noise.py (+ board_noise_runs.json from the translator owner's
BOARD-OWN-AS-ENEMY.json 60d51fd6…, test_board_noise.py).

## Thread IDs (copy verbatim)

| who | thread id |
|---|---|
| BOT LEAD | thread:delegated-task:command%3Amcp%3A53609d4a-a2de-484a-834d-8566c6339c9f%3Adelegate-task%3Aclasher-bot-lead-20261014-r1 |
| LIVE LEAD | thread:delegated-task:command%3Amcp%3A53609d4a-a2de-484a-834d-8566c6339c9f%3Adelegate-task%3Aclasher-live-lead-20261014-r1 |
| live-diag (driver owner) | thread:delegated-task:command%3Amcp%3Ad5b57bd6-719b-4e85-a080-8b8bfc639a49%3Adelegate-task%3Abot-lead-live-diag-r1 |

## State (2026-10-17T19:05Z)

- **Driver:** live-diag's frozen copy /mpac/sdicks02/jobs/clasher/bot-livediag/cadence-bn/ (l16_cadence.py f2088e23…,
  run-l16-cadence.sh 1e93df82…) with the token `bn(off|v11|v14c|v11x3)`.
- **Source tree:** /mpac/sdicks02/repos/clasher-bot-cycle on 04 and 08 at main d04aea9e9.
- **08 needs** LIVEDIAG_OLD=/mpac/sdicks02/jobs/clasher/bot-livediag/mirror/bot-deckopt2 and
  LIVEDIAG_HELPERS=…/mirror/bot-deckopt2-sam.
- **Smoke** (private driver copy, 08, job dir bnsmoke): 0 errors; bnv11x3 applied 26–39 runs per game; bnoff = 0.
- **Launched 19:04Z** (job dir bn1/):
  - 04 main-s0 (shard 0/2, 20 workers, PGID 134969);
  - 08 main-s1 (shard 1/2, 20 workers, PGID 1905540);
  - 04 parity par-v2 (cadence-v2, res-wint; PGID 134875) and par-bn (cadence-bn, res-wint + res-wint-bnoff; PGID 134903),
    10 cases on base 4245.
- **Readout:** `python3 -m bot.livediag.l16_report <bn1/main-s0> <bn1/main-s1> --ref res-wint:clean` plus paired CIs.
- PEKKA-1 (the BOT LEAD's) starts on 04 + 08 at ~20:30Z: keep each host ≤ 110 load.
