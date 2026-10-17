# LV2: level-aware planner at ACCOUNT levels. Pre-registration (full-pool owner; written before any LV2 game)

Ordered by the BOT LEAD on 2026-10-17, with the LIVE LEAD's "dist" arm added. The live planner plans every card on both
sides at L11 (levels=None). Sam's s79-m05 replay showed L11 planning misjudging Fireball vs Barbarians at real levels.

**BASE = 1565145774864592.** Drawn with int.from_bytes(os.urandom(6),'big')<<4 on 127x08 at 2026-10-17T23:21:03Z (check_bank: disjoint), before any LV2 game.

## Code (this commit)
- **bot/search/levelplan.py** (default OFF; nothing calls it unless a driver asks): install(rt, player, seat, decks, own_levels, opp_levels, towers).
  - It finds our K4L search tier under the wrappers and applies bot.levels.match.install_planner with an 'exact' spec: MatchLevelRoot (per-level card exports, warm caches, tower curve leaf).
  - opp_levels is either a dict (the oracle: the true deck vector) or a callable card -> level used for EVERY card. The callable is what "dist" uses, so a belief-sampled hidden card's level never reveals whether it is in the true deck.
  - The opponents' planners are unchanged (L11).
- **bot/levels/root.py:** `repair_public_graph` is guarded with hasattr, exactly as bot/live/levels.py does. The live search tier's CachedResources has no such method, so without the guard every level-planned decision raised and fell back to the fast tier.
- **bot/livediag/l16_cadence.py:**
  - arm tokens `PLx` (exact) and `PLd` (dist);
  - `--plan-table` (its sha is recorded in bank.json);
  - the planner-levels record per row (status must start with 'exact', else the row fails).
- **bot/fullpool/lv2_table.py → reports/bot/fullpool/lv2/opp-levels-dist.json** (sha256 81e1f4b0c6ef7974ff790f3a5535ff36e931d37f61c6f77e897a147c8bf2c9f9).
  - Source: the s73–s79 Battle Logs (/mpac/sdicks02/scratch/live-lead-share/opponent-decks-20261017-s7[3-9]-royal-arena.jsonl, 87 battles at ~1,900–2,200 trophies). s79 was included because the table was not yet committed when it landed.
  - The 42 battles whose run is one of the A/B's 43 case rows are excluded, leaving 45 battles.
  - Per card: the median logged level (half up) when n ≥ 3 (33 of 39 cards). Otherwise our CURRENT level of that card + the median offset (+1) if it is in our deck, else our deck median (7) + 1. King 9 (constant; not read from tower HP).
- **Live interface (for the LIVE LEAD; bot/live is unchanged):** see the levelplan.py docstring. Call install(...) per battle before LivePlayer.start, with:
  - own = collection levels for our deck;
  - opp = lambda c: dist_level(table, c, own);
  - towers = [our King, 9] in seat order.
  - No perception is needed. (LivePlayer also has its own `levels=` LevelRoot path in bot/live/levels.py. It scales only board bodies, so it is not what is tested here.)

## Pre-game checks (08, 2026-10-17)
- **Default-off parity:** 10 cases vs LIVE-K4CW-r16-fp at account levels on the 43 rows (base 0x1E5). res-lb-wintp on the dev tree vs parent main 68816487f gave 10/10 identical command hashes. 0 errors, 0 issues.
- **CPU-ms per decision** (same smoke, warm level caches, same host and job; pooled / median):
  - L11: 371 / 353;
  - exact: 448 / 428 (1.21×);
  - dist: 494 / 464 (1.33×).
  - Both are ≤ 1.5× L11, so no cheap variant arm.
  - Both level arms change play on 10/10 cases. The smoke's game outcomes are 10 cases on another bank and are not evidence.

## Design
- **Arms** (live names, serial twins, deadlines cleared, paired on every case):
  - `res-lb-wintp`: planner L11 (live);
  - `res-lb-PLd-wintp`: dist (ours true + the opponent from the table, King 9);
  - `res-lb-PLx-wintp`: exact oracle (both sides' true vectors and towers).
- **Account row (primary):**
  - Truth: our levels Valkyrie 6, Archers 8, Bats 7, Cannon 9, Fireball 6, Zap 8, MiniPekka 7, Giant 7, King 7. Opponents at each Battle Log row's logged levels and logged King (9).
  - Opponents: LIVE-K4CW-r16-fp and R3a.
  - Own deck: Sam's live deck. Opponent decks: WINT-ACC1's pre-declared set, pool v3.1 (sha256 2cff081966197616e9e99cdd34e79eb08737d02b16ddd7b704156cf637ae5850) strata acc = the 43 rows of pools/wintacc1-rows.json (sha256 d6ff4a44f02596383516dd277581a9a6ba58ab29f4f687af942bbc842964b0dc): King 9, full levels, no Goblin Hut.
  - 300 cases per opponent, so 1,800 games.
- **L16 row (sanity):** L16 both sides, towers 16/16; planner L11 vs exact (= L16); vs LIVE-K4CW-r16-fp; the same strata; 100 cases, so 200 games. Expected ≈ 0.
- **Engine:** RoyaleSim 16.402, noise clean, vocab vocabv3/vocab-full.json, runtime live16402b-r3. CLASHER_LEVELS_CACHE = $J/level-configs (own cache).
- **Hosts:** filler lines on 04 (user-limited ≤ 70) and 08, queued after HZ1 (tier 6, below the deckopt3 / LVG2 / PF1 / PT1 claims).
  - Account row: --shard k/30 (60 games per block, 10 workers, lease 13). L16 row: --shard k/5.
  - A shed block re-runs into <out>-rN. Rows are deterministic; duplicates must match and count once.

## Pre-registered decision (bootstrap 95 % CI over cases, 4,000 draws, seed 0; bot/fullpool/hz_report.py)
- **Ship rule (LIVE LEAD), applies to dist vs L11, vs LIVE-K4CW-r16-fp, account row:** ship if the CI lower bound > 0, or if the CI lower bound ≥ 0 with point > +0.02.
- **Also reported:**
  - exact − L11 (the upper bound) and dist − L11, pooled and per opponent;
  - the L16 row exact − L11;
  - CPU-ms per decision per arm; reaction p50/p90; undefended share; elixir at the enemy's cross; wincon-spend and idle-play shares.
- No early stopping. All rows are read together once complete.
