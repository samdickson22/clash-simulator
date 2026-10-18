# Collector close — 2026-10-18T07:00:51.518574+00:00

PF1 and deck final2 both final and reported; UTC is past07:00Z. No experiment jobs, queues, refs or experiment worktrees were changed. Current origin/main`8ca80863b738f2faa2c06c9a0eafde6b05486271`; study source SHAs and frozen definitions are in each readout.

Final readouts: pf1, deck-final2, lvg2, lvg2-valk, hp1 S0/CPU qualification, hz1, lv2, perception-h31/h32/h35/h36/h37, perception-volume. Each is `<name>-20261018.md` in this directory. HZ1 includes completed s32/s39; no missing HZ1/LV2 shards.

PT1 pending: 10/16complete shards; 1728/2400raw row files, outcomes unread. Missing completion: l16-s5, l16-s6, l16-s7, acct-s5, acct-s6, acct-s7. Root127x08:/mpac/sdicks02/jobs/clasher/bot-cycle/pt1/. See pt1-20261018.md. Both pre-scoring nonoverlap checks passed; observed+201bank is PRIMARY under coordinator ruling, with+301PREREG mismatch disclosed.

P1 full GPU quality runs pending; exact paths, latest steps, age and completion metadata in hp1-20261018.md and `/tmp/clasher-results-collector/p1-status-latest.json`. NS2 is status-only in ns2-20261018.md, controller on04. No final NS2 claim.

Perception coverage gaps remain in individual readouts: h31/h32 missing old12 raw79d, volume missing new-deck and hero artifacts, candidate dedicated hero rows unscorable. h35/h36/h37 fail old12 no-bad-class gate. No detector deployment recommendation.

Local scoring/collection scripts and compact output receipts: `/tmp/clasher-results-collector/`. PT1 continuation: refresh completion metadata, require all16shards, then collect_pt1.py→score_pt1.py→write_pt1.py. Bank audit file `pt1-bank-audit.json` predates any PT1 outcome read; collection validates all actual banks and pair keys. Do not reuse retired killed shards. All remote scoring is nice19.

Hourly fleet records: fleet-20261018.md. Idle alerts were sent only after paired samples; no unreported clear stall was found in registered pending jobs.
