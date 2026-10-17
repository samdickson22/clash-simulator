# Per-seat card and tower levels on our engine (L16 max) — results

CARD LEAD implementation, exploration tier, 2026-10-17 UTC. Branch `cards/levels` (from origin/main 7065dc345).
Code: [`bot/levels/match.py`](../../../bot/levels/match.py), `bot/players/ours.py` (`play_match(levels=...)`),
`bot/eval/headline.py` (`--levels max` on our engine), `bot/deckopt2/run.py` (opt-in `--engine ours`).
Gate tools: [`tools/`](tools); receipts: [`receipts/`](receipts). Job dir: 127x04 `/mpac/sdicks02/jobs/clasher/cards/levels`.
All gates ran on 04 under cpu_job leases of at most 6, nice 15. The 08 jobs never got admission (08 was over its
cap) and were stopped before starting.

## How to run

```bash
# HEADLINE at max levels on our engine (every card on both sides and both King towers at level 16)
python -m bot.eval.headline --out OUT --candidate K4L-R-gs-mk1a1 --opponents R3a --bank LIVE-AB1 --levels max
```
```python
from bot.levels.match import max_levels, from_lists
play_match(rt, players, seed=..., decks=..., levels=max_levels())                 # Sam's eval rule
play_match(rt, players, seed=..., decks=..., levels={'cards': {0: 16, 1: {'Giant': 9}}, 'towers': {0: 16, 1: 14}})
play_match(..., levels=from_lists([{card: lvl}, {card: lvl}], [t0, t1], planner='l11'))  # RoyaleSim-style args
```
`levels=None` (default) is today's exact code path. Missing seats/cards are level 11; levels are 1–16.
`CLASHER_LEVELS_CACHE` sets the planner's per-level export cache (default
`/mpac/sdicks02/jobs/clasher/cards/levels/level-configs`, subdirectory `<runtime tag>-match3`; built once per
runtime under a file lock, about 7 min CPU for L11+L16+L17 on live16402c; already built on 04). deckopt2: `prepare --engine ours` records `engine` in a new manifest; `run` then plays our
engine at the same true levels with all-L11 planners, as its RoyaleSim design.

## Design

**True game.** `play_match` already runs the Python engine (the runtime's `src/clasher`), which has per-player levels:
`PlayerState(card_levels=..., tower_level=...)`. Every deployment is scaled by the deploying player's level
(`resolve_card_play`). Death spawns, spawner children and spell spawns inherit it, and Mirror plays the copy at
Mirror's level + 1, so L17 at max. On the normalized feed every card, champions included, scales with the one Common
table up to 16, so rarity caps don't matter here. Evolutions stay off. `level_battle` builds the battle with these
per seat. No released runtime file is changed. The runtime has gaps at non-11 levels; `install_engine_levels()`
patches them process-wide, only on the levels path, and never at level 11:

| Gap in the runtime at L != 11 | Fix (levels path only) | Evidence |
|---|---|---|
| Crown tower curve limited to 10–12 | `tower_scaling.tower_stat` outside 10–12 uses `bot/levels/root.tower_stat` (same 7%/8%, then 10% after 9, truncated) while the battle is built | L16 King 7728 HP / 173 dmg, Princess 4858 / 173; RoyaleSim 16.402: 7728 / 4858 / 4858, tower hit 173 |
| Earthquake (damage/building/crown), Tornado (crown) refuse L != 11: measured L11 pins | pin × multiplier(L)/multiplier(11), truncated; unpinned fields keep the engine formula | RoyaleSim L16: Earthquake crown 78 (ours 78), Tornado unit hit 134 (ours 134) |
| Clone refuses L != 11 | plays its L11 spell object; Clone has no level-scaled stat | — |
| Graveyard at L != 11 lost its Skeleton data and used a stale built-in body (67 HP at level 1, 274 at L16) | the constructor gets the gamedata object registry that the L11 registry is built from | RoyaleSim L16 skeleton 130 HP, first tower hit 130; ours 130 / 130 (it was 274) |
| Miner crown damage pin 39 returned at every level | scales like the spell pins on any body whose level is not 11 | RoyaleSim L16 62; ours 62 (it was 39) |

The spell audit ([tools/spell_audit.py](tools/spell_audit.py)) builds every registry spell at L16 through this
path and compares all fields with the L11 registry object. After the fixes, the only differences are `level` and
level-scaled numbers (Mirror is resolved separately; GlobalClone is not a deck card).

**Planners.** Search players with a `root_fn` hook (MultiSearchPlayer subclasses: K4S-*, K4C-*, K4L-*) and the
search tier of LIVE-* players get `MatchLevelRoot` when `planner='exact'` (the default). It is the BOT LEAD's
`ExactLevelRoot`, which gives exact level-L root bodies (fields of the producing card's level-L export), the tower
curve, a per-seat native rollout config (`LevelConfigs.mixed`) and the fc cut (`CutConfig`). This change adds two
things on top:
- **Mirror:** the native Mirror resolver reads the fixed key `cards['level12:<card>']`. For a Mirror at level M
  those entries become the level-(M+1) exports, keeping the level-12 entries' `leaf_elixir_share`. At max that is
  L17, consistent with the true game. The mirrored entry follows the root seat's Mirror holder; with mixed per-seat
  Mirror levels it is shared, like the pilot's direct-cast rule.
- **Leaf and scripted crown maxima** take the tower level (`root.leaf_native`).

The exports are built under the same `install_engine_levels`, so native rollouts use the same spells as the true
game. All 121 live16402c cards export at L16 and L17 with 0 errors; all 121 L11 exports equal `R.config`.

The planner is told the declared levels of both seats. That is fair under a public rule (max: everyone at 16). With
private per-card opponent levels use `planner='l11'`, or the pilot's opponent estimate.

**Policies see level-11 packets.** The only level-dependent packet column is entity column 30,
`base_damage = log1p(damage)/8`; HP is a fraction. `L11Packets` replaces it with the row's (token, kind) level-11
template value. It is applied only when some level is not 11. On level-11 games it is an exact identity: 34,046 rows,
0 changed, 0 unmapped (2 full-pool R3a/v1 games, LIVE-AB1 cases 0–1; [log](receipts/l11packets-identity-probe2.log), 127x08). This covers v1, R3a, students, the R3a proposer and the it5s2
fast tier.

**Level-11 assumptions that remain (documented, not changed):**
- The learned rollout opponent (`lopp_feat`) reads cost × HP fraction, so it is level-invariant.
- NativeScripts card metadata (scripted-opponent scores) stays L11; only the two crown maxima change.
- Planning stays at L11 for: players without root_fn (PolicyPlayer, K4S-b*/KU SearchPlayer, `aliased:` wrappers);
  pooled K4L (p<N>), whose workers keep L11 leaf metadata (recorded as `l11 (pooled …)`); the extra roots of
  K4S-m<M>; and K4L D roots.
- Every match result carries `levels.planners`, the planner status per seat. Headline rows carry `level_planners`
  and `level_packets`.

## Gates

### 1. Default `levels=None` byte-identical (PASS)

Before = `git archive 7065dc345` (origin/main); after = commit 5662f3e17. The later commits change only
`bot/levels/match.py`, which the default path never imports, and gate tools. 04, `PYTHONHASHSEED=0`, single-thread
BLAS.

**(a) K4L HEADLINE** `K4L-R-gs-rw-fc-p2` vs R3a/v1, cases 0–5, as in `reports/cards/runtime/tools/gate_k4l.sh`:
**r1-total 12/12 identical, live16402c 12/12 identical**, 0 errors.

| case | r1-total R3a | r1-total v1 | live16402c R3a | live16402c v1 |
|---|---|---|---|---|
| 0 | `c97c01efd8b26fc7` | `735a54ff61829ff3` | `38ca14d87c9ca677` | `872e6bfc2462229a` |
| 1 | `0e4bded993e5287e` | `014ea92e54c66235` | `b50ea8753dfcde90` | `315442ea17f49ea0` |
| 2 | `d82a57557a11ba77` | `ac5b989b40f558f9` | `09a0b737c743d913` | `bc3e623f2dc478a0` |
| 3 | `aacf7644108ea9b9` | `3bc29a662fb7d31b` | `5e7aba8a333d582c` | `6feb21c56c511984` |
| 4 | `69ef6692519e930c` | `1ad1ece376c0d048` | `3057a250233a4498` | `136465ec2e2d5c28` |
| 5 | `9136d901cf2dc3d4` | `a080132ca267adab` | `5f8667c4c217c776` | `24cd763cce34f9cc` |

(command_sha256 prefixes, identical before and after; r1-total = released r1-cards1 root + r1-total pins.)

**(b) Full-pool `K4L-R-gs-mk1a1`** (live16402c, `bot/fullpool/run/env.sh`: k1a1 net, extended R3a/v1, open-world
belief) vs R3a/v1 on LIVE-AB1 cases 0–4: **10/10 play_match command hashes identical**, 0 errors.

| case | R3a | v1 |
|---|---|---|
| 0 | `2bf6063112a8c99f` | `3edc95389e4583c4` |
| 1 | `a33bc8c0dc12dd82` | `a1ee23635a908058` |
| 2 | `608c85b9bb284b4e` | `57b084136c32c993` |
| 3 | `9d7dc31eec58f006` | `3f76e30aa56d505e` |
| 4 | `84d5a00d9fde18eb` | `24bd0c31c00d495d` |

### 2. L16 stats (PASS, with pre-existing L11 differences listed)

[tools/gate_stats.py](tools/gate_stats.py), live16402c vs RoyaleSim 16.402 (clasher-bot venv), at L11 and L16. All
120 cards that both engines know were compared (every non-Mirror card in our pool), including all 56 translator (C56)
cards, marked * below.

- **Towers L16:** RoyaleSim max HP [7728, 4858, 4858]; ours 7728 / 4858, damage 173 / 173. RoyaleSim's tower hit on
  a unit is 173.
- **HP:** RoyaleSim `unit_hitpoints(card, L)` covers the whole chain (own, second summon, spawn, death spawn,
  release) and is compared with every body our Python engine puts down at that level: formation, 300 ticks of
  children, then deaths forced. Per row:

  | | equal | equal by value (name alias) | differs | unmatched |
  |---|---|---|---|---|
  | L11 | 104 | 24 | 4 | 8 |
  | L16 | 104 | 24 | 4 | 8 |

  **No row changes status between L11 and L16.** Every L16 difference is an L11 data difference scaled by the
  table. "differs": ElectroSpirit* 217/215, Ghost* 1210/1152, Goblinstein* 2385/2240, and RamRider's rider, a name
  collision with the Ram. "unmatched": bodies the probe can't reach or name, at both levels (BarbLog*/RoyalDelivery*
  releases, GoblinCurse goblin, GoblinDrill dig, LittlePrince guard, Phoenix egg, SkeletonKing skeletons,
  WitchMother hog).
- **Damage:** first hit on the enemy's L16 princess tower, card at level L (troops from our bridge, spells on the
  tower). Equal: 85 (L11) and 89 (L16); differs 14 and 13; no hit 21 and 18 (buildings that only target troops,
  Log/BarbLog/RoyalDelivery refused on a tower in RoyaleSim, fast-dying troops). Spell and crown damage at L16,
  RoyaleSim / ours: Fireball 253/253, Rocket 546/546, Lightning 423/423, Earthquake 78/78, Zap 77/77,
  Arrows 40/40, Freeze 60/60, GoblinBarrel 600/600, Graveyard 130/130, Miner 62/62, GoblinCurse 16/16, Vines 57/57.
  Every card that differs at L16 already differs at L11 by the same ratio: ArcherQueen*, DarkMagic, ElectroGiant,
  Ghost*, Goblinstein*, GoldenKnight, Hunter, LavaHound, Poison* (crown 22/21 → 34/33), Tornado* (crown 26/25 →
  41/39), Wallbreakers*, Wizard*, Xbow*. These are L11 data differences in live16402c, not level effects; they
  belong to the card-data owners. ElixirGolem's first hit differs at L11 only (timing).
- **Spawned / death-spawned levels, true game:** [tools/deploy_levels.py](tools/deploy_levels.py) plays every
  one of the 121 cards at L16 through `level_battle`. 121/121 are accepted. 106 cards put down 128 distinct bodies
  (formation, 300 ticks of children, death spawns after forced deaths), and every one is at level 16, e.g.
  Tombstone→Skeleton@16, Golem→Golemite@16, Witch→Skeleton@16, Graveyard→Skeleton@16. Mirror's copy (after a
  Knight) is at 17. Wrong levels: 0. [Receipt](receipts/deploy16.json).
- **Planner rollouts = true game:** [tools/gate_native.py](tools/gate_native.py) compares native
  `clasher_core.BattleState` on the per-seat config (`LevelConfigs.mixed` + Mirror remap) with the Python engine at
  the same per-seat levels. Cases: Tombstone, Witch, Graveyard, Golem, SkeletonArmy (seat levels 11/16),
  BattleRam, LavaHound, ElixirGolem, GoblinHut, Fireball, Earthquake (16 vs 11), Mirror and Knight (16/16, Mirror
  copy L17). **13/13: digests identical every tick for 700 ticks, body sets identical.** End-state levels are
  per seat, e.g. Tombstone Skeleton 16 vs 11, GoblinHut SpearGoblin 16 vs 11. [Receipt](receipts/native.json).
- **Other cards** (beyond RoyaleSim's translator set): the scaling equals our level table (multiplier 16/11 =
  1.59765625) wherever L11 agrees. Every compared card is in the table above.

### 3. No-crash full-pool L16 run (PASS)

`bot.eval.headline --bank LIVE-AB1 --levels max`, live16402c (both seats L16, both King towers L16), full-pool
`K4L-R-gs-mk1a1` vs R3a, cases 0–3: **4/4 terminal games (3601–4232 ticks), 0 errors, 0 panic/traceback lines.**
Planner status: K4L `exact`, R3a `l11 (no root_fn)`. Packets: 14,288–18,434 rows per game normalized, 0 unmapped.
Towers start at 7728/4858. [Rows](receipts/3-max.jsonl), with play logs.

| case | seat | ticks | K4L score | command_sha256 |
|---|---|---|---|---|
| 0 | 0 | 4232 | 1 | `3f376aaf4c1d7b0b` |
| 1 | 1 | 3601 | 1 | `3bf3b7b2f06cd7ca` |
| 2 | 0 | 3601 | 1 | `d04525344e6c5e91` |
| 3 | 1 | 3601 | 1 | `d9dfe4a3457f374b` |

Search diagnostic ([tools/gate3_diag.py](tools/gate3_diag.py), cases 4–5, play_match direct): **every K4L
decision searched on an exact L16 root** (106/106 and 108/108 decisions with rollouts; 0 native failures; 0
`bot.search.lopp` FAILURES). Root counters: 106/108 roots; 1100/1114 bodies, of which 405/422 were leveled from
exports; 577/628 crown towers on the curve; 0 unmapped. Per-seat config: 121 cards changed, 0 unsupported,
Mirror level 17, 0 Mirror unsupported. Both terminal. [Receipt](receipts/g3diag.json).
These are no-crash games, not a strength measurement.

### 4. Unit tests (PASS)

`pytest bot/levels/test_match.py`: 15 passed. Covered: spec resolution and rejection, the L16 tower curve, the
tower-curve patch (only outside 10–12), the per-seat L16 config builder (formation, death table, qualified
spell, all-11 identity), the Mirror L17 remap, `L11Packets`, the planner install scope (policy, pooled,
LIVE search tier, all-11), and the re-entrant export-cache lock. That lock self-deadlocked in the first gate-3
attempt when `supported.json` was missing; the run was stopped and rerun.

## Not done / for the BOT LEAD

- The pre-existing L11 differences above, and `live16402c` crown values for Poison/Tornado (one off at L11).
- Pooled K4L (p<N>) plans at L11 at non-11 tower levels. Making it level-aware needs the pool workers to take the
  root's leaf metadata (`lopp_fast.get_pool`, BOT LEAD code).
- Merging any change under `bot/` changes deckopt2's `source_sha256` manifest check for runs prepared before it,
  as every bot/ change does.
