# Runtime full-pool card scope: pin set `r1-cards1` (CARD LEAD, exploration)

Status (2026-10-16 ~02:15Z): implemented. Root parity PASS (600/600, 3 arms). HEADLINE K4L command hashes PASS
(12/12 cases identical across c56/full × before/after the speed fix). Policy HEADLINE PASS (40/40). Non-C56 decks: 0
crashes/panics/errors in 41 + 6 games (§5). Live-search speed on full scope: overhead found and fixed (§5b). Restart
notes: `PROGRESS.md` (this dir).

## 1. What changed

| file | change |
|---|---|
| `bot/players/runtime.py` | new pin set `r1-cards1` = r1-total pins (same native `681b5f2c…`) + `card_scope='full'` + `fc_side_cut=True`. After the normal Resources build, `Runtime.__init__` calls `bot.cards.scope.extend(R, scope)` when `card_scope != 'c56'`, and `bot.cards.fc_cut.install()` when `fc_side_cut`. `r1`, `r2` and `r1-total` set neither key, so both paths are skipped and the build is byte-for-byte today's. (Another worker later added a `live16402` pin set, a `gamedata_sha256` check and `tournament_crown_from_gamedata` that reuse the `card_scope` hook; those are not part of this change. `live16402` does not set `fc_side_cut`: §7.) |
| `bot/cards/scope.py` (new) | the scope shim: `EXTRA_CARDS` (the one constant to trim), `EXCLUDED`, `FULL_WINS_BODIES`, `META_CARD_TOKENS`, `extend()` |
| `bot/cards/fc_cut.py` (new) | side-table fc cut for scope=full (§5b): the fc root cut also drops side-table entries no name in the root can reach |
| `bot/search/lopp_fast.py` (**outside the allowed set**, approved by the BOT LEAD in addendum 4; +33/−12) | `LearnedPool.begin(..., base_cut=None)`: reduce_fast passes the player's fc flag, so fc roots ride the base config (sent once) whatever their size; any other config ships once per worker, keyed by sha1 of its text (`CONFIG_CACHE = 8`, FIFO, mirrored in `_pool_worker`). `base_cut=None` (direct callers: lopp_fast_check, lopp_gil, lopp_safety_test) keeps the old 1 MiB test for fc detection. |
| `bot/cards/build_runtime.py` (new) | assembler for a card-scope runtime root (copy of r1 + engine-cards overlays + receipt) |
| `reports/cards/runtime/tools/*` (new) | probes and gate tools (§6) |

No frozen runtime file is edited. The only file outside the three allowed places is `bot/search/lopp_fast.py` (above).

**Hash-seed determinism (r1-cards1 only).** On r1/r1-total, `meta.cards[*].token` of the C56 alias pairs depends on
PYTHONHASHSEED (seeds 0/1/2 give three metas; §2 row 14). r1-cards1 pins them to the seed-0 values, which are also the
tokens the learned rollout opponents were trained on (`bot-lopp-models/{pool,R3a,v1}.npz` `meta_vocab` holds 20, 77
and 114, not 24, 38 or 289): BarbLog 20, BlowdartGoblin 77 (the vocab's DartGoblin token), Ghost 114. No sort rule
reproduces this mix (alphabetical insertion would give BarbLog 24). New cards with two tokens (Assassin, EliteArcher,
RageBarbarian, SkeletonBalloon, SkeletonWarriors, Snowball) get their own runtime name's `card_action` token. Result:
the r1-cards1 meta is identical for PYTHONHASHSEED 0–3 (sha 13726095…), and its C56 cards equal r1-total's at seed 0.
Under seed 0 the pins are no-ops for C56, so every gate below (all run at seed 0) covers them.

**Where the scope lives (decision): the pin set (`runtime.py` + `bot/cards/scope.py`), not the glue.** Editing
`engine-cards/c56_controller.py` in the copied root would also need `CARDS` changed in `c56_scripted.py`
(`SUPPORTED_CARDS | C56_ADDED_CARDS`, read by the Python scripted bots), which lives in the Python engine overlay that
Batch A is editing, and it would change every consumer of `c56_controller.CARDS` at once (R.bots included). The pin
set keeps the base build untouched and adds the new cards in a separate pass that is merged in. r1/r1-total roots work
unchanged; `r1-cards1` works on any root that carries the 681b5f2c-compatible native (the assembled one, §3).

### How `extend(R, 'full')` works

The C56 scope is baked in at four sites of the Resources build: `c56_controller.CARDS`, the def-time default
`metadata(..., action_cards=CARDS)`, `c56_scripted.C56_ADDED_CARDS` (scripted-bot scope, read at call time), and
`fair_player.CARDS` (config + start-up demos). `extend` keeps the normal C56 build, then runs a **second** Resources
build with those four widened to C56 + EXTRA_CARDS (patched inside a context manager, always restored; the
`cached_resources` class is created inside the patch so its copied globals see the wide list), and merges **base
first**:

- `R.config`: every C56 entry (cards and every side table) is the base object, in base order; full-only keys follow.
  `config(card)` is per card, so the full build's C56 entries are identical; `_merge` asserts it (it raises on any
  difference). Side tables gain only new keys (probe: death_areas 1→6, death_children 2→26, production_children 2→14,
  spawn_areas 0→8, spirit_areas 0→2, death_objects 2→6, ability_bombs 1→2, new `bomb_children`, `soul_*`). Mirror adds
  `level12:<card>` payloads for every card (config cards: 121 playable + 116 `level12:` = 237).
- `R.meta` (native scripted-opponent tables): base cards/bodies first, new after; overlap asserted equal, except
  `meta.bodies`, where the base wins and the conflict is recorded in `R.scope_conflicts`. The one conflict:
  `RamRider`. The base build saw only the rider payload under that name (token 272, range 5.5, hp 593). The full
  build adds the card's own stats (token 271 Ram, buildings-only, hp 1766), and that is what the native reads for the
  Ram entity, whose stats name is `RamRider`. It is listed in `FULL_WINS_BODIES`, so the full row is kept. No C56 card
  puts a `RamRider` body on the board, so C56 states can't see the change. `meta.bodies` keeps 142 entries both ways.
  `R.native = NativeScripts(json.dumps(merged meta))`.
- `R.costs` = `{name: cost}` over the merged config (C56 keys/values/order unchanged; includes `level12:` keys).
- `R.templates` = base dict + full-build keys it lacks (168 → 350). Templates are registered with `setdefault` in
  config order, so a single full build could pick a different template for a token a C56 card shares with a new card
  (e.g. Goblin from GoblinDrill vs GoblinGang). The base-first merge rules that out.
- Unchanged: `R.builder`, `R.bots` (Python scripted bots: our own candidates, Python-side scripts), `rt.PRIOR`, `rt.CAT`.

Scope: `EXTRA_CARDS` = the 66 pool cards outside C56 (pool 122 − 56 − 3 pool aliases of C56 cards: Archer=Archers,
IceSpirits=IceSpirit, IceGolemite=IceGolem) minus `EXCLUDED = {MergeMaiden}` (Spirit Empress has no `card_vocab`
entry; card_action token 1 = UNK). **65 new cards, 121 playable in total.** Every one passes `differential.config`.
The lead's native sweep (`127x08:jobs/clasher/cards/probe-native.log`) can trim more: drop a name from `EXTRA_CARDS`.
Start-up: about 72 s on a loaded 08 (C56 build about 21 s plus the full pass).

## 2. Baked-in C56 sites (inventory) and what r1-cards1 does to each

Full per-component tables with file:line: `INVENTORY.md` (this dir; read-only research, 2026-10-16). Summary, with
the state under **r1-cards1** (verified by the runs in §5 unless marked *code*):

| # | site | C56 today (r1-total) | under r1-cards1 |
|---|---|---|---|
| 1 | `c56_controller.CARDS`, `metadata()` assert, `resources()` | 56 | widened in the 2nd pass (§1) |
| 2 | `c56_scripted.C56_ADDED_CARDS` / `SUPPORTED_CARDS`, `bot.cards` | 56 | widened in the 2nd pass only; `R.bots` stay C56 |
| 3 | `fair_player`: `config(CARDS)`, `costs`, template demos, `root` "no C56 public model template" | non-C56 body → `ValueError` | templates for all 121; roots with Fisherman/Bomber/Tombstone/... build (§5) |
| 4 | `DerivedPublicState` ids from `costs`; human deck catalog (2,925 decks, only the 56) | non-C56 reveal → `KeyError` | ids cover the new cards. Plain `s1.Belief` (non-live K4*/K4L players) still raises `ValueError('no train deck/order…')` on the first non-C56 reveal (§5, expected). `LiveBelief` rebuilds the prior as catalog decks completed with the revealed cards, so **hidden slots are always C56** (prior unchanged, by design) |
| 5 | D1 sidecar `DerivedD1(costs)` (every policy tier, fast tier, RL) | first non-C56 play → `ValueError('unknown card cost')` | works (fast tier and policies play out non-C56 games, §5). Mirror: `config` holds the placeholder cost 1.0, but D1 charges `costs[last_card] + 1` (`derived_d1.py`, correct) |
| 6 | command channel `delay_fixes.py:73` `card not in costs` | non-C56 own play → `ValueError` | passes the costs check; our own non-C56 hand still fails earlier (row 7) |
| 7 | `C56RolloutPlanner.candidates` (`c56_scripted.py:195`, via `R.bots`) | own non-C56 hand → `ValueError('own hand outside C56 action scope')` | **unchanged** (R.bots stay C56). Our decks are C56 today; widening R.bots is the next step if we ever hold a new card |
| 8 | native `meta.cards` gating (`scripts.rs:249,291,296`, `c56_scripts.rs:54`, `delay_commands.rs:42,61`) | the scripted rollout opponents never play a non-C56 card (it clogs a slot) | they now **play** the revealed/sampled new cards in rollouts (meta.cards has 121). Mirror needs `config.cards["level12:<prev>"]`; the fc cut (`config_need`) doesn't keep it, so Mirror is skipped in fc rollouts (*code*, no panic) |
| 9 | native step-time config lookups (spell areas, chains) | r1-total: missing → effect skipped | entries exist for the new cards; the physics are the lead's per-card sweep (Python vs native, 900-tick digests) |
| 10 | K4L learned opponent vocab (`lopp_train.py` → `.npz` `meta_vocab` = 57 = pad + 56) | non-C56 hand token → 0 from native view | **silently approximate**: the native view now sends the real token; the net maps it to index 0 (pad embedding), `cost_of` 0 → flagged affordable; the native mask allows the slot, so the learned opponent can play the card with the pad embedding. No crash. Retraining with a 122 vocab changes the table shapes |
| 11 | policy nets v1 / R3a / it5s2 / RL r5 v10 (360-token embedding) | real tokens, untrained rows | unchanged (no IOOB possible; non-C56 rows untrained) |
| 12 | live translator `PROXY` / `unknown_card='drop'` / `no_template:` drops | non-C56 plays dropped or proxied, units without templates dropped | **unchanged code**; with r1-cards1, `R.templates` and `R.costs` cover the new cards, so the translator can pass them through instead of dropping/proxying. That is a LIVE LEAD decision (§7) |
| 13 | `royalesim_vocab.py` (built from `c56_controller.CARDS` demos), `royalesim_translate.py:256` `costs[last]` | non-C56 units unresolved | unchanged (it imports `CARDS` at module import, not affected by the shim) |
| 14 | `meta.cards[*].token` for the alias pairs BarbLog/BarbarianBarrel, BlowdartGoblin/DartGoblin, Ghost/RoyalGhost | **depends on PYTHONHASHSEED** (set iteration in `c56_scripted.initialize`; seeds 0/1/2 give 3 different metas on r1-total). Under seeds other than 0, the learned rollout opponents (trained on 20/77/114) see those 3 cards as unknown | **pinned** to the seed-0 tokens; new alias cards get their own-name token; meta identical for seeds 0–3 (§1) |
| 15 | lopp_fast fc cut (`config_need`, `ConfigCache`, `_ConfigJson`) and `LearnedPool.begin`'s 1 MiB fc test | cuts `cards` only; the side tables (95 KB) ride along | side tables grow to 795 KB, so every fc root carried them, and roots over 1 MiB were re-shipped to every worker on every decision. **Fixed**: `fc_cut.py` side cut + the `base_cut` / content-hash pool cache (§5b) |

## 3. Assembled runtime root (`bot/cards/build_runtime.py`)

```
# on 05 (git): export a commit (git archive; uncommitted edits never ship)
python bot/cards/build_runtime.py --rev HEAD --export-only /mpac/sdicks02/jobs/clasher/cards/runtime/src-<sha12>
# on the runtime host, with that tree copied there:
python bot/cards/build_runtime.py --tree src-<sha12> --target DIR --native SO   # or --build-dir OUT (cargo, -j 16)
```

Copy (default) or `--link` (hardlinks via rsync --link-dest; overlays are always written as new inodes, so r1 is
never written through a link). Overlays: `engine-cards/py/src/clasher/**` → `src/clasher/**`,
`engine-cards/py/gamedata.json` → `gamedata.json`, `engine-cards/*.py` → `engine-rs/`, native →
`native/clasher_core.abi3.so`. Receipt: `CARDS-RUNTIME-RECEIPT.json` (commit, the worktree's uncommitted engine-cards
paths, which are *not* included, native sha + origin, sha256 of all overlay files + manifest sha, which overlays changed
a base file, base-only files). Refuses a target that overlaps r1, a non-empty target without a receipt, and any target
under `clasher-bot-runtime/` without `--release`.

Dev roots (not the real one): `127x08:` and `127x03:/mpac/sdicks02/jobs/clasher/cards/runtime/r1-cards1-dev`, from
commit b7143dd7a (engine-cards unchanged since 7e64d8b93), native 681b5f2c (`jobs/clasher/cards/out-total`), 473
overlay files, **0 changed vs r1**, manifest `72c5f691…`. Use: `CLASHER_BOT_RUNTIME=<root>
CLASHER_BOT_RUNTIME_PINS=r1-cards1` (no `CLASHER_DELAY_NATIVE_DIR`).

## 4. Parity: C56-only inputs, scope=c56 vs scope=full

Arms (all PYTHONHASHSEED=0, native 681b5f2c): **live** = r1 root + native-total-r1, pins r1-total (today's live
runtime); **c56** = dev root, pins r1-total; **full** = dev root, pins r1-cards1.

### 4a. Native roots (`tools/parity_scope_roots.py`, adapted from native-total-tools/parity_roots.py)

300 real search roots sampled (seed 20261015) from the 12 recorded K4S-m2 vs R3a games
(`127x03:jobs/clasher/bot-native-total/roots`). Each is rebuilt with the arm's own `R.config`, as `full` (whole config)
and `cut` (lopp_fast ConfigCache, the fc pool path), then evaluated with the arm's own `R.native` (NativeScripts from
`R.meta`). Snapshots are hashed without their config text (the one thing the scope changes).

| arm | scope | config cards | records | identical to live | config sha |
|---|---|---|---|---|---|
| live | c56 | 56 | 600 | — (reference) | ac4e792e… |
| c56 | c56 | 56 | 600 | **600/600** | ac4e792e… |
| full | full | 237 | 600 | **600/600** | e68a9f66… |

Re-run 01:52Z with the final code (lopp_fast change + r1-cards1 `fc_side_cut`, so the full arm's `cut` variant is the
side cut): live / c56 / full again **600/600** identical. The side cut is also checked directly
(`tools/side_cut_check.py`: full config vs today's cards-only cut vs the side cut, same values incl. step digests):
**265/265** recorded C56 roots and **80/80** non-C56 roots (D1/D3/D4/M1) identical. Median cut config: C56 roots
1.13 MB → 0.39 MB, non-C56 roots 1.20 MB → 0.46 MB (full config 5.81 MB).

Per arm: 9,336 rollout_e1 values (WAIT, timed WAIT, ≤4 plays × 3 styles, frozen budget), 1,800 select_action calls
(+ digests), 478 apply_discrete + step 40, 1,800 step digests/snapshot bodies, evaluate, evaluation_parts,
public_view and public_mask of both seats. Every value is bit-identical (float.hex / sha256).

### 4b. HEADLINE command hashes (`bot.eval.headline`, HEADLINE_BASE cases), c56 vs full

`command_sha256` is `bot.players.ours.play_match`'s hash over every executed command (tick, seat, action, accepted),
i.e. the HEADLINE protocol's per-game command hash; both seats' players are inside it.

**K4L search (`tools/gate_k4l.sh`, 08):** `K4L-R-gs-rw-fc-p2` (the live K4L body, deterministic: no wall, 2 pool
workers, fc cut) vs R3a and v1, cases 0–5. Four arms on the dev root: c56 / full × **before** (lopp_fast.py at HEAD,
r1-cards1 without the side cut, i.e. the state that showed the overhead) / **after** (content-hash pool cache +
`base_cut`, r1-cards1 with `fc_side_cut`).

| opp | case | command sha (c56-before) | c56-after | full-before | full-after | score | plays (seat 0/1) |
|---|---|---|---|---|---|---|---|
| R3a | 0 | c97c01efd8b2 | = | = | = | 1.0 | 40/37 |
| R3a | 1 | 0e4bded993e5 | = | = | = | 1.0 | 39/37 |
| R3a | 2 | d82a57557a11 | = | = | = | 1.0 | 28/39 |
| R3a | 3 | aacf7644108e | = | = | = | 1.0 | 38/37 |
| R3a | 4 | 69ef6692519e | = | = | = | 0.0 | 60/71 |
| R3a | 5 | 9136d901cf2d | = | = | = | 1.0 | 57/64 |
| v1 | 0 | 735a54ff6182 | = | = | = | 1.0 | 37/26 |
| v1 | 1 | 014ea92e54c6 | = | = | = | 1.0 | 30/35 |
| v1 | 2 | ac5b989b40f5 | = | = | = | 1.0 | 27/29 |
| v1 | 3 | 3bc29a662fb7 | = | = | = | 1.0 | 33/36 |
| v1 | 4 | 1ad1ece376c0 | = | = | = | 1.0 | 44/32 |
| v1 | 5 | a080132ca267 | = | = | = | 1.0 | 17/33 |

**12/12 identical across all four arms, 0 errors.** This covers K4L (native rollouts + learned rollout opponent +
pool + fc cut), R3a (cutoff default, proposals, opponent) and v1 (opponent) on C56 games.

**Policies (`tools/polgate.sh`, 08):** students it5s2 (`it5s2-step001200.pt@0.5375`, the live fast tier) and RL r5
v10 (`bot-rl-r5/snapshots/policy-00010.pt@0.5375`, sha e188e2ae…) vs v1 and R3a, cases 0–9, c56 (pins r1-total) vs
full (pins r1-cards1, final code), dev root, PYTHONHASHSEED=0. (Planned for cases 0–29; cut to 0–9 because 03 sat at
load 95. The c56 arm resumed 9 games from 03 on 08, and the full arm ran on 08.)

| candidate | vs | identical command sha (c56 vs full) |
|---|---|---|
| it5s2 | v1 | **10/10** |
| it5s2 | R3a | **10/10** |
| RL r5 v10 | v1 | **10/10** |
| RL r5 v10 | R3a | **10/10** |

**40/40 identical, 0 errors, 3,028 plays.** That covers both students' D1 / feature path on the widened `R.costs`, plus
v1 and R3a as opponents.

The 577-fixture native gate (`parity_fixtures.py`) builds its configs with `differential.config(cards)` directly, not
through Runtime, so it can't see the scope. The native is the same file (681b5f2c), so that gate's result for
r1-total carries over unchanged.

## 5. Non-C56 opponent decks: no-crash runs (full scope)

`tools/noncore_matches.py` / `noncore.sh` (03, 2026-10-16 00:54–01:34Z, r1-cards1 on the dev root, before the §5b
fix): our player holds X-deck 0 (C56); the opponent holds a non-C56 deck and is either R3a or `random` (every 10
ticks, P=0.35, a uniformly random legal play from the v5 public mask, which makes sure the new cards get played).
Decks: D1 = Goblin Cage, Spear Goblins, Tombstone, Bomber, Graveyard, Freeze, Mortar, Fisherman; D2 = Barbarian
Hut, Witch, P.E.K.K.A, Mega Minion, Mirror, Electro Wizard, Royal Giant, Heal Spirit; D3 = Goblin Drill, Skeleton
King, Lava Hound, Clone, Rage, Golden Knight, Phoenix, Monk; D4 = Elixir Golem, Skeleton Barrel, Night Witch, Goblin
Curse, Vines, Void, Battle Ram, Elixir Collector; M1 = Goblin Cage, Spear Goblins, Tombstone, Bomber + Knight,
Fireball, Hog Rider, Musketeer; X1 = X-deck 1 (C56 control). A spy on `R.root` counts roots, root exceptions, roots
whose opponent hand/cycle holds a non-C56 card, and the non-C56 entity stats names in each native root.

| player | opp | deck | games | crashes | panics | errors | native fail | search fail | root errors | roots (opp non-C56) | search / default / other | new cards played by opp | non-C56 entities in roots |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| K4L-R-gs-rw-fc | random | M1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 206 (199) | 0 / 0 / 0 | Bomber 11, SpearGoblins 11, Tombstone 11, GoblinCage 2 | Tombstone 78, Bomber 73, GoblinCage 24, GoblinBrawler 9 |
| LIVE-K4L…p4 | R3a | D1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 260 (260) | 1 / 303 / 0 | GoblinCage 6, Fisherman 6, Bomber 6, Tombstone 6, SpearGoblins 5, Mortar 5 | Fisherman 115, Tombstone 91, GoblinBrawler 85, Bomber 67, Mortar 65, GoblinCage 61 |
| LIVE-K4L…p4 | R3a | D2 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 227 (226) | 8 / 254 / 0 | Heal 4, Mirror 4, ElectroWizard 4, BarbarianHut 3, MegaMinion 3, RoyalGiant 3, Witch 2 | RoyalGiant 74, Witch 70, MegaMinion 52, ElectroWizard 49, BarbarianHut 31, Heal 6 |
| LIVE-K4L…p4 | random | D1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 307 (305) | 139 / 180 / 0 | Fisherman 12, SpearGoblins 12, Bomber 12, Tombstone 12, Freeze 9, GoblinCage 3, Mortar 1, Graveyard 1 | Fisherman 177, Tombstone 156, Bomber 124, GoblinCage 38, GoblinBrawler 33, Mortar 23 |
| LIVE-K4L…p4 | random | D2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 320 (318) | 142 / 189 / 0 | Heal 11, ElectroWizard 10, MegaMinion 10, Mirror 10, Witch 9, RoyalGiant 1 | MegaMinion 294, Witch 135, ElectroWizard 106, Heal 51, RoyalGiant 19 |
| LIVE-K4L…p4 | random | D3 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 442 (440) | 7 / 492 / 0 | Rage 10, GoblinDrill 9, Clone 9, GoldenKnight 6, SkeletonKing 5, Phoenix 5, Monk 2 | GoldenKnight 169, SkeletonKing 140, Phoenix 117, Monk 88, GoblinDrill 74, Rage 53 |
| LIVE-K4L…p4 | random | D4 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 364 (362) | 9 / 385 / 0 | DarkMagic 7, GoblinCurse 7, Vines 7, SkeletonBalloon 7, ElixirGolem 5, Elixir Collector 1, DarkWitch 1, BattleRam 1 | ElixirGolem 128, ElixirGolem4 119, SkeletonBalloon 101, ElixirGolem2 58, Elixir Collector 27, BattleRam 11, DarkWitch 10 |
| LIVE-K4L…p4 | random | M1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 444 (436) | 11 / 504 / 0 | SpearGoblins 13, Bomber 12, Tombstone 11, GoblinCage 2 | Tombstone 230, Bomber 220, GoblinBrawler 31, GoblinCage 27 |
| LIVE-K4L…p4 | random | X1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 423 (0) | 21 / 462 / 0 | — | — |
| LIVE-fast-it5s2 | R3a | D1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0) | 0 / 0 / 1209 | Bomber 14, GoblinCage 13, Fisherman 13, SpearGoblins 13, Tombstone 13, Mortar 13 | — |
| LIVE-fast-it5s2 | R3a | D2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0) | 0 / 0 / 1050 | Mirror 9, MegaMinion 9, Heal 8, ElectroWizard 8, BarbarianHut 6, RoyalGiant 5, Witch 2, Pekka 1 | — |
| LIVE-fast-it5s2 | R3a | D3 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0) | 0 / 0 / 1105 | SkeletonKing 10, Rage 10, GoldenKnight 8, Phoenix 8, Monk 6, Clone 5, LavaHound 2 | — |
| LIVE-fast-it5s2 | R3a | D4 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0) | 0 / 0 / 992 | ElixirGolem 11, GoblinCurse 10, DarkWitch 9, BattleRam 6, SkeletonBalloon 5, Vines 5, Elixir Collector 4, DarkMagic 3 | — |
| LIVE-fast-it5s2 | R3a | M1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0) | 0 / 0 / 1043 | Bomber 9, SpearGoblins 9, Tombstone 8, GoblinCage 2 | — |
| LIVE-fast-it5s2 | R3a | X1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0) | 0 / 0 / 1111 | — | — |
| LIVE-fast-it5s2 | random | D1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0) | 0 / 0 / 930 | SpearGoblins 11, Bomber 11, Tombstone 10, Fisherman 9, Freeze 7, GoblinCage 3, Graveyard 2 | — |
| LIVE-fast-it5s2 | random | D2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0) | 0 / 0 / 1026 | Heal 11, ElectroWizard 10, MegaMinion 10, Mirror 10, Witch 9, RoyalGiant 1 | — |
| LIVE-fast-it5s2 | random | D3 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0) | 0 / 0 / 910 | GoblinDrill 9, Rage 8, Clone 8, GoldenKnight 5, Phoenix 5, SkeletonKing 4, Monk 1 | — |
| LIVE-fast-it5s2 | random | D4 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0) | 0 / 0 / 776 | DarkMagic 7, GoblinCurse 7, Vines 7, SkeletonBalloon 6, ElixirGolem 5, Elixir Collector 1, DarkWitch 1, BattleRam 1 | — |
| LIVE-fast-it5s2 | random | M1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0) | 0 / 0 / 1022 | Bomber 12, SpearGoblins 12, Tombstone 11, GoblinCage 2 | — |
| LIVE-fast-it5s2 | random | X1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 (0) | 0 / 0 / 1041 | — | — |

**41 games, 0 crashes, 0 panics, 0 errors, 0 native failures, 0 search failures, 0 root exceptions.** Every new card
the opponent played shows up as entities in the native roots (Goblin Cage, Goblin Brawler from the cage, Tombstone,
Bomber, Fisherman, Mortar, Witch, Mega Minion, Electro Wizard, Golden Knight, Skeleton King, Phoenix, Monk, Elixir
Golem and its splits, Skeleton Barrel, ...). Spear Goblins' body `SpearGoblin` is already a C56 body (Goblin Gang),
so it isn't counted as new. The K4L-R-gs-rw-fc row is the deterministic non-live body with `--live-belief` (below).

- **Non-live search players + plain s1 Belief:** `K4L-R-gs-rw-fc` without LiveBelief raises
  `ValueError('no train deck/order is consistent with public plays')` on the first non-C56 reveal (closed-world C56
  catalog; §2 row 4). Live play uses LiveBelief and doesn't hit it. With `--live-belief`, 2/2 M1 games are clean.
- **Search vs default split.** In these runs the live search fell back to the it5s2 default on most decisions
  (completed ≈ 0.01–0.3 of 25–30 candidates) on D3/D4/M1, **and on the X1 C56 control too**. D1/D2 early in the window
  got about 45% searched. This follows 03's load (55 → 85 during the window), not the cards. §5b separates the two.

**Final-code re-run** (`tools/noncore_final.sh`, 08, 02:09–02:17Z, lopp_fast content-hash cache + r1-cards1
`fc_side_cut`, host load ≈25), LIVE-K4L-R-gs-rw-fc-w200-t4-p4, 1 game per deck:

| opp | deck | crashes | panics / errors / native fail / search fail / root errors | roots (opp non-C56) | search / default | completed / candidates (mean) | search wall ms (mean) |
|---|---|---|---|---|---|---|---|
| random | D1 | 0 | 0 / 0 / 0 / 0 / 0 | 83 (82) | 79 / 5 | 9.43 / 11.6 | 122 |
| random | D2 | 0 | 0 / 0 / 0 / 0 / 0 | 113 (112) | 109 / 6 | 9.81 / 10.9 | 129 |
| random | D3 | 0 | 0 / 0 / 0 / 0 / 0 | 86 (85) | 83 / 4 | 9.06 / 10.7 | 101 |
| random | D4 | 0 | 0 / 0 / 0 / 0 / 0 | 87 (86) | 82 / 6 | 8.18 / 10.6 | 99 |
| random | M1 | 0 | 0 / 0 / 0 / 0 / 0 | 112 (110) | 108 / 5 | 10.27 / 11.2 | 121 |
| R3a | D1 | 0 | 0 / 0 / 0 / 0 / 0 | 109 (108) | 104 / 6 | 9.67 / 11.3 | 114 |

**6/6 clean. With the fix, on a quieter host, the live search completes on non-C56 decks: 94–96% of decisions
searched, about 9 of 11 candidates completed, ~100–130 ms of the 200 ms wall.** Earlier (§5, 03 at load 85, before
the fix) it was 0.01–0.3 completed. The new units again appear in the roots (Goblin Cage, Goblin Brawler, Fisherman,
Mortar, Mega Minion, Witch, Electro Wizard, Golden Knight, Phoenix, Skeleton King, Elixir Golem splits, ...). Not a
paired comparison (different host and time from §5); §5b is the controlled one.

### 5b. Live-search cost on full scope: cause and fix

**Measurement** (`tools/decision_timing.py`): the live recipe's code path (LivePlayer → WallLearnedPlayer →
reduce_fast, LiveBelief) with a 20 s wall (`LIVE-K4L-R-gs-rw-fc-w20000-t1-p2`), so every decision completes. That
makes it deterministic: arms play the same game and pair decision by decision (same actions, same command sha). Per
decision: poll, belief update, propose, candidates, sample, R.root, fc json, root.snapshot, pool.begin, and
reduce_fast's own `phase_ms` (ship, native, learned, worker parse, chunk), plus config bytes.

**Cause.** lopp_fast's fc cut keeps only the referenced *cards*; every side table rides along whole. Under scope=full
the side tables grow from 95 KB to 795 KB (death_children 21 → 358 KB, bomb_children 98 KB, production_children
98 KB, soul_skeletons 84 KB; about half are Mirror's `level12:` copies). So every fc root carried ~1.2–1.5 MB of
config. That is over `LearnedPool.begin`'s fc test (`len(parts[1]) < 1 << 20`, lopp_fast.py:249), so the pool treated
the cut as a foreign config and **re-shipped it to every worker on every decision** (`config_resent` every time),
and each worker re-parsed it. On the same decisions the native rollouts cost the same in both scopes, and the new
cards are not slow per native tick: 03 medians per complete decision, native ms: X1 151, D3 145, D4 154, M1 130, D1 187.

**Fix** (approved by the BOT LEAD):
1. `bot/cards/fc_cut.py` (r1-cards1 pin `fc_side_cut`): the fc cut also keeps only side-table entries whose key is
   reachable by name from the root (its players/entities/pending casts and the kept cards' config entries,
   transitively). Value parity: §4a (600/600, 265/265, 80/80).
2. `bot/search/lopp_fast.py`: fc roots are flagged by reduce_fast (`base_cut`), not guessed by size, so they always
   ride the base config (shipped once). Any other config ships once per worker per content hash.

**Quiet before/after** (127x05, `taskset -c 48-51`, SMT siblings idle, nice 10, load 15–25, 01:58:38–02:05:08Z;
62 complete decisions per run, paired by tick; every pair has the same actions and the same command sha: X1 9fa08ea0
in all four arms, D3 5ba8a7b5 in both):

| run | total | root | snapshot | ship | worker parse | native | config bytes | paired total ratio |
|---|---|---|---|---|---|---|---|---|
| X1 c56 before | 166.2 | 3.2 | 0.7 | 1.7 | 4.1 | 111.5 | 0.37 MB | — (reference) |
| X1 c56 after | 158.5 | 3.2 | 0.7 | 1.7 | 4.1 | 108.9 | 0.37 MB | ×0.987 vs c56 before |
| X1 full before | 172.8 | 5.1 | 2.0 | 6.0 | 7.1 | 116.5 | 1.26 MB | ×1.065 vs c56 before |
| X1 full after | 167.6 | 3.3 | 0.6 | 1.6 | 5.1 | 110.7 | 0.31 MB | ×1.006 vs c56 before |
| D3 full before | 181.9 | 12.1 | 2.1 | 7.0 | 6.2 | 118.0 | 1.31 MB | — |
| D3 full after | 164.3 | 3.7 | 0.7 | 1.9 | 5.8 | 105.1 | 0.39 MB | ×0.880 vs D3 before |

(medians, ms; t1-p2 so all native work is one thread.) **The fix removes the full-scope overhead:** on a C56 deck,
full scope goes from ×1.065 to ×1.006 of c56, and a non-C56 deck gets 12% faster. The lopp_fast change is neutral on
c56 (×0.987). Projected on the Mac (fleet cores ~2.8× slower): X1 full-after ≈ 60 ms per complete t1-p2 decision.
**No 10–20× effect exists.** The near-zero completions in §5 were host load at w200 t4-p4 on 03 (load 85; the X1 C56
control shows the same), plus this ~+10–25 ms overhead, which is now gone.

## 6. Tools (`reports/cards/runtime/tools/`)

| tool | what |
|---|---|
| `probe_config.py` | config(C56) vs config(C56+pool): C56 parts identical; which names config accepts |
| `probe_vocab.py` | pool vs C56 aliases vs `builder.card_vocab` (found MergeMaiden) |
| `probe_tokens.py` | token names, deployed entity stats names (RamRider) |
| `smoke_scope.py`, `dump_meta.py` | build sizes/hashes per pin; meta dump (hash-seed check); C56 reference lists `c56_*.json` |
| `parity_scope_roots.py`, `compare_scope.py`, `gate.sh` | the §4 gate (`gate.sh roots` / `gate.sh headline`) |
| `noncore_matches.py`, `noncore.sh`, `noncore_final.sh`, `noncore_summary.py` | the §5 runs (R.root spy, decision sources/errors/panics; `--live-belief`, `--save-roots`) and table |
| `gate_k4l.sh`, `polgate.sh` | §4b HEADLINE command-hash gates (K4L 4 arms; policies per arm) |
| `decision_timing.py`, `timing_summary.py`, `timing.sh`, `quiet05.sh`, `config_sizes.py`, `time_roots.py` | §5b per-phase timing (paired by tick), config bytes per key |
| `side_cut_check.py`, `probe_native_config.py` | side-cut value parity; whether a root's native config parses back equal to R.config (it doesn't: the native adds defaulted fields such as `mirror: false`, which is why the pool doesn't classify configs by value) |
| `chain03.sh`, `chain03b.sh` | host chains used on 03 |

## 7. Open issues / decisions for other leads

**BOT LEAD**
1. **lopp_fast.py diff** (+33/−12, §1): review it and own it. The `base_cut` flag assumes every root an fc player
   passes to the pool is a shim cut of `R.config`. That holds for `R.root` and `LevelRoot` (both use `config=R.config`).
   A future root builder with its own config must pass `base_cut=False`.
2. **macOS spawn pools:** `fc_cut.install()` patches `ConfigCache` in the parent. Forked workers (Linux) inherit it;
   spawned workers (macOS default) don't, so they keep lopp_fast's cards-only cut. Values are the same, but on the Mac
   every worker parses about 1.2 MB per root instead of 0.4 MB. Fix: import `bot.cards.fc_cut` and call `install()` in
   `_pool_worker`'s spawn branch when the parent had it (one line in lopp_fast.py); I didn't add it.
3. **K4L learned opponent is C56-only** (57-entry vocab): under r1-cards1 a non-C56 hand card maps to the pad embedding
   with cost 0 and is always "affordable", and the native mask now allows the slot. Rollouts with such cards are
   approximate. Retraining needs a 122-card vocab (the table shapes change).
4. **Non-live search players + plain s1 Belief** raise on non-C56 reveals (§5). Any eval vs non-C56 decks needs
   LiveBelief (`bot.live.player.live_belief_class`), as `noncore_matches.py --live-belief` does.
5. **PYTHONHASHSEED on r1/r1-total:** set PYTHONHASHSEED=0 wherever r1/r1-total runs (live included). Otherwise the
   learned opponents see BarbLog/DartGoblin/Ghost as unknown. r1-cards1 doesn't depend on the seed (§1).
6. Our own non-C56 hand still raises (`C56RolloutPlanner.candidates`, R.bots stay C56; §2 row 7). Widening `R.bots`
   is the next scope step if a live deck ever holds a new card.

**LIVE LEAD**
7. With r1-cards1, `R.templates` / `R.costs` / `R.meta` cover 121 cards, so the translator can pass non-C56 plays and
   units through instead of `unknown_card='drop'`/`'proxy'` and the `no_template:` drops. The search then models them
   (§5 shows roots with them build and search). Switching is a translator decision; the PROXY table becomes optional.
8. Mirror: fc rollouts skip Mirror (its `level12:<prev>` config entry isn't in the cut; no panic). D1 charges
   Mirror `costs[last_card] + 1` (correct).
9. Start-up time: r1-cards1 builds in ~50–75 s (C56 ~20 s), so the live loop should build it before the session.

**CARD LEAD**
10. `EXTRA_CARDS` holds all 65 non-C56 pool cards except MergeMaiden (no vocab token). Trim it with the native sweep
    (`probe-native.log`). The native physics of the new cards is that sweep's job; this change only makes them
    reachable.
11. The real `clasher-bot-runtime/r1-cards1` isn't created yet: run `build_runtime.py --release` from a committed
    engine-cards revision (the Batch A edits in the worktree are uncommitted and would *not* ship). If its native sha
    differs from 681b5f2c, update the r1-cards1 `native_sha256` pin.
