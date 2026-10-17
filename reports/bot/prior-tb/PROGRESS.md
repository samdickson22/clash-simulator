# PT1 / PT2 prior tie-break: PROGRESS (resume here)

Owner: cycle-model owner (Opus), for the BOT LEAD. Pre-registration: PREREG.md (main ecd42cc54, amendment 1 in
6273e0d60: f1a2 is a self-prior). PT2 design: PT2-DESIGN.md (main eaceb8b60; proposal, not run). Code: main 68816487f
bot/search/priortb.py (token pt<N>).

## Thread IDs (copy verbatim)

| who | thread id |
|---|---|
| BOT LEAD | thread:delegated-task:command%3Amcp%3A53609d4a-a2de-484a-834d-8566c6339c9f%3Adelegate-task%3Aclasher-bot-lead-20261014-r1 |
| live-diag | thread:delegated-task:command%3Amcp%3Ad5b57bd6-719b-4e85-a080-8b8bfc639a49%3Adelegate-task%3Abot-lead-live-diag-r1 |
| LIVE LEAD | thread:delegated-task:command%3Amcp%3A53609d4a-a2de-484a-834d-8566c6339c9f%3Adelegate-task%3Aclasher-live-lead-20261014-r1 |

## State

- **Priority: LOW** (below LV2, WINT-ACC1 and deckopt3; alongside HZ1). 08 only, a small worker count. Don't take
  LV2's slots on 04/08; 04 is capped at ≤ 70 load (user).
- **Job dir:** 08:/mpac/sdicks02/jobs/clasher/bot-cycle/pt1/:
  - pt1-base.txt;
  - cadence-pt1/ (driver copy);
  - smoke1/;
  - par-new/, par-old/ (parity, base 4246, account row, 10 cases vs R3a);
  - lane.sh W (claims claims/<row>-s<k>, 16 shard jobs: rows l16/acct × shard k/8; out <row>-s<k>/; prior counts in
    prior-log/).
- **Trees:** /mpac/sdicks02/repos/clasher-bot-cycle-pt1-68816487f (new) and -e686e2a6a (parent), on 04 and 08.
- **Readout:** paired normal CIs per row (pooled and per opponent; sc1/ana/paired.py logic); behaviour_diag sim per
  arm per row; l16_report; prior-log counts.

- **2026-10-17T22:09Z:** parity PASS 10/10.
- **2026-10-17T22:10Z:** PT1 launched on 08: lane1 PGID 3531103, lane2 PGID 3531521, 4 workers each.
  - Add lanes only if slots free up and LV2 doesn't need them.
  - A lane on another host needs its own claims and out dirs: claims are per host.
