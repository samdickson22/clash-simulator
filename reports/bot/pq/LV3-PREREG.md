# LV3: revealed opponent levels in the planner (PLr). Pre-registration (play-quality owner, exploration)

Registered before any LV3 game. BASE **2890364282531200**, drawn on 127x04 at 2026-10-18T03:27:43Z with
`int.from_bytes(os.urandom(6),'big')<<4` (check_bank: disjoint).

## Why
LV2 (reports/coordinator/readouts/lv2-20261018.md, old Giant deck): dist planning vs K4CW-fp at account levels
+.037 [−.017, +.090] (fails), exact-level oracle +.083 [+.023, +.140]. A card's level is public once it is played
(level badge; the unit's level in the client's public unit data), so a deployable arm sits between them.

## Change
Arm `PLr` (bot/search/revealed_levels.py + l16_cadence, default off): bot.search.levelplan.install with an opponent
level callable = the LV2 dist table (reports/bot/fullpool/lv2/opp-levels-dist.json, sha256 81e1f4b0…) for cards not
yet played, the card's true level from the moment it appears in the public enemy play stream; the opponent King at its
true level (public). Our cards at our true levels. True levels are prewarmed before play; a reveal that changes a level
rebuilds the root's level config once. Mirror copies on the board keep their rebuilt level (documented limit).

## Design
- Driver l16_cadence `--own-deck` live Hog deck, `--levels account`, ours Skeletons 7, Archers 8, Valkyrie 7, Cannon 9,
  Fireball 7, Zap 9, ElectroSpirit 8, HogRider 8, King 7; opponents their logged levels and King.
- Pool: LV2's battlelog-pool-v3.1 (reports/bot/live-diag/pools/battlelog-pool-v3.1.jsonl, sha256 2cff0819…), LV2's
  43 rows (strata `acc=92,…,159`, the rows excluded from the dist table). Vocab vocab-full.json.
- Opponents LIVE-K4CW-r16-fp (primary) and R3a, 300 paired cases each. Arms `res-lb-wintp` (L11 planner, live) and
  `res-lb-PLr-wintp`. 1200 games, 04/08, bot/pq/l16.sh.

## Prediction and ship rule
Prediction: PLr − L11 > 0 vs K4CW-fp. Ship (LV2's registered rule): vs K4CW-fp, lower 95% bound > 0, or ≥ 0 with point
> +.02; play-quality metrics not worse. Readout as RF1 (hz_report + standing metrics), plus CPU-ms per decision and
reveals per game.
