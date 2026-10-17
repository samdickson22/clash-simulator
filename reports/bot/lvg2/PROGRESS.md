# LVG2: PROGRESS (resume here)

Owner: cycle-model owner (Opus), for the BOT LEAD. Pre-registration: PREREG.md (main b0ef78a48). Priority: above LV2/NS2
and PT1; below deckopt3 and the finishing WINT-ACC1.

## State

- **Launched 2026-10-17T22:39Z** on 08: 3 lanes × 8 workers (lvg2/lane.sh, PGIDs 3773236 / 3773841 / 3774346).
  Admitted at 22:41Z.
- **04 lane:** lane4 (PGID 2185827, 4 workers), CLAIM_HOST=127x08, MAX_LOAD=62.
- **Jobs:** 18 (arm × k4cw/r3a), claimed as mkdir 08:bot-cycle/lvg2/claims/<job>. Out dirs are on the host that ran
  the job (08 or 04).
- **Readout:** rsync both hosts' lvg2/<job>/ to 05, then:
  `python3 05:/mpac/sdicks02/jobs/clasher/bot-cycle/lvg2/ana/lvg2_report.py ROWS official-upgrade-table.json copies-20261017c.json`
- **Affordability inputs:** copies from collection-20261017c.json (sha 86908f6f…; gold 87,640; wilds NULL). The second
  column uses the stale 74 common / 6 rare wild cards.
- **Electro Spirit:** boosted, needed=4 in file c. VERIFY THE BASE LEVEL before spending.
- **Deliver:** a one-line ranked list to the BOT LEAD and the LIVE LEAD.

## Messaging rule (Sam, standing, 2026-10-17)

Every t3_thread_send uses `mode: "steer"`; on `thread_not_sendable` resend the same text with `mode: "auto"`; never `queue`. Put this in any helper brief.

- **2026-10-17T23:17Z:** amendment 1 (Valkyrie top-up, main 26752547a).
  - lvg2/lane-v.sh runs vbase-k4cw / va8-k4cw.
  - It is started by 08:pt1/resume-v.sh (PGID 4109218) when LVG2 lane PGID 3773236 exits, then that waiter runs a PT1
    lane.
  - PT1 waiters 2 and 3 (pt1/resume-after.sh, PGIDs 4066938 / 4066980) start PT1 lanes when LVG2 PGIDs 3773841 /
    3774346 exit.
  - Valkyrie copies: 0/50 (collection c).

- **Watching/readout handed to a Sol helper (Sam: Sol first, Opus minimal):** task node:delegated-task:command%3Amcp%3A2f315658-8107-4a3c-8a46-c1e5387ddf5f%3Adelegate-task%3Acycle-owner-sol-watch-lvg2-pt1-r1. It sends the LVG2 ranked list and the Valkyrie row straight to the BOT LEAD and LIVE LEAD, watches PT1 admission, scores the PT1 readout and wakes the owner only for decisions or failures.
