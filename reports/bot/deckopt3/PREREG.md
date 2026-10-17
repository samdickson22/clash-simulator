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
