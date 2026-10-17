# DECK SEARCH v3: pre-registration (bot lead; written before any screen or claim game)

Question (Sam): "have we not unlocked new cards to change the deck, or is this the best one?" The answer is read-only
advice. Sam picks the deck; this harness never touches the account.

## Inputs
- **Collection:** the live collection.json (last observed 2026-10-17T20:22Z, 30 owned cards, gold 40,518, gems 425,
  wild cards 54 common / 4 rare, King 7). Job copy `inputs/collection-live-20261017T2022Z.json`, sha256 b4d592c1…
  All 30 owned cards are supported by the full-scope runtime and vocab (pool v3.1 manifest `supported_cards`).
- **Upgrade costs:** the official rarity-aware table (bot-deckopt2 `official-upgrade-table.json`, sha256 08a1040a…).
- **Opponent pool:** Battle Log pool v3.1 as is (sha256 2cff0819…, 160 rows / 95 distinct). Only the **69 rows with
  logged card and King levels** (s69–s78, the current-arena decks) can be played at logged levels, so every row
  draws from these 69 rows. The 91 v1 rows (s1–s27) have no levels and are not used.
- **Our player:** `res-wintp` in live-diag's driver = the live LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-wint, deadlines
  cleared (serial twin), exactly as in PEKKA-1.
- **Driver:** live-diag's `bot/livediag/l16_cadence.py` unchanged (sha256 174b70bb…, the PEKKA-1 copy), called by
  `bot/deckopt3/driver.py`. One bank entry = (case, deck); every deck arm plays every case. Source tree: PEKKA-1's
  `clasher-bot-livediag-par-7df775763`. Hosts 04 / 08, cpu_job leases, nice 15.

## Levels
- **Account rows (A, B):** each card at its **reachable level**: the highest level it reaches from its held copies plus
  gold, with no wild cards (the 4 rare wilds stay reserved for Valkyrie) and no gems. Sam's eight cards have no upgrade
  completable from held copies, so they play at their current levels (Valkyrie 6, Archers 8, Bats 7, Cannon 9,
  Fireball 6, Zap 8, MiniPekka 7, Giant 7). BabyDragon (epic, 184 copies) is capped at L10 (14,400 gold). King 7.
  Opponents play at their logged levels and King. The vector is `inputs/our-levels.txt`:
  `Archers=8,Arrows=8,BabyDragon=10,Barbarians=6,Bats=7,BattleRam=6,Bomber=5,Cannon=9,ElectroSpirit=7,FireSpirits=4,Fireball=6,Giant=7,GoblinCage=7,GoblinHut=5,Goblins=6,InfernoTower=7,Knight=3,MegaMinion=6,MiniPekka=7,Minions=6,Mortar=6,Musketeer=5,Rocket=5,SkeletonDragons=7,Skeletons=7,SpearGoblins=7,Tombstone=5,Valkyrie=6,Wizard=7,Zap=8,King=7`.
  Data caveat: the collection records BabyDragon as "level 3", below the epic start (L6); its `needed` = 2 matches an
  epic's first step, so it is treated as L6 with 184 copies. To be verified at the next collection read.
- **L16 rows (C, D):** every card and tower L16 on both sides (Sam's standing rule for play evals).

## Stage 1: screen (selection only; never a claim)
- **SCREEN BASE = 37907432851555**, drawn with os.urandom(6) at 2026-10-17T20:49:05Z.
- 48 cases (seed = BASE + i, seat = i % 2, a pool row drawn uniformly over the 69 leveled rows), account levels, vs
  LIVE-K4CW-r16-fp. 23 arms (`bot/deckopt3/decks.py` CANDIDATES):
  - anchors: `sam` (Valkyrie, Archers, Bats, Cannon, Fireball, Zap, MiniPekka, Giant) and `dk2` (last night's winner:
    Valkyrie, Archers, Goblins, InfernoTower, Fireball, Giant, MiniPekka, Skeletons);
  - single swaps from Sam's deck: Cannon→InfernoTower; Bats→BabyDragon; Valkyrie→BabyDragon; Zap→Arrows;
    Bats→Skeletons; Valkyrie→Wizard; Bats→SkeletonDragons; Bats→ElectroSpirit; Cannon→GoblinCage; Bats→SpearGoblins;
  - double swaps from Sam's deck: Inferno+BabyDragon(for Bats); Inferno+Arrows; Inferno+Skeletons; BabyDragon+Arrows;
    Inferno+BabyDragon(for Valkyrie);
  - swaps from dk2: Goblins→Zap; Goblins→BabyDragon; Skeletons→Bats;
  - archetypes: BattleRam + BabyDragon; Giant + BabyDragon + Inferno; Mortar siege.
- **Selection rule:** rank the 21 non-anchor arms by mean paired win difference vs `sam` on the 48 screen cases (draw =
  0.5); ties broken by lower gold cost, then by name. The top 4 go to the finals. Screen numbers are reported as
  selection evidence only.

## Stage 2: finals (claim bank)
- **FINAL BASE:** a fresh os.urandom(6) value, committed to main in this file before the first final game.
- **Arms (6):** `sam`, `dk2`, and the top 4 screened decks, all paired on the same cases.
- **Row A (deck-choice row):** 200 cases, seed = FINAL BASE + i, seat = i % 2, pool row drawn uniformly over the 69
  leveled rows (observed frequency), account levels as above vs logged levels / King, opponent LIVE-K4CW-r16-fp.
- **Row B (P.E.K.K.A / Hog weighted):** the s73–s78 share of decks containing P.E.K.K.A or HogRider is 28/52 = 0.538
  (the 69 leveled rows: 36/69 = 0.522, so A already sits close to it). B adds 100 supplementary cases (seed = FINAL
  BASE + 100000 + i), drawn uniformly over the 36 leveled P.E.K.K.A-or-Hog rows, same levels and opponent. B =
  0.538 × mean(all P.E.K.K.A/Hog cases of A and the supplement) + 0.462 × mean(the other A cases). B also reports the
  P.E.K.K.A/Hog stratum alone, and the P.E.K.K.A-only subset, per arm.
- **Row C (L16 play-strength row):** the first 150 cases of A (same seeds, seats, opponent decks), all L16, vs
  LIVE-K4CW-r16-fp.
- **Row D (weak-opponent sanity row):** the first 100 cases of A, all L16, vs R3a.
- **Size:** 6 arms × (200 + 100 + 150 + 100) = 3,300 games.
- **Statistics:** score = win + 0.5 × draw. Per arm and row, the win rate with a 95 % bootstrap CI over cases; Δ vs
  `sam` with a paired bootstrap CI over cases (10,000 resamples, seed 0; B resamples within each stratum). Every row
  is reported separately and never pooled across rows. Unclean rows are kept and listed; a case enters a row's paired
  analysis only if all its arms are clean (count reported).
- **Decision statement:** a deck "beats Sam's deck" only if its row-A Δ has a 95 % CI entirely above 0. If none does,
  the report says "no clear improvement on row A". Rows B–D are context (P.E.K.K.A matchup, play strength at L16,
  weak-opponent sanity), not a second chance at the claim.
- **Cost per finalist:** gold, copies and wild cards to reach the row-A levels from the collection, and the mean deck
  level vs Sam's 7.25.
- No early stopping; finals are read when complete (an interim count may be posted without outcomes).

## Amendment 1 (2026-10-17T20:59Z, before any final game; no screen result read)
- **FINAL BASE = 8811788417582**, drawn with os.urandom(6) at 2026-10-17T20:58:57Z. Row A / C / D seeds = FINAL BASE + i;
  row B supplement seeds = FINAL BASE + 100000 + i (driver tags `A`, `Bsup`, `C`, `D`).
- The two fixed finalists (`sam`, `dk2`) may start on the final bank as soon as a host has room, before the screen
  ends; the four screened arms join the same cases later. Entries are per (case, deck), so arms added later play
  exactly the same cases. No final result is read before all arms of a row are complete.
- Hosts: the screen runs on 04 (shards 0–9/25), 08 (10–18/25) and 01 (19–24/25, ≤ 60 load). Cross-host parity: the
  same entry on 01 and 08 gave identical command hash, state hash and play log (smoke, 20:58Z).

## Amendment 2 (2026-10-17T21:12Z, before any final game; the screen result not read)
- **Goblin Hut decks are excluded from the claim bank** (BOT LEAD advice after PEKKA-1): RoyaleSim's translator has no
  counterpart for the Goblin Hut garrison sprite (SpearGoblin_Dummy), so those games show our player a partial board.
  The finals draw only from the leveled rows whose deck has no GoblinHut: 69 − 11 = **58 rows** (driver
  `--exclude-card GoblinHut`). The 11 dropped rows: s70-m02, s72-m02, s72-m01, s73-m06, s74-m17, s74-m16, s74-m02,
  s76-m06, s76-m11, s76-m13, s78-m02.
- Row B weight follows the same rule: the s73–s78 P.E.K.K.A-or-Hog share without Goblin Hut decks is **26/44 = 0.591**
  (the 58-row draw for A has 34/58 = 0.586, so A and B differ little; per PEKKA-1, B mostly measures a higher
  Hog / Ram push exposure). The supplement draws from the 34 P.E.K.K.A-or-Hog rows.
- The screen keeps its registered pool (all 69 leveled rows; selection only). Its ranking is also reported without
  the Goblin Hut cases, for information; the registered rule (all 48 cases) picks the finalists.
- PEKKA-1 (live-diag RESULTS §14) is cited, not re-run. Our player stays `res-wintp` (live -res-wint) for comparability
  with PEKKA-1 and the live bot; if WINT-ACC1 changes the live default, the BOT LEAD decides whether finalists re-run.

## Amendment 3 (2026-10-17T21:25Z; no screen or final result read)
- **Data correction:** the collection entry stored as "BabyDragon" (Level 3, 184/2) is the in-game card **"Minion Giant"**
  (LIVE LEAD fresh zoom 21:17Z, orange rarity strip). It is not in the pinned gamedata or the full-scope runtime, so it
  cannot be simulated. We do not own Baby Dragon. The 8 Baby Dragon screen arms (s-bd4bats, s-bd4valk, s-inf-bd,
  s-bd-arrows, s-inf-bd4valk, w-bd, a-ram-bd, a-giant-bd) are **void**. Their played rows are kept, unread.
- The three screen jobs were stopped at 21:19Z (172 games played, outcomes not read) and relaunched on the same SCREEN
  BASE, cases and shard layout, skipping the played entries (`inputs/screen-done-r1.txt`). Levels: `our-levels-v2.txt`
  (the same vector without BabyDragon).
- **Five replacement arms** (`decks.py`, decks v2 sha256 c3ec1844…): s-mm4bats (Bats→MegaMinion), s-inf-wiz4valk
  (Cannon→InfernoTower, Valkyrie→Wizard), w-wiz (dk2 Goblins→Wizard), a-ram (BattleRam, Wizard, Valkyrie, Archers,
  InfernoTower, Fireball, Zap, Skeletons), a-giant-wiz (Giant, Wizard, MiniPekka, Archers, InfernoTower, Fireball, Zap,
  Skeletons). Screen = 2 anchors + 18 candidates = 20 arms; the selection rule (top 4 by paired Δ vs sam) is unchanged.
- The fresh full collection (reports/live/account/collection-20261017.json) is pending. If it shows other identity or
  level errors among the finalists' cards, the affected arms are corrected before their final games and the change is
  logged here.

## Amendment 4 (2026-10-17T21:30Z; no screen or final result read): verified collection
- **Source:** the verified snapshot `reports/live/account/collection-20261017.json` (LIVE tree, read-only; sha256
  521030198aa00e9b8b26562f558e407decb1674dec8b82e28f1ae346c7cd26c2), copied to `inputs/`. `decks.py` now reads it.
  30 owned cards; 8 unowned (BombTower, HogRider, FlyingMachine, Pekka, Witch, SkeletonArmy, BabyDragon, Guards).
  Gold 40,518, gems 425, wilds 54 / 4 / 0 / 0 / 0, King 7. No owned epic, legendary or champion card.
- **Re-validation of every screen arm:** all 20 v2 arms use only owned cards and only cards the full-scope runtime
  supports. Excluded from the owned set: BabyDragon (not owned) and MinionGiant (runtime mapping null). The 8 Baby Dragon
  arms stay void (amendment 3).
- **Levels:** the reachable-level vector recomputed from the verified file is **byte-identical** to `our-levels-v2.txt`
  (all 29 usable cards have the same level and copies as the 20:22Z collection), so the running screen and the fixed
  final arms need no change. The `sam` / `dk2` final rows started with the v1 string, which differs only by an unused
  BabyDragon entry.
- ElectroSpirit's base level is null in the snapshot (boosted display L7). `needed = 2` matches a common at L1. With 300
  copies it reaches L7 from held copies (1,625 gold). Only `s-espirit` uses it, and the report flags this.
- **Finalists:** `sam` and `dk2`, plus the top 4 valid screen arms by the registered rule. If a selected arm is later
  found unbuildable, the next-ranked valid arm takes its place.

## Amendment 5 (2026-10-17T21:35Z; no screen or final result read): collection re-issue e218db08
- `decks.py` now reads the re-issued snapshot (sha256 e218db08763a5ef9686d3c51e7de9b7912cb2101c9df3576daf14314e5e8cfb8;
  free claims Rocket 15→65 copies, Cannon 0→300/800). Recomputed reachable vector: only **Rocket L5 → L7** moves; Cannon
  stays L9. No screen arm and no finalist uses Rocket, so **e218db08 → no change** to any deck's levels in the screen or
  the final bank. Upgrade costs in the report use this file.

## Amendment 6 (2026-10-17T21:40Z; before any final-bank result is read): live switch rule (Sam via coordinator / BOT LEAD)
Sam authorises switching the live deck if it is beneficial. The final readout applies exactly this rule:
- **Switch to deck D** if, on **row A**, the paired Δ(D − sam) has a 95 % CI lower bound > 0, **and** on **row C** (L16 vs
  LIVE-K4CW-r16-fp) D is not worse: its Δ(D − sam) point estimate is ≥ 0, or its 95 % CI includes 0.
- If several decks qualify, pick the one with the highest row-A point estimate. If none qualifies: **keep Sam's deck**.
- Rows B and D are reported and do not enter the rule.
- The report gives the winner's 8 cards, rows A–D with CIs, its upgrade cost from collection e218db08, and its
  post-switch upgrade priority at account levels. Cards with no LEVELGAIN measurement are marked unmeasured.
- At the screen interim, a deck that leads the screen decisively is named as an early call. The screen selects only;
  the claim needs the final.

## Amendment 7 (2026-10-17T22:30Z; no final-bank result read): Sam's new deck, levels, Hog, provisional read
- **Inputs changed (BOT LEAD / Sam, 22:16–22:28Z):** Hog Rider is owned. Sam upgraded cards himself (Hog Rider 8,
  Valkyrie 7, Electro Spirit ~8, boosted). He then **chose his deck: Hog Rider 8, Archers 8, Cannon 9, Skeletons 7,
  Fireball 6, Zap 8, Electro Spirit ~8, Bats 7** (`sam3`).
- **Baseline:** row A's reference arm is now `sam3`. The question is whether ANY owned deck clearly beats it under the
  amendment-6 switch rule. This is advice only. His previous Hog deck `sam2` (Valkyrie, Archers, Bats, Cannon, Fireball,
  Zap, MiniPekka, Hog Rider) and the old Giant deck `sam-giant` (= old `sam`) stay as comparison arms.
- **Stopped as stale (account levels Valkyrie 6, no Hog; played rows kept, unread):** final row A `sam/dk2`
  (final/A-fixed-08) and the row-B supplement (final/Bsup-fixed-04). The two Hog screen jobs started at 22:27Z were
  stopped before any game. Final row C `sam/dk2` (L16, level-independent) continues as comparison-arm evidence.
- **Provisional read (selection-only, labelled PROVISIONAL):** tag `prov`, SCREEN BASE cases (48), account levels
  `our-levels-prov.txt` (= v2 with Valkyrie 7, Electro Spirit 8, Hog Rider 8; all other levels unverified until
  collection-20261017b). Arms (`inputs/prov2-decks.json`): sam3, sam2, h1 (sam3 with Musketeer for Archers),
  h3 (h1 with Valkyrie for Bats), sam-giant, s-arrows (the screen leader), h-classic (Hog, Cannon, Musketeer,
  Fireball, Zap, Skeletons, Electro Spirit, Knight), h-archers (Hog, Cannon, Archers, Fireball, Zap, Skeletons,
  Electro Spirit, Valkyrie). It is read on whatever paired cases are complete at the deadline.
- **Next:** when collection-20261017b lands (42 cards, incl. epics at L6), a widened screen at its levels. Then a
  **fresh final bank** (new os.urandom base, logged here before its first game) vs `sam3` under the switch rule.
  FINAL BASE 8811788417582 is retired; its played rows stay archived, unread.
