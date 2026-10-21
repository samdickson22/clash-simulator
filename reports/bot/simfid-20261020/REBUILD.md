# Rebuilding HF human replays in our engine: prototype

2026-10-20, 127x05, exploration. Code: `bot/simfid/rebuild.py` (method), `rebuild_report.py` (tables), `rebuild.sh` / `rebuild_all.sh` (runs), `test_rebuild.py`. Run dir: `/mpac/sdicks02/jobs/clasher/simfid-20261020/rebuild/`. Sample manifests, the corpus scan and the full summary are in `reports/bot/simfid-20261020/rebuild/`. Nothing was trained, deployed or run on 04/08, the Mac, or an emulator. All compute ran at `nice 15` with 30 workers or fewer. MemAvailable never dropped below 100 GiB.

## Verdict

The pipeline works end to end, is deterministic, and costs about 4.9 CPU-s per match. On this engine, though, the rebuilt trajectories are not faithful human states:

- **Winner agreement is no better than a constant guess.** It is 59.1% on 1,000 random replays, below the 62.1% you get by always predicting a source-team win. On the Oct 4 sample it is 31/50, against Oct 4 native 41/50 and always-team 38/50.
- **Matches end early.** In 58% of matches our engine finishes before the source does, leaving 24% of source events pending.
- **Nothing qualifies as faithful-supported.** Every sampled match uses an evolution, hero, unsupported champion ability or non-Princess tower before its end. The median faithful prefix ends at tick 221 (11 s).

Opening-hand inference matters a lot compared with no inference: card-unavailable drops from 5,599 to 635 events on the 1,000. Which consistent assignment is chosen hardly matters (993/999 identical runs). Real levels matter for HP (MAE 1,255 vs 1,676 at L11) but barely for winners.

## Method

**Source.** VanguardX101/IL_Replay, rev `059d43a0`, 52 shards, 252,238 matches (local hash-verified copy at `/mpac/sdicks02/tmp/clashai-research/.../L67/hf/replays`). Each payload gives:
- both 8-card decks with a form suffix (`-ev1`, `-hero`) and a level per card;
- the support tower card and its level;
- every `play_card` (20 Hz tick, `native_world_units` x/y) and `activate_ability` (tick plus 1–2 non-authoritative `ability_source_candidates`);
- the result, crowns, and final tower HP.

`form_at_play` is `unknown` on all 16,981,965 plays, so the source never says whether a given play was evolved. Seat 0 is `team`, at the bottom (y < 16). Seat 1 is `opponent`. Coordinates go straight to `Position(x/1000, y/1000)`. The parse is independent of P16/C56, but uses the same field conventions as `clasher.rl.human_replay_demonstrations.parse_il_replay_record`.

**Levels.** HF `level` is the displayed level (1–16), which is also the unit our engine's `card_levels` / `tower_level` use. Evidence from the full-corpus scan (`rebuild/scan.json`, 4,035,808 card entries): the minimum level per rarity is Common 1, Rare 4, Epic 6, Legendary 9, Champion 11, with 0 entries below that rarity's first displayed level. A rarity-relative encoding (the native `sp.l` convention) would put Legendaries at 0–7, and none appear. This also agrees with the Oct 4 pass, which converted HF level to native via `l = level − rarity start`.

Matches with a missing, zero or impossible level are rejected, never defaulted to 11. That is 947 matches (0.38%) corpus-wide and 1 of the random 1,000. Tower level 0 alone accounts for 1,861 side entries.

The engine has one tower level per seat, shared by King and Princess. The source gives only the support card's level, so it is used for both. King level is therefore an assumption.

**Forms and supports** (`classify`):
- Evolutions and heroes are not implemented in the engine (`has_evolution` is metadata only).
- Towers are Princess-only: Dagger Duchess, Cannoneer and Royal Chef are not modelled.
- Spirit Empress runs as the 3-elixir ground form (`MergeMaiden_Normal`). Which form was played is not in the source.
- Champion abilities are probed per engine tree (`ability_champions()`). In rt-live16402b-r3 only Archer Queen, Goblinstein, Mighty Miner and Skeleton King activate. Boss Bandit, Golden Knight, Little Prince and Monk do not.

Every unsupported element runs as its base card or as Tower Princess. The match is labelled `base-form-substitution`, and `faithful_prefix_end_tick` records the earliest of:
- the first play of an evolution, hero or approximated card;
- tick 0, if either side has a non-Princess tower;
- the first ability event the engine cannot execute.

Only a match with none of these is `faithful-supported`. No unsupported element is silently substituted and called faithful.

**Opening hand and queue** (ClashAI's idea, implemented independently):
- Per side, all 70 × 24 = 1,680 (opening-hand set, queue order) pairs are run through the ordinary cycle over the side's whole play sequence (played card to the back of the queue, queue front into the hand). Inconsistent pairs are rejected.
- Our engine cycles Champions ordinarily (post-October-2025 rule, `PlayerState.play_card`) and Mirror is an ordinary deck card. The data agrees: 1,998/1,998 sampled sides, and all 1,200 sides in a 600-match probe (452 of them champion-deck sides), have at least one consistent pair. No special cycle had to be modelled, and nothing was classified `unsupported-cycle`.
- The chosen pair is the first consistent one in a fixed enumeration (`itertools.combinations` of the source deck list, then `permutations` of the rest). It is never ranked by outcome.
- Setup is a one-time `PlayerState(hand=…, cycle_queue=…)` before tick 0. Hand-slot order doesn't matter because the engine addresses hand cards by name.

**Injection.** Each source event is attempted when engine tick = source tick + offset, with offset frozen at 0 (see below), in source order. Nothing is forced. Each rejection is recorded:
- `not_in_hand` / `refill_pending` (together: card-unavailable);
- `elixir`;
- `placement`;
- `mirror_unresolvable`;
- `ability_unsupported_form` (hero ability);
- `ability_unsupported_engine` (Champion without an engine ability);
- `ability_ambiguous` (two live candidates);
- `ability_unavailable`.

The strict tier (`main`) never retries. The `slack40` tier retries elixir, refill-pending and ability-unavailable rejections every tick for up to 40 ticks, holding that side's later events behind the retried one. The run ends at the engine's own terminal (cap 7,200 ticks); events left over are `pending_at_terminal`. A match is `clean` only if nothing was rejected and nothing was pending.

**Scoring.**
- The source winner comes from the `team` result.
- Crowns are compared as an exact pair.
- HP is compared lane-invariantly per seat: King plus the sorted Princess pair. A fallen King zeroes all three, which is the source convention.
- `six-HP` means all six values equal. `HP MAE` is the mean over the six absolute errors.
- Engine RNG is `random.Random(0)`. A repeat run is bit-identical (50/50 identical terminals and receipts).

**Tick convention.** Measured once on a separate 40-match discovery set (`discovery40.json`: seed 1020, disjoint from both evaluation samples) under the strict main tier. The predeclared criterion was the fewest legality rejections (card-unavailable + elixir + placement + ability-unavailable); outcome is not used, and ties go to the smallest |offset|.

| offset | −2 | −1 | 0 | +1 | +2 |
|---|---|---|---|---|---|
| legality rejections (of 2,881 events) | 63 | 53 | 53 | 53 | 53 |

A uniform shift only translates the trajectory: terminal ticks move by exactly the offset, with identical outcomes. Only −2 adds rejections. **Offset 0 is frozen** (`DEFAULT_OFFSET`). Two independent checks:

- **Elixir bound.** Starting at 6.0 elixir on engine tick 0, the elixir-feasibility lower bound over 149,135 early Ranked, non-Collector plays has its bulk edge between −5 and 0. The remaining long tail comes from extra-elixir effects such as Elixir Golem.
- **End-of-game boundary.** The latest source command in the corpus is tick 5979, while our engine accepts commands up to 6000. Some regulation-length games carry commands at 3603–3617. These boundaries are not explained by a single constant; see Limitations.

## A. The Oct 4 50-match sample

The sample was reproduced from `study.py prepare()`'s rule (20 evenly spaced rows plus 30 greedy coverage additions, ties to the earliest row) applied to HF `part-000000` (SHA `9f612709…`, the pinned shard-0 hash). The Oct 4 `sample-inventory.json` was not retained on 05, so the indices could not be compared directly. Every documented property matches exactly: 3,772 events, 122 base cards, 180 card/form labels plus 4 towers, 50 evolution decks, 42 hero decks, 49 matches with ability events, 10 mixed-level matches, 6 non-Princess matches, levels 11–16, and rows 0 and 526 present. Indices are in `rebuild/native50.json`.

| run | winner | crowns | six-HP | HP MAE | all commands injected | card-unavail. | ability rejected | pending events |
|---|---|---|---|---|---|---|---|---|
| Oct 4 native, arbitrary order (baseline) | 28/50 | 16/50 | 1 | 1459.66 | 1/50 | 301 | 22 | 1,150 |
| Oct 4 native, first-use order | 40/50 | 37/50 | 2 | 663.06 | 26/50 | 13 | 4 | 411 |
| **Oct 4 native, first-use + real levels** | **41/50** | **39/50** | **2** | **622.78** | **28/50** | 13 | 3 | 400 |
| ours (rt16402b-r3), source deck-list order, real levels | 26/50 | 11/50 | 0 | 1724.72 | 0 (plays: 1) | 347 | 126 | 1,157 |
| ours, first-use order, real levels | 31/50 | 20/50 | 1 | 1099.93 | 3 (plays: 15) | 32 | 133 | 809 |
| ours, L11 normalized, inferred hand | 30/50 | 19/50 | 0 | 1680.17 | 2 (plays: 14) | 35 | 133 | 807 |
| **ours, inferred hand + real levels, strict (`main`)** | **31/50** | **20/50** | **1** | **1099.93** | **3 (plays: 15)** | **32** | **133** | **809** |
| ours, `main` + 40-tick slack | 30/50 | 19/50 | 1 | 1129.38 | 3 (plays: 15) | 36 | 133 | 809 |
| ours, last consistent candidate (diagnostic) | 31/50 | 20/50 | 1 | 1099.93 | 3 | 32 | 133 | 809 |
| ours, src-root engine (`src/clasher` + root gamedata), `main` | 32/50 | 25/50 | 1 | 1137.92 | 4 (plays: 17) | 32 | 132 | 846 |

How to read the table:

- **"All commands injected"** is our `clean`. "plays" counts matches where every *play* was injected and nothing was pending, with ability rejections excluded. Our engine rejects 119 hero and unsupported-champion abilities, which the native client executes, so ability rejections make up most of our non-clean matches.
- **Main tier totals:** 2,777 of 3,772 events injected (73.6%); 32 not in hand; 3 elixir; 18 placement; 133 ability.
- **Null baselines:** always-team-wins is right 38/50, and the most common crown pair (1-0) is right 29/50.
- **Hand inference vs no inference.** Inference against a no-inference order (source deck list) cuts card-unavailable from 347 to 32 and raises winner agreement from 26 to 31. First-use order is itself a consistent assignment here: its plan differs from `main` in all 50 matches, yet the terminals and receipts are identical. The same holds for the last candidate. Any assignment that satisfies the ordinary cycle puts every source card in hand at its play time, so the choice among consistent assignments only changes unplayed hand contents, i.e. observation features.
- **Levels.** Real vs L11 changes HP MAE (1,100 vs 1,680) and six-HP, but winners and crowns move by only 1.
- **Remaining gap to native.** It is mostly early engine terminals (30/50 matches; 809 events pending), tower troops (2/6 winners) and missing hero/evolution mechanics. Of the 30 early terminals, 11 ended at 3601 on a regulation crown lead where the source went on, 11 ended on a sudden-death crown and 8 on a King kill.

## B. 1,000 random replays from the full 252,238

Selection: `random.Random(20261020).sample` over the concatenated shard rows, excluding the native-50. Refs and tags are in `rebuild/random1000.json`. 999 ran; 1 was rejected `level-incomplete`.

**Consistency and ambiguity**

- 1,998/1,998 sides (999/999 matches) have at least one consistent ordinary-cycle assignment.
- Candidates per side: 65–256 for 1,988 sides and 257–1,680 for 10. The median is 256. No side has a unique hand set or a fixed queue position.
- After four plays the hand is just the deck minus the last four played cards, so only the first few plays constrain the opening. The opening stays ambiguous almost everywhere, but in our engine this is outcome-irrelevant: `main` vs last candidate gives 993/999 bit-identical runs and 997/999 identical winners. The 6 differences are refill-timing edge cases.

**Forms, supports and tiers**

| | matches |
|---|---|
| evolution in a deck (played) | 1,000 (997) |
| hero in a deck (played) | 928 (918) |
| non-Princess support tower | 144 |
| approximated card (Spirit Empress) | 20 |
| any unsupported or ambiguous ability event executed | 758 |
| `faithful-supported` | **0** |
| `base-form-substitution` | 1,000 (median faithful prefix ends at tick 221; 144 at tick 0) |

Corpus scan for comparison: evolution decks 252,138/252,238, hero decks 237,037, non-Princess support side entries 32,789 (Cannoneer 4,445, Duchess 14,258, Chef 15,269). Event kinds: 16,981,965 plays and 854,195 abilities. There is no unknown card slug: all 122 base slugs map to an engine card.

**Commands and outcomes**

| config (rt16402b-r3) | winner | crowns | six-HP | HP MAE | clean | plays complete | card-unavail. (matches) | elixir | placement | ability rej. | pending events (matches) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **main** (strict) | **590/999 (59.1%)** | **358 (35.8%)** | 8 | 1254.99 | 69 | 269 | 635 (209) | 138 (110) | 358 (217) | 2,169 (813) | 17,088 (582) |
| slack40 | 585 (58.6%) | 360 (36.0%) | 8 | 1248.14 | 71 | 281 | 516 (185) | 79 (65) | 343 (212) | 2,182 (815) | 16,870 (580) |
| first-use order | 591 (59.2%) | 359 (35.9%) | 8 | 1254.25 | 69 | 269 | 631 (208) | 138 | 358 | 2,169 | 17,073 |
| L11 normalized | 582 (58.3%) | 352 (35.2%) | 1 | 1676.27 | 67 | 279 | 635 (210) | 138 | 360 | 2,188 | 16,866 |
| source deck-list order | 561 (56.2%) | 262 (26.2%) | 3 | 1607.44 | 4 | 12 | 5,599 (961) | 96 | 299 | 1,940 | 22,738 (665) |
| src-root engine, main | 568 (56.9%) | 344 (34.4%) | 7 | 1253.97 | 68 | 288 | 582 (196) | 103 | 366 | 2,177 | 16,283 (564) |

Notes on the main tier:

- **Injection.** 49,941 of 70,329 source events (71.0%) were injected.
- **Ability rejections.** Of 3,376 source ability events, the rejections break down as: 1,494 hero form, 380 Champion without an engine ability, 137 ambiguous, 158 unavailable.
- **Null baselines.** Always-team-wins is right 621/999 (62.1%); the most common crown pair (1-0) is right 423/999.
- **Subsets.**
  - Princess-only matches: 504/855 winners (58.9%). Non-Princess: 86/144 (59.7%).
  - Matches with no unsupported or ambiguous ability: 143/228 (62.7%).
  - Matches with every play injected and nothing pending: 207/269 winners (77.0%), 118 crowns, 5 six-HP. This subset is selected by agreement-correlated success, so it is not an unbiased estimate.
  - `clean`: 60/69 winners.
- **Early terminals.** 582 matches had pending events at the engine terminal: 244 ended at the 3601 regulation boundary with a crown lead while the source continued, 171 on a sudden-death crown, and 167 on a King kill.

**Throughput.** Mean 4.86 CPU-s per match (p95 9.0) single-threaded, engine plus inference. Inference is negligible. 1,000 matches take 174 s wall on 30 workers, about 5.7 matches/s. Extrapolated to 252k matches: about 340 CPU-hours per configuration, or about 11 hours on 30 workers. That is engine-only, with no observation capture.

## Limitations

- **No source seed, patch or version.** HF strips dates and client/content versions. The rt-live16402b-r3 engine is a reimplementation pinned to 16.402 data with the L11-era T1 calibration (not the newer calibration being ported in parallel). Combat outcome agreement is bounded by engine accuracy, not just by reconstruction.
- **Forms are not supported.** Evolution and hero forms, three support towers, the Spirit Empress form choice and four Champion abilities are missing. On this corpus that leaves the faithful tier empty, so every outcome number here is base-form substitution. A faithful-prefix tier (states before `faithful_prefix_end_tick`) is recorded per match, but its median length is 11 s.
- **Ability attribution is weak.** Source ability events carry no authoritative source. Two-candidate events are resolved only when exactly one candidate is alive in our engine, and they are rejected otherwise.
- **Tick boundaries are unresolved.** Offset 0 minimises rejections and matches the elixir edge. The source's command cut-off (tick 5979 vs our 6000) and its post-180 s commands in regulation-length games point to native end-of-game timing that our engine does not reproduce; this is a candidate cause of the 3601 early terminals. Pending events are counted as failures, never clipped.
- **King level is unknown.** It is taken as the support card's level, and the engine has one level per seat.
- **Slack is incomplete.** Slack only covers elixir, refill and ability timing; placement and card-unavailable rejections are never retried. Even with 40 ticks, 79 elixir rejections remain.
- **Native comparison is aggregate only.** The Oct 4 per-match native results are not on 05, so table A compares aggregates, not paired matches.
- **Hand ambiguity remains a policy-feature leak.** It does not move our engine's trajectory, but which unplayed cards sit in hand vs the queue is unidentified (FIDELITY.md). An actor label must not depend on it.

## Reproduction

```bash
cd <this checkout>
RT=/mpac/sdicks02/jobs/clasher/simfid-20261020/rt-live16402b-r3
RD=/mpac/sdicks02/jobs/clasher/simfid-20261020/rebuild
S="bot/simfid/rebuild.sh $RT/src $RT Fireball,Poison"
$S scan --workers 16 --out $RD/scan.json
$S select native50 --out $RD/samples/native50
$S select random --n 1000 --seed 20261020 --exclude $RD/samples/native50.json --out $RD/samples/random1000
$S select discovery --n 40 --seed 1020 --exclude $RD/samples/native50.json $RD/samples/random1000.json --out $RD/samples/discovery40
for o in -2 -1 0 1 2; do $S run --sample $RD/samples/discovery40 --config main --offset $o --out $RD/discovery/main-off$o.jsonl --workers 30; done
bot/simfid/rebuild_all.sh $RD          # every A/B run on both engines + report.json / report.md
# another engine (e.g. the calibrated engine-cards/py tree): ENGINES="name:SRC:ROOT:CROWN" bot/simfid/rebuild_all.sh $RD
CLASHER_ROOT=$RT PYTHONPATH=$RT/src:. python -m pytest -q bot/simfid/test_rebuild.py   # 11 tests
```

The engine is whatever `clasher` package is first on `PYTHONPATH`, with gamedata from `CLASHER_ROOT`. Every result line records `engine_id` (resolved `clasher/__init__.py`, root, crown pin).

## What's left

1. Re-run A and B on the calibrated engine-cards/py tree once it lands (`ENGINES=...`).
2. Diagnose the 58% early terminals, starting with the native regulation/overtime end timing and command cut-off (5979 vs 6000) and tower damage (King kills 167).
3. Engine support for evolutions, heroes, the three support towers and the four missing Champion abilities. Without it, a faithful tier on HF data does not exist.
4. If the native sandbox path proceeds, pair per-match against native receipts. Use this harness as the "our engine" column, scoring each prefix only up to its divergence point.
