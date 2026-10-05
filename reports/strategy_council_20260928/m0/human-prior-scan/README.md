# IL_Replay human-prior feasibility scan

This scan tested whether the public IL_Replay corpus can serve as a rough human prior: what cards do, and when people play them. Following Sam's guidance, it substitutes base forms for evo/hero variants, normalizes levels and ignores balance drift. Nothing was fitted. The scan did not touch the pilot runs, runtime snapshots or the emulator. Every job ran single-threaded under `nice -n 15`.

## Data located

- **IL_Replay** (`VanguardX101/IL_Replay`, revision `059d43a0…`): only shard 0 (5,000 matches) existed on disk, at `artifacts/worktree-data/clasher-event-policy/reports/external_reel_DdMGvYLsyL_20260913/sample-part-000000.parquet`. To scan the full corpus, the other 51 replay shards were streamed from the pinned HF revision into memory. Each was checked against the manifest SHA-256, parsed, and discarded; no raw shard was saved. All 252,238 matches were covered (`scan_shards.json`).
- **KataCR**: `datasets/external/Clash-Royale-Replay-Dataset` (347 `.npy.xz` episodes, 4.2 GB; groups `fast_hog_2.6` and `golem_ai`) and `datasets/katacr_hog26_human_v1.npz` (383,670 rows). These are camera-derived. Entities have neutral HP, evo forms were mapped to base, and only one side is recorded.
- **TV-Royale**: many small `datasets/tv_royale_*` archives (for example 182 chronological sequences and 148/37 replay-disjoint train/holdout IDs), plus 58 YouTube causal-pipeline manifests. These sources are sparse, one-perspective and vision-derived; see `../human-audit/README.md`. Neither KataCR nor TV-Royale provides two-sided timed placements with results. IL_Replay does.

## 1. Record format (IL_Replay `replays/*.parquet`, one row per match)

The columns are `result` (victory/defeat/draw, from the team side), `team_crowns`, `opponent_crowns`, `battle_type`, `game_mode` and `payload_json`. The payload contains the following.

- **Both decks**: 8 × `{card_key, level, name}` per side. Forms appear in the key: `-ev1` for evo and `-hero` for hero. Levels use the current scale. Slot levels are 16 in 3.41M cases, 11 in 562k (capped modes), and 12–15 in 49k. There is also a tower troop per side: princess 469k, royal-chef 15k, dagger-duchess 14k, cannoneer 4k.
- **Result**: crowns, result, `final_tower_hitpoints` per side (king, left, right), elixir leaked, and duration in seconds.
- **Events**: these come from both sides. A `play_card` event has `side`, `card_key`, `replay_tick_20hz` (exact 20 Hz tick) and `native_world_units` x/y in millitiles (team at the bottom, y < 16000). `form_at_play` is always `unknown`. `activate_ability` events (18.9k in shard 0) have a tick and a side but no authoritative source.
- **Not present**: intermediate state, tower-HP timelines, hands, elixir, player identity, dates and patch.

## 2. Supported cards (`supported_cards.json`)

The corpus uses 122 base cards (180 keys counting forms; 42 base cards occur as evos and 16 as heroes). Each slug is mapped to gamedata in `card_map.py`. Three support scopes were checked:

| Scope | Cards | Definition |
|---|---|---|
| **P16** | 16 | Pilot roster (Archers, Cannon, DarkPrince, Fireball, Giant, Goblins, HogRider, IceGolem, IceSpirit, Knight, Log, Musketeer, Prince, Skeletons, Tesla, Zap) |
| **G66** | 66 | `training_decks/simple_gym_supported_v1.json`, the tensor simple-Gym support profile (includes 15 of the P16 cards; Goblins is not in it) |
| **S117** (JSON key `s120`) | 117 | Scalar engine. `deploy_card` accepts the card at L11 and the defining effect was observed in `card_smoke.py` / `spell_probe.py` |

**S117 list** (`*` = evo and/or hero forms in the corpus that are substituted by base): archer-queen, archers\*, arrows, baby-dragon\*, balloon\*, bandit, barbarian-barrel\*, barbarian-hut, barbarians\*, bats\*, battle-healer, battle-ram\*, berserker\*, bomb-tower, bomber\*, boss-bandit, bowler\*, cannon\*, cannon-cart, clone, dark-prince\*, dart-goblin\*, earthquake, electro-dragon\*, electro-giant, electro-spirit, electro-wizard, elite-barbarians\*, elixir-golem, executioner\*, fire-spirit, fireball, firecracker\*, fisherman, flying-machine, freeze, furnace\*, giant\*, giant-skeleton, giant-snowball\*, goblin-barrel\*, goblin-cage\*, goblin-demolisher, goblin-gang, goblin-giant\*, goblin-hut, goblin-machine, goblins\*, goblinstein, golden-knight, golem, graveyard, guards, heal-spirit (approximation: legacy Heal spell), hog-rider, hunter\*, ice-golem\*, ice-spirit\*, ice-wizard, inferno-dragon\*, inferno-tower, knight\*, lava-hound, lightning, little-prince, lumberjack\*, magic-archer\*, mega-knight\*, mega-minion\*, mighty-miner, miner, mini-pekka\*, minion-horde\*, minions, mirror, monk, mortar\*, mother-witch, musketeer\*, night-witch, pekka\*, phoenix, poison, prince, princess\*, rage, ram-rider, rascals, rocket, ronin, royal-delivery, royal-ghost\*, royal-giant\*, royal-hogs\*, royal-recruits\*, rune-giant, skeleton-army\*, skeleton-barrel\*, skeleton-dragons, skeleton-king, skeletons\*, sparky, spear-goblins, spirit-empress (approximation: ground MergeMaiden_Normal), suspicious-bush, tesla\*, the-log, three-musketeers, tombstone\*, tornado, valkyrie\*, wall-breakers\*, witch\*, wizard\*, x-bow, zap\*, zappies.

**Not supported**: 5 cards. These are accepted by the engine but do nothing useful:
- **No effect**: vines, void (DarkMagic) and goblin-curse do zero damage to units and towers.
- **Body only**: elixir-collector produces no elixir, and goblin-drill cannot dig into the enemy side and spawns no goblins.

Tower troops are substituted by Tower Princess. Champion bodies work; abilities are triggered by side when an ability event appears. The smoke test is shallow behaviour. It is not parity calibration.

## 3. Usable matches (`corpus_tiers.json`)

Of the 252,238 matches, all are 1v1 with two 8-card decks. 251,665 have plays from both sides, and every one of those plays has coordinates with no unmatched timeline events. Tier (a), "both decks fully supported after base substitution", is the same as "all 16 cards supported".

| Scope | (a) all 16 | (b) ≤1 unsupported per deck | (c) ≤2 per deck | (a) and both sides at L11 |
|---|---:|---:|---:|---:|
| P16 | **262** | 424 | 663 | 74 |
| G66 | **6,386** | 25,974 | 58,171 | 756 |
| S117 | **146,290** | 246,803 | 251,645 | 19,606 |

Only 7, 24 and 65 tier-(a) matches respectively have no evo or hero forms. A strict base-form requirement would therefore remove almost all the data. Most P16 tier-(a) matches are Hog 2.6 mirrors.

## 4. Coverage leverage (greedy cumulative tier-(a) matches; marginal = matches missing exactly that one card)

- **S117** (only 5 cards missing): vines adds 34,742 (cumulative 181,032), then elixir-collector 207,654, goblin-drill 225,448, void 242,139 and goblin-curse 251,665. Fixing those 5 cards makes the whole corpus tier (a).
- **G66, top 10**: mighty-miner 8,687, berserker 11,185, skeleton-army 13,732, elite-barbarians 16,153, phoenix 17,900, lightning 19,627, furnace 21,637, goblin-hut 25,615, electro-giant 27,308, goblin-cage 29,407.
- **G66, next 10**: goblinstein 31,535, skeleton-dragons 33,592, elixir-collector 37,665, barbarians 39,890, wizard 42,043, golden-knight 44,208, executioner 46,416, goblins 50,016, zappies 53,393, mother-witch 56,598.
- **G66, top marginal**: mighty-miner 2,301, berserker 2,156, skeleton-army 1,717, elite-barbarians 1,309.
- **P16, top 10**: electro-spirit 361, x-bow 503, berserker 594, rocket 691, lightning 724, elite-barbarians 739, minions 756, firecracker 770, earthquake 811, mighty-miner 1,294.
- **P16, 11 to 20**: barbarian-barrel 1,780, furnace, royal-hogs, goblin-hut 2,057, royal-ghost 2,816, wizard, bomb-tower, goblinstein 3,477, valkyrie, baby-dragon 3,774.

## 5. Open-loop re-simulation (`resim_pilot.py`, `resim_*.json`)

The re-simulation replays both sides' recorded placements at their exact ticks in the scalar engine: L11, base forms, princess towers, hand cycle reconstructed from first-play order. It then compares the result at the recorded end time.

As a control, each match keeps its opponent's stream but takes the team's deck and placements from a different match.

| Run | n | Winner agreement | Crowns exact | 6-tower up/down agreement | Median first contradiction (fraction of match) |
|---|---:|---:|---:|---:|---:|
| P16 pilot | 20 | **0.70** | 0.50 | 0.74 | 0.88 |
| P16 pilot control | 20 | 0.45 | 0.05 | 0.54 | 0.26 |
| P16, all tier (a) | 262 | **0.65 ± 0.06** | 0.49 | 0.78 | 0.97 (118 never contradicted) |
| P16 control | 262 | 0.52 | 0.02 | 0.54 | 0.27 |
| G66 | 100 | 0.64 ± 0.09 | 0.49 | 0.75 | 0.92 |
| G66 control | 100 | 0.49 | 0.03 | 0.52 | 0.26 |
| S117 | 100 | 0.68 ± 0.09 | 0.42 | 0.73 | 0.89 |
| S117 control | 100 | 0.43 | 0.02 | 0.52 | 0.27 |

- The engine accepted 99.4–99.8% of recorded placements.
- Hand forcing was needed for 0.15–0.6% of plays.
- Elixir top-ups were needed for fewer than 0.15% of plays. Recorded ticks are therefore elixir-consistent with our economy, so timing alignment is sound.
- Contradiction means one of two things happened: the sim destroyed a tower that stood at the real end, or a recorded placement in the enemy half (a "pocket" placement, which proves the real tower on that lane was down) found the sim tower still up. When contradicted, the first contradiction came at a median of about 155–205 s with true actions, against about 57–70 s in the controls.
- The main errors are tower outcomes in both directions. 195 of 262 P16 matches have a real tower kill that the sim never reproduces, which fits stronger evo/hero/L16 units than the L11 base stand-ins.
- The contradiction time is an upper bound on how long the replay stays plausible. Unit-level divergence between tower events cannot be seen.
- Caveats: the S117 pool is the first 400 tier-(a) matches (all from shard 0) and the G66 pool is the first 1,500 (shards 0–13). The team side wins 60–74% of these samples.

## Recommended path

1. Treat IL_Replay as an action and timing prior, not as state/action truth. Its decks, timing, positions and card-response context are rich. Open-loop re-simulation tracks real tower outcomes clearly above the control for the first ~75–100% of a match, but it is not faithful enough for exact relabelling.
2. Pre-train in this order. First, a behaviour-cloning prior on re-simulated observations from G66 tier-(a) matches (6.4k matches, 540k plays), cutting each match at its first contradiction. Then widen to S117 tier (a) (146k matches, 10.3M plays) once the scalar behaviour of the 51 extra cards is admitted.
3. Engine work with the best data per hour:
   - Fix vines, void, goblin-curse, elixir-collector and goblin-drill (S117 coverage 58% → 100%).
   - For G66, add mighty-miner, berserker, skeleton-army, elite-barbarians, phoenix and lightning (6.4k → 19.6k matches).
   - For pilot expansion, add electro-spirit, x-bow, berserker and rocket (262 → 691).
4. Keep forms as recorded metadata on every sample, and down-weight samples after their contradiction time.

## Files

- `card_map.py`: slug-to-gamedata map, form stripping, support classes.
- `card_smoke.py`, `spell_probe.py` (with their `.json` outputs): scalar smoke tests.
- `scan_corpus.py`: corpus stream; writes `corpus_index.jsonl.gz` (25 MB compact per-match index), `payloads_{p16,g66,s120}_tier_a.jsonl.gz` (re-sim pools, 9.6 MB) and `scan_shards.json`.
- `analyze_corpus.py` writes `corpus_tiers.json`. `build_summary.py` writes `supported_cards.json` and `summary.json`.
- `resim_pilot.py [pool] [n] [control]` writes `resim_<pool>_n<n>[_control].json`.
