# live16402: live-balance pin set (client 16.402 card stats for all 122 pool cards)

Worker `cards-live16402-opus-r1` for CARD LEAD, 2026-10-16. Exploration tier. Code: `bot/cards/balance_overlay.py`
(generator + receipt), `bot/cards/test_balance_overlay.py` (15 synthetic tests), `bot/cards/build_live16402.py`
(assembler), `bot/players/runtime.py` (`PIN_SETS['live16402']` + two small hooks), `reports/cards/live16402/tools/`
(effect check, totality wrapper, gate script). Receipt: `receipt.json` (sha256s, counts, names; no stat tables).

**Source vs live build.** Stats are RoyaleSim `cards-160402017-20261006.json`, content **16.402.19** (client build
160402017, the 2026-10-06 update). The live client is versionCode **160402020**. It is the same 16.402 line, but a
later build or a server-side balance push after 2026-10-06 is not covered.

## Runtime

| | |
|---|---|
| Dev root | `127x08:/mpac/sdicks02/jobs/clasher/cards/runtime/live16402-dev/` (read-only; copy on 03 `jobs/clasher/cards/live16402/runtime/`) |
| Base | `r1-cards1-dev` (cards-runtime-scope worker's `build_runtime.py`, receipt sha256 `55163570…`) |
| gamedata.json | in `892fbfa0…` (= r1 = `engine-cards/py/gamedata.json`) → out **`a7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb`** (reproduced byte for byte on 05 and 08) |
| RoyaleSim 16.402.19 | `babaa3d129e370c5838f12001683e2a5579dbaec581fd94968e689aacfc3fb60` (`cards-160402017-20261006.1`) |
| RoyaleSim 15.535 | `c68d6c011e0130649aa2647b21e293c8bf7141e32262bdfd8cc7592704229fdc` (`cards-15535.1`) |
| Calibration copy | main's root `gamedata.json` `9a70da5a…` (= origin/main) |
| Native | `681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b` (unchanged, no native change needed) |
| Code at build | `balance_overlay.py` `694b3028…`, `build_live16402.py` `9fad0953…`, `statsdiff.py` `09313854…`, `balance_size.py` `87c4dbf2…` (worktree, uncommitted) |

Select it with:

```
CLASHER_BOT_RUNTIME=<live16402 root> CLASHER_BOT_RUNTIME_PINS=live16402
# CLASHER_DELAY_NATIVE_DIR: leave unset (the native is <root>/native), or set it to <root>/native
```

Pin entry: `dict(PINS, native_sha256=681b5f2c…, card_scope='full', gamedata_sha256=a7de3e93…,
tournament_crown_from_gamedata=('Fireball', 'Poison'))`. r1 / r1-total / r2 / r1-cards1 entries are untouched.

**Runtime verify checks.** `Runtime(verify=True)` hashed only the native, v1 and R3a, never gamedata. With the same
native as r1-cards1, `PINS=live16402` on the wrong root would have silently run the old stats. So the live16402 entry
pins `gamedata_sha256`, and verify checks it against `$CLASHER_ROOT/gamedata.json`, the file the engine actually loads
(3 lines, only for pin sets that carry the key). quickwin_resources keeps no disk cache. The other gamedata sha
checks in the tree are in RL code: `clasher.rl.council_opponents` / `council_evaluation` / `readiness_*` (and
engine-speed `es_rollout.py`, which imports council_opponents lazily). None of them fired on the paths gated here
(Runtime build, totality, headline K4L, LIVE K4L / fast tier), all of which ran on the live16402 root. A tool that
builds a `CouncilOpponentPool` with an r1 gamedata pin would refuse this root, by design. `verify=False` callers
such as totality.py skip all pin checks, as before.

**Engine override hook.** `clasher.balance.TOURNAMENT_SPELL_OVERRIDES` pins level-11 crown damage measured on an earlier
client (Fireball 172 = 688 × 25 %). With the 16.402 Fireball crown percent (25 → 23) that pin did two things: it
**masked** the change at level 11 (crown stayed 172), and the engine's reconciliation check rejected the level-12
build, so Mirror's `level12:Fireball` payload **dropped out of the config**. For spells named in
`tournament_crown_from_gamedata`, `Runtime.__init__` pops that pin before Resources builds. The engine then derives
crown damage from the overlay's percent, as it already does at other levels. Effect: Fireball L11 crown **159**
(L12 174, Mirror payload back). Poison stays **21**: its 16.402 percent (23 → 22) reproduces the pinned 21 exactly,
which independently supports that change; its `level12:Poison` Mirror payload now reconciles and appears. Without the
pin key, i.e. every other pin set, nothing is popped.

## What changed (counts; values only in the runtime dir's `LIVE16402-OVERLAY-DETAIL.json`)

**79 gamedata values in 46 cards** (19 C56, 27 others; 78 distinct card/body/field names, BushGoblin HP sits at two
paths). Pass 1 = the comparer's slots (`statsdiff.py` / `balance_size.py` mapping, reproduced exactly: 0 missing,
0 extra rows): 57 RoyaleSim values + 5 calibration values. Pass 2 = named objects (our nested blocks by `name` +
`source` against RoyaleSim's `units` / `projectiles` / `area_effect_objects` / `buffs` tables, same rules, only at
locations pass 1 does not own): 16 + 1. Pass 2 exists because the comparer cannot see a spell's damage on a nested
projectile or a buff's crown percent; it found real 16.402 changes on C56 cards (BarbLog rolling damage, Royal Delivery
damage, Ice Golem death-freeze buff time, Poison crown percent) and others (Battle Healer's heal area, Executioner and
Bowler projectile range, Goblin Machine rocket speed, Little Prince guard damage, Suspicious Bush goblin HP).
Field names per card (from `receipt.json`; values are not in git):

C56:

| Card | Slots | Fields (body field) |
|---|---|---|
| ArcherQueen | 1 | damage |
| BarbLog | 2 | BarbLogProjectileRolling damage, Barbarian hitpoints |
| ElectroSpirit | 1 | hitpoints |
| FireSpirits | 2 | damage, hitpoints |
| Fireball | 1 | crown tower damage percent |
| FirespiritHut | 2 | FireSpirits damage, FireSpirits hitpoints |
| Ghost | 2 | damage, hitpoints |
| GoblinGang | 2 | SpearGoblin hit speed (ms), SpearGoblin load time (ms) |
| GoblinHut | 2 | SpearGoblin hit speed (ms), SpearGoblin load time (ms) |
| Goblinstein | 2 | goblinstein_doctor damage, hitpoints |
| Golem | 1 | sight range |
| IceGolemite | 2 | FreezeIceGolemite buffTime, hitpoints |
| MightyMiner | 1 | damage |
| Poison | 1 | Poison crown tower damage percent |
| RoyalDelivery | 1 | RoyalDeliveryProjectile damage |
| Skeletons | 1 | summon radius |
| Wallbreakers | 1 | damage |
| Wizard | 2 | damage, load time (ms) |
| Xbow | 3 | damage, hit speed (ms), projectile speed |

Others:

| Card | Slots | Fields (body field) |
|---|---|---|
| AxeMan | 1 | AxeManProjectile projectileRange |
| BarbarianHut | 2 | Barbarian hitpoints |
| Barbarians | 1 | hitpoints |
| BattleHealer | 6 | BattleHealerHeal lifeDuration, BattleHealerHeal radius, damage, hit speed (ms), hitpoints, load time (ms) |
| BattleRam | 2 | Barbarian hitpoints, sight range |
| Bomber | 1 | damage |
| Bowler | 1 | BowlerProjectile projectileRange |
| ElectroGiant | 1 | damage |
| EliteArcher | 1 | damage |
| Elixir Collector | 2 | lifetime (ms), mana generate (ms) |
| Freeze | 2 | buff time (ms), duration (ms) |
| GiantBuffer | 1 | hitpoints |
| GoblinCage | 1 | GoblinBrawler hitpoints |
| GoblinGiant | 4 | SpearGoblin hit speed (ms), SpearGoblin load time (ms), SpearGoblinGiant hit speed (ms), SpearGoblinGiant load time (ms) |
| GoblinMachine | 3 | GoblinMachineRocketProjectile speed, damage, hitpoints |
| GoldenKnight | 1 | damage |
| Heal | 1 | HealSpirit hitpoints |
| LavaHound | 3 | damage, hit speed (ms), load time (ms) |
| LittlePrince | 1 | ChampionGuard damage |
| MergeMaiden | 2 | MergeMaiden_Mounted damage, MergeMaiden_Normal damage |
| MiniSparkys | 2 | hit speed (ms), load time (ms) |
| Mortar | 2 | hit speed (ms), load time (ms) |
| RamRider | 1 | damage |
| Ronin | 2 | hit speed (ms), load time (ms) |
| SpearGoblins | 2 | hit speed (ms), load time (ms) |
| SuspiciousBush | 2 | BushGoblin hitpoints |
| Vines | 1 | duration (ms) |

Per-field totals over all bodies (from `changes_by_field` in `receipt.json`): damage 22, hitpoints 18, hit speed (ms) 11, load time (ms) 11, duration (ms) 3, buff time (ms) 2, crown tower damage percent 2, sight range 2, projectileRange 2, lifetime (ms) 1, mana generate (ms) 1, projectile speed 1, summon radius 1, radius 1, speed 1 (sum 79).

### Calibration corrections (rule 2; flagged in the receipt)

Main's calibration values were measured on the 15.535 client. Used only where RoyaleSim 15.535 == 16.402:

| Card | Path | Runtime | Calibration (15.535) | RS 15.535 | RS 16.402 | Written | Decision |
|---|---|---|---|---|---|---|---|
| BarbarianHut | `/summonCharacterData/deathSpawnCharacterData/hitpoints` | 270 | 280 | 280 | 280 | 280 | calibration: calibration applied: RoyaleSim 15.535 == 16.402 on this field |
| BarbarianHut | `/summonCharacterData/spawnCharacterData/hitpoints` | 270 | 280 | 280 | 280 | 280 | calibration: calibration applied: RoyaleSim 15.535 == 16.402 on this field |
| Barbarians | `/summonCharacterData/hitpoints` | 270 | 280 | 280 | 280 | 280 | calibration: calibration applied: RoyaleSim 15.535 == 16.402 on this field |
| BattleRam | `/summonCharacterData/deathSpawnCharacterData/hitpoints` | 270 | 280 | 280 | 280 | 280 | calibration: calibration applied: RoyaleSim 15.535 == 16.402 on this field |
| ElectroSpirit | `/summonCharacterData/hitpoints` | 90 | 84 | 85 | 84 | 84 | apply: calibration superseded: RoyaleSim 15.535 != 16.402 (or 15.535 missing), 16.402 wins |
| FireSpirits | `/summonCharacterData/hitpoints` | 90 | 84 | 85 | 84 | 84 | apply: calibration superseded: RoyaleSim 15.535 != 16.402 (or 15.535 missing), 16.402 wins |
| Goblinstein | `/summonCharacterSecondData/projectileData/damage` | 36 | 53 | 53 | 53 | 53 | calibration: calibration applied: RoyaleSim 15.535 == 16.402 on this field |
| Rascals | `None` | None | 100 | None | None | None | keep-calibration-unconfirmed: calibration not applied: RoyaleSim has no 16.402 value |
| Wallbreakers | `/summonCharacterData/projectileData/damage` | 137 | 110 | 110 | 118 | 118 | apply: calibration superseded: RoyaleSim 15.535 != 16.402 (or 15.535 missing), 16.402 wins |
| BarbLog | `/projectileData/spawnProjectileData/spawnCharacterData/hitpoints` | 270 | 280 | 280 | 280 | 280 | calibration: calibration applied: RoyaleSim 15.535 == 16.402 on this field |
| FirespiritHut | `/summonCharacterData/onStartingActionData/actionToExecuteData/spawnDataData/hitpoints` | 90 | 84 | 85 | 84 | 84 | apply: calibration superseded: RoyaleSim 15.535 != 16.402 (or 15.535 missing), 16.402 wins |

Calibration paths outside the pool: BarbarianLauncher (not a pool card) keeps 270.
Rascals deploy delay (calibration 100, runtime unset) is **not applied**: RoyaleSim has no value in either table,
so rule 2 cannot confirm it (open issue).

### Kept as ours

- **Uncertain cells (rule 3)**, the 19 rows of BALANCE-SIZE.md (d):

| Card | Body | Field | Why |
|---|---|---|---|
| DarkMagic | card | damage | RoyaleSim has no damage field for this spell (it sits in the strike action graph) |
| DarkMagic | card | hits air | gamedata AOE flags are false; the laser-ball sub-actions may do the hitting |
| DarkMagic | card | hits ground | gamedata AOE flags are false; the laser-ball sub-actions may do the hitting |
| ElectroWizard | card | crown tower damage percent | crown value is not on the card's own damage object |
| Freeze | card | crown tower damage percent | RoyaleSim 16.402.19 crown cell is blank (loads as 100), no measured value |
| GoblinCage | card | death spawn deploy (ms) | RoyaleSim death_spawn.deploy_time_ms may be a spawn delay, not the spawned unit's deploy time |
| GoblinCurse | card | damage | RoyaleSim has no damage field for this spell (it sits in the curse action graph) |
| GoblinMachine | card | crown tower damage percent | crown value is not on the card's own damage object |
| GoblinMachine | card | minimum range | gamedata minimumRange sits in onStartingActionData (the rocket attack); RoyaleSim may not model it as range |
| IceWizard | card | crown tower damage percent | RoyaleSim 16.402.19 crown cell is blank (loads as 100), no measured value |
| Lightning | card | hit speed (ms) | RoyaleSim hit_speed_ms (500) is the strike interval the 16.402 strike test calls AreaHitSpeed; gamedata hitSpeed on the area object may be a different concept |
| MegaKnight | card | spawner interval (ms) | gamedata spawnInterval 1 on the MegaKnight block; RoyaleSim models no spawner, so likely not a spawn field |
| MegaKnight | card | spawner number | gamedata spawnNumber 1 on the MegaKnight block; RoyaleSim models no spawner, so likely not a spawn field |
| Rage | card | crown tower damage percent | crown value is not on the card's own damage object |
| RageBarbarian | card | crown tower damage percent | crown value is not on the card's own damage object |
| SkeletonWarriors | card | summon radius | RoyaleSim gives spawn_radius_milli, not summon_radius_milli; assumed to be the same concept |
| Vines | card | hits air | gamedata AOE flags are false; the trap sub-actions may do the hitting |
| Vines | card | hits ground | gamedata AOE flags are false; the trap sub-actions may do the hitting |
| Zap | card | crown tower damage percent | RoyaleSim 16.402.19 crown cell is blank (loads as 100), no measured value |

- RoyaleSim defaults (`defaults_applied`, not a cell) are never written (0 cases in this data; tested).
- **Structural** (21): attacks-air/ground and hits-air/ground flags that gamedata encodes in `tidTarget`, mostly
  buildings-only units (Golem, Ice Golem, Lava Hound) where RoyaleSim's flag means something else; ThreeMusketeers'
  second-unit name. 58 ABSENT slots (gamedata has no such key, e.g. flying height) are not created.
- **Hold** (1): Void (`DarkMagic`) elixir 3. RoyaleSim says 5 in both 15.535 and 16.402, so it is no 16.402 balance
  change but a source disagreement; elixir drives the elixir model and action costs. Verify on the live card.

## Engine effect (`tools/dump_config.py` + `diff_config.py`, both roots built with Runtime)

43 of the 46 changed cards change the engine config / native metadata; the level-12 (Mirror) payloads follow.
No engine change: **GoblinGiant** (its spear riders have no payload in the engine config at all: the engine does not
model them from gamedata; an engine gap, not an overlay one), **LittlePrince** (the card row is unchanged; its
`ChampionGuard` body row changed), **MergeMaiden** (excluded from scope; its variant bodies changed).
Fireball/Poison crown: see the hook above. Elixir costs (`R.costs`) unchanged except the Fireball/Poison level-12
Mirror entries.

## Gate

### (a) No crashes: 0 crashes, panics or errors

| Run (127x08, live16402 root, PYTHONHASHSEED=0) | Games / probes | Crashes | Panics | Other failures |
|---|---|---|---|---|
| totality.py, recorded-root config | 6,707 probes | – | 0 | 68 failing cuts, all the designed `ValueError: unsupported card absent` (reference run: 68) |
| totality.py, recorded-root config, `--scrub` | 6,707 | – | 0 | 0 |
| totality.py, live16402 `R.config` (`--runtime-config`) | 6,707 | – | 0 | 67 failing cuts, same designed ValueError |
| totality.py, live16402 config, `--scrub` | 6,707 | – | 0 | 0 |
| LIVE K4L `LIVE-K4L-R-gs-rw-fc-w200-t4-p4` vs random / R3a on D1–D4, M1, X1 | 33 games | 0 | 0 | 0 decision / native / search / root errors |
| Fast tier `LIVE-fast-it5s2`, same decks | 36 games | 0 | 0 | 0 |
| Complete-search `K4L-R-gs-rw-fc` + live belief vs random, D1–D4, M1 | 10 games | 0 | 0 | 0 |

All 79 games terminal. Opponents played 32 distinct non-C56 cards (747 plays in the LIVE run); 16 overlay-changed
cards were played (BarbarianHut, BattleRam, Bomber, ElectroSpirit, Elixir Collector, Fireball, Freeze, GoblinCage,
GoldenKnight, Heal, LavaHound, Mortar, Skeletons, SpearGoblins, Vines, Xbow). On the loaded 08 the LIVE tier's 200 ms
wall often fell back to the it5s2 default (2,813 searches, 1,699 defaults), hence the complete-search run.
Decks: `reports/cards/runtime/tools/noncore_matches.py` (cards-runtime-scope worker's tool, run unchanged).

### (b) Sanity eval: K4L vs R3a and v1, HEADLINE cases 0–199 per pin

Protocol HEADLINE-v1 (`bot.eval.headline`, C56 X-decks, base 1455777415631152). live16402 arm: `K4L-R-gs-rw-fc`,
08 `gate/hl-l16`. Current-pin arm: the bot lead's `K4L-R-gs` HEADLINE run under r1 (04
`jobs/clasher/bot-lopp2/base/bot-lopp-hl2`, cases 0–199). It stands in for a rerun because 12 cases × both
opponents of `K4L-R-gs-rw-fc` under r1-total (08 `gate/hl-cur`) replay it with identical `command_sha256`, 24/24.
Bootstrap 95% CI over games (4,000 draws, `bot.eval.summarize.ci`); paired = same case, live16402 − current.

| K4L vs | live16402 | current pin | paired diff |
|---|---|---|---|
| R3a | 0.810 [0.755, 0.865] (162-0-38) | 0.830 [0.780, 0.880] (166-0-34) | −0.020 [−0.080, +0.045] |
| v1 | 0.920 [0.880, 0.955] (184-0-16) | 0.950 [0.915, 0.975] (190-0-10) | −0.030 [−0.075, +0.015] |
| pooled (400) | 0.865 | 0.890 | −0.025 [−0.063, +0.013] |

Same level, as expected: both CIs include 0; 60 of 400 cases changed outcome (25 better, 35 worse), 0 identical
command streams (the stats change every game). The policies were trained on the old stats, so a small cost is
plausible; this eval measures sim self-consistency, not live strength.

## Open issues

1. Source build: 16.402.19 (160402017) vs live 160402020; any later balance push is not covered.
2. Void elixir 3 vs RoyaleSim 5 (held); Rascals deploy delay calibration unconfirmed (not applied). Both want a look
   at the live client.
3. GoblinGiant spear riders are not in the engine config (no effect from their 16.402 change; fidelity gap).
4. 19 uncertain cells kept (Zap/Freeze/IceWizard blank crown cells, Lightning strike interval, ...).
5. balance.py's other measured pins (Arrows, Earthquake, Log, Zap, Rage, Tornado, Snowball, Rocket, Freeze crowns;
   Earthquake damage) were not touched: the overlay did not change their percents, so they still agree.
6. Dev root only. Release = `build_live16402.py --base clasher-bot-runtime/r1-cards1 --target
   clasher-bot-runtime/live16402 --release` after r1-cards1 is released (needs the lead's OK); gamedata sha must
   stay `a7de3e93…` (it will if r1-cards1's gamedata is still `892fbfa0…`).
7. Uncommitted: all of this plus the other workers' edits in the same worktree; the lead commits.
