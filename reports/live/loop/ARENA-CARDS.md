# Clash Royale arenas 0–10: unlocked cards vs C56

Research date: 2026-10-15. Requested by: clasher-live loop.

## Reading this file

- **C56 source:** `engine-rs/c56_controller.py` builds `CARDS = sorted(SUPPORTED_CARDS | C56_ADDED_CARDS)` from `src/clasher/rl/public_scripted_opponent.py` (16 names) and `src/clasher/rl/c56_scripted.py` (40 names). Union = **56** names, no overlap.
- **Arena lists are contested.** Sources disagree on arena numbering, trophy thresholds and several card lists (details in "Conflicts" below). The per-arena card list is the **Pocket Tactics** list (updated 2026-10-03), the freshest and most complete source I could reach. Sportskeeda and RoyaleAPI-era guides are used as cross-checks.
- **Rarity, elixir, type and body count are from model recall, not from a fetched source.** No reachable source gave these per card. `?` marks values I am least sure of. Verify against the game's gamedata before using them in the simulator.
- **Status column:** `IN_C56` means the card is in the 56-name list; `MISSING` means it is not. Name aliases that need checking are noted.
- **Training Camp** has no trophy range in the primary source (it is excluded as the tutorial arena). Starter cards are taken from one source.

## Arena table

| Arena | Trophies | Card | Rarity† | Elixir† | Type† | Ground/Air, bodies† | C56 status | Notes |
|---|---|---|---|---|---|---|---|---|
| Training Camp | 0 (tutorial) | Giant | Rare | 5 | Troop | Ground, single | IN_C56 | Starter, per Skycoach |
| Training Camp | 0 (tutorial) | Fireball | Rare | 4 | Spell | — | IN_C56 | Starter, per Skycoach |
| Training Camp | 0 (tutorial) | Princess | Legendary | 3 | Troop | Ground, single | IN_C56 | Starter, per Skycoach |
| 1 Goblin Stadium | 0–300 | Goblins | Common | 2 | Troop | Ground, multi (3) | IN_C56 | |
| 1 Goblin Stadium | 0–300 | Goblin Cage | Rare | 4 | Building | — | **MISSING** | |
| 1 Goblin Stadium | 0–300 | Goblin Hut | Rare | 5 | Building | — | IN_C56 (`GoblinHut`) | |
| 1 Goblin Stadium | 0–300 | Spear Goblins | Common | 2 | Troop | Ground, single | **MISSING** | |
| 2 Bone Pit | 300–600 | Bomber | Common | 2 | Troop | Ground, single | **MISSING** | |
| 2 Bone Pit | 300–600 | Skeletons | Common | 1 | Troop | Ground, multi (3) | IN_C56 | |
| 2 Bone Pit | 300–600 | Tombstone | Rare | 3 | Building | — | **MISSING** | |
| 2 Bone Pit | 300–600 | Valkyrie | Rare | 4 | Troop | Ground, single | IN_C56 | |
| 3 Barbarian Bowl | 600–1000 (800 in one source) | Barbarians | Common | 5 | Troop | Ground, multi (4) | **MISSING** | `AngryBarbarians` is a different card |
| 3 Barbarian Bowl | 600–1000 | Battle Ram | Rare | 4 | Troop | Ground, single | **MISSING** | |
| 3 Barbarian Bowl | 600–1000 | Cannon | Common | 3 | Building | — | IN_C56 | |
| 3 Barbarian Bowl | 600–1000 | Mega Minion | Rare | 3 | Troop | Air, single | **MISSING** | |
| 4 Spell Valley | 1000–1300 | Bomb Tower | Rare | 4 | Building | — | IN_C56 (`BombTower`) | |
| 4 Spell Valley | 1000–1300 | Electro Spirit | Common | 1 | Troop | Ground, multi (3) | IN_C56 | |
| 4 Spell Valley | 1000–1300 | Fire Spirit | Common | 2 | Troop | Ground, multi (3) | IN_C56 (`FireSpirits`) | |
| 4 Spell Valley | 1000–1300 | Inferno Tower | Rare | 5 | Building | — | IN_C56 (`InfernoTower`) | |
| 4 Spell Valley | 1000–1300 | Skeleton Tower (name conflict, see below) | ? | ? | Building? | — | **MISSING** | Sportskeeda lists "Skeleton Dragons" here instead |
| 4 Spell Valley | 1000–1300 | Wizard | Rare | 5 | Troop | Ground, single | IN_C56 | |
| 5 Builder's Workshop | 1300–1600 | Bats | Common | 2 | Troop | Air, multi (5) | IN_C56 | |
| 5 Builder's Workshop | 1300–1600 | Flying Machine | Rare | 4 | Troop | Air, single | **MISSING** | |
| 5 Builder's Workshop | 1300–1600 | Hog Rider | Rare | 4 | Troop | Ground, single | IN_C56 (`HogRider`) | |
| 5 Builder's Workshop | 1300–1600 | Mortar | Common | 4 | Building | — | **MISSING** | |
| 5 Builder's Workshop | 1300–1600 | Rocket | Rare | 6 | Spell | — | IN_C56 | |
| 5 Builder's Workshop | 1300–1600 | Zap | Common | 2 | Spell | — | IN_C56 | |
| 6 P.E.K.K.A's Playhouse | 1600–2000 | Baby Dragon | Epic | 4 | Troop | Air, single | IN_C56 | |
| 6 P.E.K.K.A's Playhouse | 1600–2000 | Goblin Barrel | Epic | 3 | Spell | — | IN_C56 (`GoblinBarrel`) | |
| 6 P.E.K.K.A's Playhouse | 1600–2000 | Guards | Epic | 3 | Troop | Ground, multi (3) | **MISSING** | |
| 6 P.E.K.K.A's Playhouse | 1600–2000 | P.E.K.K.A | Epic | 7 | Troop | Ground, single | **MISSING** | `MiniPekka` is Mini P.E.K.K.A., a different card |
| 6 P.E.K.K.A's Playhouse | 1600–2000 | Skeleton Army | Epic | 3 | Troop | Ground, multi (15) | IN_C56 | |
| 6 P.E.K.K.A's Playhouse | 1600–2000 | Witch | Epic | 5 | Troop | Ground, single | **MISSING** | |
| 7 Royal Arena | 2000–2300 | Balloon | Epic | 5 | Troop | Air, single | IN_C56 | |
| 7 Royal Arena | 2000–2300 | Dark Prince | Epic | 4 | Troop | Ground, single | IN_C56 (`DarkPrince`) | |
| 7 Royal Arena | 2000–2300 | Prince | Epic | 5 | Troop | Ground, single | IN_C56 | |
| 7 Royal Arena | 2000–2300 | Three Musketeers | Rare | 9 | Troop | Ground, multi (3) | **MISSING** | |
| 7 Royal Arena | 2000–2300 | Royal Hogs | Rare | 5 | Troop | Ground, multi (4) | IN_C56 (`RoyalHogs`) | |
| 7 Royal Arena | 2000–2300 | Royal Giant | Common | 6 | Troop | Ground, single | **MISSING** | |
| 7 Royal Arena | 2000–2300 | Royal Recruits | Common | 7 | Troop | Ground, multi (5) | **MISSING** | Sportskeeda says "Royal Guards" here |
| 8 Frozen Peak | 2300–2600 | Battle Healer | Rare | 4 | Troop | Ground, single | **MISSING** | |
| 8 Frozen Peak | 2300–2600 | Cannoneer | Rare | 5 | Building | — | **MISSING** | |
| 8 Frozen Peak | 2300–2600 | Freeze | Epic | 4 | Spell | — | **MISSING** | |
| 8 Frozen Peak | 2300–2600 | Giant Skeleton | Epic | 6 | Troop | Ground, single | **MISSING** | |
| 8 Frozen Peak | 2300–2600 | Giant Snowball | Common | 2 | Spell | — | **MISSING** | |
| 8 Frozen Peak | 2300–2600 | Ice Golem | Rare | 2 | Troop | Ground, single | IN_C56 | |
| 8 Frozen Peak | 2300–2600 | Ice Spirit | Common | 1 | Troop | Ground, single | IN_C56 | |
| 8 Frozen Peak | 2300–2600 | Lightning | Epic | 6 | Spell | — | IN_C56 | |
| 8 Frozen Peak | 2300–2600 | Vines | Rare? | 3? | Spell | — | **MISSING** | Only Pocket Tactics and one other list name it |
| 9 Jungle Arena | 2600–3000 | Barbarian Barrel | Epic | 2 | Spell | — | **MISSING** | `BarbLog` in C56 looks like the log projectile, not this card |
| 9 Jungle Arena | 2600–3000 | Barbarian Hut | Rare | 7 | Building | — | **MISSING** | |
| 9 Jungle Arena | 2600–3000 | Berserker | Rare | 2 | Troop | Ground, single | IN_C56 | |
| 9 Jungle Arena | 2600–3000 | Dart Goblin | Common | 2 | Troop | Ground, single | **MISSING** (alias check) | C56 has `BlowdartGoblin`; probably the same card, verify |
| 9 Jungle Arena | 2600–3000 | Goblin Gang | Common | 3 | Troop | Ground, multi | IN_C56 (`GoblinGang`) | |
| 9 Jungle Arena | 2600–3000 | Goblin Giant | Epic | 6 | Troop | Ground, single | **MISSING** | |
| 9 Jungle Arena | 2600–3000 | Poison | Epic | 4 | Spell | — | IN_C56 | |
| 9 Jungle Arena | 2600–3000 | Rune Giant | Epic? | 7? | Troop | Ground, single | **MISSING** | |
| 9 Jungle Arena | 2600–3000 | Skeleton Barrel | Common? | 3? | Spell? | — | **MISSING** | |
| 9 Jungle Arena | 2600–3000 | Earthquake (Sportskeeda list only) | Rare | 3 | Spell | — | IN_C56 | Not on the Pocket Tactics list |
| 10 Hog Mountain | 3000–3400 | Elite Barbarians | Epic | 6 | Troop | Ground, multi (2) | **MISSING** | |
| 10 Hog Mountain | 3000–3400 | Furnace | Rare | 4 | Building | — | **MISSING** | |
| 10 Hog Mountain | 3000–3400 | Golem | Epic | 8 | Troop | Ground, single | IN_C56 | |
| 10 Hog Mountain | 3000–3400 | Hunter | Rare | 4 | Troop | Ground, single | **MISSING** | |
| 10 Hog Mountain | 3000–3400 | Minion Horde | Common | 5 | Troop | Air, multi (6) | IN_C56 (`MinionHorde`) | |
| 10 Hog Mountain | 3000–3400 | Tesla | Common | 4 | Building | — | IN_C56 | |
| 10 Hog Mountain | 3000–3400 | X-Bow | Epic | 6 | Building | — | IN_C56 (`Xbow`) | |
| 10 Hog Mountain | 3000–3400 | Zappies | Rare | 4 | Troop | Ground, multi | **MISSING** | |

† Model recall. Not sourced.

## Per-arena MISSING count (arenas 1–10)

| Arena | Cards listed | MISSING from C56 | Which |
|---|---|---|---|
| Training Camp | 3 | 0 | — |
| 1 Goblin Stadium | 4 | 2 | Goblin Cage, Spear Goblins |
| 2 Bone Pit | 4 | 2 | Bomber, Tombstone |
| 3 Barbarian Bowl | 4 | 3 | Barbarians, Battle Ram, Mega Minion |
| 4 Spell Valley | 6 | 1 | Skeleton Tower (name conflict; "Skeleton Dragons" per Sportskeeda) |
| 5 Builder's Workshop | 6 | 2 | Flying Machine, Mortar |
| 6 P.E.K.K.A's Playhouse | 6 | 3 | Guards, P.E.K.K.A, Witch |
| 7 Royal Arena | 7 | 3 | Three Musketeers, Royal Giant, Royal Recruits |
| 8 Frozen Peak | 9 | 6 | Battle Healer, Cannoneer, Freeze, Giant Skeleton, Giant Snowball, Vines |
| 9 Jungle Arena | 10 | 6 | Barbarian Barrel, Barbarian Hut, Dart Goblin (alias?), Goblin Giant, Rune Giant, Skeleton Barrel |
| 10 Hog Mountain | 8 | 4 | Elite Barbarians, Furnace, Hunter, Zappies |
| **Total, arenas 1–10** | | **32** | 31 if Dart Goblin = BlowdartGoblin |

## Top 10 MISSING cards to add first

Ranked by earliest unlock, then how often the card shows up at low trophies.

1. **Spear Goblins** (Arena 1, Common, 2): the most-used early cycle card.
2. **Goblin Cage** (Arena 1, Rare, building): a common Goblin Gang / Goblin Cage deck piece at low trophies.
3. **Bomber** (Arena 2, Common, 2): core early splash troop.
4. **Tombstone** (Arena 2, Rare, building): common in Bone Pit and Skeleton decks.
5. **Barbarians** (Arena 3, Common, 5): core Barbarian Bowl troop.
6. **Battle Ram** (Arena 3, Rare, 4): common mid-low trophy push card.
7. **Mega Minion** (Arena 3, Rare, 3, air): common air splash.
8. **Mortar** (Arena 5, Common, 4, building): common siege building at 1300+.
9. **Flying Machine** (Arena 5, Rare, 4, air): common mid-trophy air card.
10. **Witch** (Arena 6, Epic, 5): common at 1600+; P.E.K.K.A (Arena 6) follows immediately after.

## Recent changes and version notes

- **Trophy Road rework, late 2025.** Extended the main road from 10,000 to 12,000 trophies with new arenas. gamer.org dates the update 2025-11-24. Cashify and Sportskeeda call it the December 2025 update. ([Sportskeeda](https://www.sportskeeda.com/mobile-games/clash-royale-december-2025-update-trophy-road-rework-explained), [gamer.org](https://www.gamer.org/clash-royale-trophy-road-update-2025-reach-12000-trophies-for-exclusive-rewards/)).
- **2026-02-23 client patch (Supercell's "March Update 2026").** Official post: four arenas added to the road, numbered Arena 29–32 at 12,000, 12,500, 13,000 and 13,500 trophies. Special deck slots reduced from 4 to 3. First Hero Slot now opens at **Arena 5**. Global Tournaments now unlock at **Arena 3**. Heroes no longer summon at random. The post states "new cards are coming" with no dates and no card-to-arena mapping. ([Supercell official post, dated 23 Feb 2026](https://supercell.com/en/games/clashroyale/blog/release-notes/march-update-2026/)).- **Arena numbering is not consistent across sources.** Older sources put Builder's Workshop at Arena 6 with 1,700 or 2,000 trophies. Pocket Tactics, Sportskeeda and Royale Chief put it at Arena 5 with 1,300. Supercell's post numbers the 2026 extension Arena 29–32; third-party lists name and number those arenas differently. Use Supercell's in-game Trophy Road as the authority.
- **Training Camp.** Skycoach lists Giant, Fireball and Princess as starter cards. Sportskeeda, in an older article, lists Tower Princess at Arena 0.

## Conflicts that matter for the sim

| Item | Source A | Source B | Effect |
|---|---|---|---|
| Barbarian Bowl threshold | 600 (Sportskeeda, Pocket Tactics range 600–1000) | 800 (Google Play guide) | None for cards, affects which arena a player is in |
| Arena 4 Skeleton card | "Skeleton Tower" (Pocket Tactics) | "Skeleton Dragons" (Sportskeeda) | One MISSING card, name unresolved |
| Arena 7 Royal Recruits / Royal Guards | Royal Recruits (Pocket Tactics) | Royal Guards (Sportskeeda) | Both MISSING, so the count is unchanged |
| Arena 9 extras | Berserker, Goblin Giant, Rune Giant (Pocket Tactics) | Earthquake (Sportskeeda) | Earthquake is IN_C56, so it isn't a gap |
| Arena 8 Vines | Named by Pocket Tactics and Jetpunk | Not named by Sportskeeda | Marked MISSING; low confidence |
| Barbarians | Pocket Tactics (Arena 3) | TrophyCoach (Feb 2026) lists Hog Rider, Witch, Knight, Tesla for Barbarian Bowl | TrophyCoach is an outlier, not used |

## Sources

Fetched and used:
- Pocket Tactics, *Clash Royale arenas guide*, https://www.pockettactics.com/clash-royale/arenas. Updated Oct 3, 2026 per page. **Primary** for arenas 1–10 card lists and thresholds (fetched 2026-10-15).
- Skycoach, *Clash Royale Arenas Guide*, https://skycoach.gg/blog/clash-royale/articles/arenas-guide. Last updated 26.02.2026 per page (fetched 2026-10-15). Training Camp starters (Giant, Fireball, Princess) and arena thresholds. Card names are given only for Training Camp and Bone Pit, so this source is thin.
- Immortal Boost, *Clash Royale Arena Guide 2026*, https://immortalboost.com/blog/clash-royale/complete-arena-guide/. Labeled 2026, no month. Early-arena unlocks.
- Clashest, *Clash Royale Arenas — Full List & Trophies*, https://clashest.com/arenas. Per search snippet only; the fetch failed (DNS), so its card list is unread. Claims the December 2025 Trophy Road update.
- Supercell, *March Update 2026*, https://supercell.com/en/games/clashroyale/blog/release-notes/march-update-2026/. Dated 23 Feb 2026. Official. No card-to-arena mapping.

Search snippets used (not fully fetched):
- Sportskeeda, *All Arenas in Clash Royale: What new cards do they unlock?*, https://www.sportskeeda.com/esports/all-arenas-in-clash-royale-what-new-cards-unlock. Undated. Arenas 4–9 cross-check.
- Sportskeeda, *Arena 4 deck* https://sportskeeda.com/esports/best-arena-4-deck-clash-royale-spell-valley. Spell Valley cards.
- Sportskeeda, *Arena 8 / arena 5–9 breakdown* (within the arena-guide article above). Builder's Workshop, Royal Arena, Frozen Peak, Jungle Arena.
- HighGround Gaming, arena 2 and arena 3 decks, https://www.highgroundgaming.com/best-arena-2-decks-clash-royale/ and https://www.highgroundgaming.com/clash-royale-best-decks-for-arena-3-barbarian-bowl/. Undated. Arena 2 and 3 composition.
- TrophyCoach, *trophy progression hub*, https://trophycoach.com/guides/trophy-progression-hub. Feb 2026 (per the Barbarian Bowl snippet). Outlier list, not used for counts.
- RoyaleAPI, *2026 Q1 update*, https://royaleapi.com/blog/2026-q1-update-march-2026?lang=en. Snippet only. Arena numbering for the 2026 extension.
- RoyaleAPI, *Season 73 Trophy Road rework*, https://royaleapi.com/blog/trophy-road-rework-2025-q2-update?lang=en. Snippet only. Mid-2025 extension.
- gamer.org, *Trophy Road Update 2025*, https://www.gamer.org/clash-royale-trophy-road-update-2025-reach-12000-trophies-for-exclusive-rewards/. Update date 2025-11-24.
- Cashify, *December 2025 update*, https://www.cashify.in/news/clash-royale-december-2025-update-brings-big-trophy-road-rework. Dec 2025.

Attempted and failed (no content used):
- Fandom wiki Arenas page, https://clashroyale.fandom.com/wiki/Arenas: HTTP 402.
- Liquipedia Arenas and Goblin Hut pages: HTTP 403.
- RoyaleAPI /cards: HTTP 403. StatsRoyale /cards: HTTP 403.
- clashroyalearena.com/cards: fetched, but the page has no arena, rarity or elixir data. It states "82 cards" and has no date.
- Royal Chief (royalechief.com/cards-by-arena): DNS failure, not retried.
- RoyaleAPI cr-api-data `arenas.json` and `cards.json` on raw.githubusercontent.com: HTTP 404.

## Limits

- No single authoritative per-card arena source was reachable. The official Supercell post names no card-to-arena mapping for arenas 1–10.
- Rarity, elixir, type and body count are recall, not sourced. Confirm against gamedata (for example, the game's `cards` CSV) before the simulator relies on them.
- `BarbLog` and `BlowdartGoblin` in C56 need a check against gamedata. The first may not be a player card, and the second may be the internal name of Dart Goblin.
