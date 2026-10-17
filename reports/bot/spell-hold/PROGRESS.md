# SC1 spell-hold: PROGRESS (resume here)

Owner: cycle-model owner (Opus), for the BOT LEAD. Measurement, pre-registration and results: RESULTS.md. Code:
bot/search/spellhold.py (+ test_spellhold.py, `sh<N>` token in lopp.py / lopp_fast.py), main 57c041f97.

## Thread IDs (copy verbatim)

| who | thread id |
|---|---|
| BOT LEAD | thread:delegated-task:command%3Amcp%3A53609d4a-a2de-484a-834d-8566c6339c9f%3Adelegate-task%3Aclasher-bot-lead-20261014-r1 |
| live-diag (driver owner) | thread:delegated-task:command%3Amcp%3Ad5b57bd6-719b-4e85-a080-8b8bfc639a49%3Adelegate-task%3Abot-lead-live-diag-r1 |

## State

- **Launched 20:22Z** (job dir bot-cycle/sc1/), driver /mpac/sdicks02/jobs/clasher/bot-livediag/cadence-sc1/:
  - 04 main-s0 (shard 0/2, 24 workers, PGID 2730493);
  - 08 main-s1 (shard 1/2, 16 workers, PGID 2606859; needs the LIVEDIAG_OLD/HELPERS mirror env);
  - 04 parity par-old (tree clasher-bot-cycle-old at 9095e1baa, PGID 2730432) / par-new (57c041f97, PGID 2730469).
- **Base:** 153589845884221; pool v3 + vocab; opponents LIVE-K4CW-r16-fp, R3a; arms res-wint / res-sh5-wint /
  res-sh15-wint.
- **Early check:** the sh arms change command hashes and cast fewer spells (one sh15 case: 0 spells vs 4).
- **Readout:** paired CIs; job dir bot-cycle/sc1/measure.py per arm (tower-only casts); bot.livediag.l16_report
  (reaction, undefended, elixir at the cross).

## 2026-10-17T21:40Z: SC1 done; add-on done (RESULTS.md)

- **SC1-AB:** sh5 +0.040 [−0.029, +0.109] (borderline pass of the bar); sh15 −0.035 [−0.112, +0.042]. sh arms cut all spell
  use (Fireball −73% / −83%). Owner: no ship on this bank; a fresh-bank sh5 replication only if the BOT LEAD wants it.
- **Add-on:** bot/livediag/behaviour_diag.py + cardtable.py (main c7120d491, cf56cbf93, log param in the RESULTS commit).
  Outputs are in job dir sc1/diag/ (05; human.json on 04).
- **Proposer vs scorer:** sc1/ps/ on 04 (18 traces, ps.py, ps-out.json).
- **Sam's position:** sc1/sam/ on 04. Contents:
  - s79sh-tree (live-diag's s79 tree plus the sh token);
  - traces trace-<arm>.json, cf-<arm>.json (banked counterfactual run-cf-hold/, cf.py), cflv/lv (levels probe,
    trace_levels.py).
- **Open proposals (not run):** the prior tie-break (pt2/pt5) pre-registration in RESULTS; a level-aware K4L-R root; a
  bank-for-card root action.
- **Perception notes sent to the LIVE LEAD:** the Goblin Hut is in the packet as a SpearGoblin troop; our Cannon is
  missing from the packet at 1070–1090.
- **Nothing is running.**

## Messaging rule (Sam, standing, 2026-10-17)

Every t3_thread_send uses `mode: "steer"`; on `thread_not_sendable` resend the same text with `mode: "auto"`; never `queue`. Put this in any helper brief.
