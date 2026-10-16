# Optional-stat totality patch (exploration tier)

The reported crash was `float(None)` in `clasher.rl.c56_scripted.ranked_actions` when a present spell's
`building_damage` is `None` and a visible enemy non-Crown building is scored. A `getattr` default only handles a
missing attribute. The patch explicitly uses ordinary damage for `None`; ordinary damage itself defaults to zero
for a non-damage spell. Numeric building-damage values keep the exact previous conversion, multiplication and
horizon order. `None` crown damage already means zero, and metadata deliberately retains optional building damage
as JSON null for Rust's existing `unwrap_or`.

Changes are confined to Python: the ranking building-damage fallback, the ranking ordinary-damage conversion, and
the metadata ordinary-damage conversion. No native source or binary changed. `r1-cards2-r2` and `live16402b-r2`
retain their parents' native, gamedata and checkpoint pins. There is no sealing.

## Scope and assumptions

Audit covers the engine actually imported from `engine-cards/py/src/clasher`, `engine-cards/c56_controller.py`,
`bot/search/candidates.py`, all `bot/search/lopp*.py` and `bot/players/*.py`, the C56 rollout planner, public scripted
opponent, public/contract-v5 placement masks, reward/leaf scoring, wait-screen8 and the runtime planner wrappers.
Rust audit covers `scripts.rs`, `c56_scripts.rs` and `leaf.rs`, including every unwrap in those files.
All stat-consuming `getattr`/dict defaults, numeric conversions and arithmetic were reviewed, including guarded
branches and the required numeric values supplied by normalized entity/config records.

The existing runtime scope is preserved. `MergeMaiden` (Spirit Empress) is already excluded by `bot/cards/scope.py`:
its v5 card-action token is UNK (1). Its stats are audited, and the probe asserts that exclusion; it cannot be
ranked as an admitted hand card without changing the observation/action contract. All admitted runtime cards and
all corresponding ladder aliases are exercised. This limitation predates the None-stat fix.

The probe builds `Runtime(verify=True)`, checks all metadata, inventories every ladder definition and script/body
stat, then exercises all four hand slots, both seats and five boards: Crown towers alone, enemy Cannon, Knight,
Minions, and all three together. It invokes public masks, all three scripted ranking styles, planner candidates,
native masks/selection/evaluation. C56 ranks are compared exactly to the original module, including every score.
The released-root rerun also checks required numeric fields for visible body rows. ThreeMusketeers' aggregate row (token 326) has None HP, but no runtime body template references it: the runtime emits the child Musketeer token. The probe records this distinction rather than treating an aggregate card wrapper as a visible body.

## Audit table

20 audit rows: 3 changed conversion sites in 2 Python files; 17 reviewed rows require no change.
Runtime inventory covers 125 spellings (122 ladder names plus runtime aliases), 121 admitted canonical cards.
The receipt records None and missing values together; spell attribute presence is distinguished in the released-root rerun.
For building_damage, only Freeze has a present None attribute; absent attributes on C56 spells already used the old getattr default.
Freeze has numeric ordinary damage 148 in this live root, so its fallback is 148; non-damage spells retain zero.

| Site | Field | Which cards are None (or missing where indicated) | Fix / disposition |
|---|---|---|---|
| c56_scripted.ranked_actions | spell.building_damage | Present None: Freeze (1); other None/missing names below | **FIX:** explicit None → ordinary damage; preserve numeric C56 horizon order |
| c56_scripted.ranked_actions | spell.damage | None (0); Clone, DarkMagic, GoblinBarrel, GoblinCurse, Graveyard, Mirror, Rage, Tornado, Vines have numeric zero | **FIX:** explicit zero default before float |
| c56_controller.metadata | spell.damage | None (0) | **FIX:** same zero default before float |
| c56_scripted / metadata | spell.crown_tower_damage | 9 None/missing: Clone, DarkMagic, GoblinBarrel, GoblinCurse, Graveyard, Mirror, Rage, RoyalDelivery, Vines | Existing or 0 handles both missing and None; no change |
| c56_scripted / metadata | spell.duration | 12 None/missing: Arrows, BarbLog, Clone, Fireball, GoblinBarrel, Log, Mirror, Rage, Rocket, RoyalDelivery, Snowball, Zap | Existing or 1; ranking reads duration only for Poison/Earthquake; no change |
| c56_scripted / metadata | spell.projectile_range | 19 None/missing: Arrows, Clone, DarkMagic, Earthquake, Fireball, Freeze, GoblinBarrel, GoblinCurse, Graveyard, Lightning, Mirror, Poison, Rage, Rocket, RoyalDelivery, Snowball, Tornado, Vines, Zap | Direct arithmetic is restricted to Log/BarbLog (both numeric); metadata or 0; no change |
| c56_scripted / metadata | spell.radius | None (0) | Already or 0; no change |
| c56_scripted / metadata | spell.hits_air | 10 None/missing: BarbLog, Clone, DarkMagic, GoblinCurse, Graveyard, Log, Mirror, Rage, RoyalDelivery, Vines | Boolean filtering, no numeric conversion; no change |
| c56_scripted / public opponent / metadata / masks | mana_cost; deploy_w_tile_margin; targets_only_buildings | None (0) across all 125 spellings | Required numeric cost; margin already or 0; targets read as bool; no change |
| initialize / public opponent / metadata / reward | summon_count | 64: Arrows, BabyDragon, Balloon, BarbLog, BarbarianHut, BombTower, Bomber, Bowler, Cannon, Clone, DarkMagic, DarkPrince, Earthquake, ElectroWizard, Elixir Collector, Fireball, Freeze, Giant, GiantBuffer, GoblinBarrel, GoblinCage, GoblinCurse, GoblinDrill, GoblinHut, GoldenKnight, Golem, Graveyard, IceWizard, InfernoTower, Knight, LavaHound, Lightning, Log, MightyMiner, Miner, MiniPekka, Mirror, Monk, Mortar, Musketeer, Pekka, Poison, Prince, Princess, Rage, RamRider, Rocket, Ronin, RoyalDelivery, RoyalGiant, SkeletonKing, Snowball, Tesla, ThreeMusketeers, Tombstone, Tornado, Valkyrie, Vines, Witch, WitchMother, Wizard, Xbow, Zap, ZapMachine | Existing or 1 (or explicit formation default); no change |
| metadata / public opponent / reward | scaled_hitpoints / hitpoints | 23: Arrows, BarbLog, Clone, DarkMagic, Earthquake, Fireball, Freeze, GoblinBarrel, GoblinCurse, Graveyard, Lightning, Log, MergeMaiden, Mirror, Poison, Rage, Rocket, RoyalDelivery, Snowball, ThreeMusketeers, Tornado, Vines, Zap | Metadata/efficiency use or 0; visible bodies use resolved child payload stats; required body fields probed; no change |
| metadata / public opponent / reward | scaled_damage | 31: Arrows, BarbLog, BarbarianHut, Clone, DarkMagic, Earthquake, Elixir Collector, Fireball, Freeze, GoblinBarrel, GoblinCage, GoblinCurse, GoblinDrill, GoblinHut, Graveyard, Lightning, Log, MergeMaiden, Mirror, Poison, Rage, Rocket, RoyalDelivery, SkeletonBalloon, Snowball, SuspiciousBush, ThreeMusketeers, Tombstone, Tornado, Vines, Zap | Existing or 0; entity.damage normalized numeric; no change |
| c56_scripted / public opponent / metadata | range | 10: BarbLog, Fireball, Freeze, GoblinBarrel, Log, MergeMaiden, Mirror, Rocket, Snowball, ThreeMusketeers | Existing or 0; no change |
| metadata / masks / public opponent | collision_radius | 22: Arrows, BarbLog, Clone, DarkMagic, Earthquake, Fireball, Freeze, GoblinBarrel, GoblinCurse, Graveyard, Lightning, Log, MergeMaiden, Mirror, Poison, Rocket, RoyalDelivery, Snowball, ThreeMusketeers, Tornado, Vines, Zap | Existing or 0/or 0.5 and explicit None checks; no change |
| c56_scripted / public opponent / metadata | attacks_air / target_type | attacks_air: all 125 spellings None/missing; target_type: 30: Arrows, BarbLog, BarbarianHut, Berserker, Clone, DarkMagic, Earthquake, Elixir Collector, Fireball, Freeze, GoblinBarrel, GoblinCage, GoblinCurse, GoblinDrill, GoblinHut, Graveyard, Lightning, Log, MergeMaiden, Mirror, Poison, Rage, Rocket, RoyalDelivery, Snowball, ThreeMusketeers, Tombstone, Tornado, Vines, Zap | Boolean/str conversion; no float/int arithmetic; no change |
| c56_rollout_planner / wait-screen8 / planner wrappers | proposals, masks, scores, elixir | No nullable card-stat arithmetic | Consumes normalized observation arrays, integer actions and numeric config; no change |
| bot/search/candidates.py / lopp*.py / bot/players/*.py | cost tables; card/config lookup; packet fields | No unguarded nullable-stat arithmetic | Costs from normalized config/model arrays; optional stats dictionaries guarded by or {}; no change |
| Rust c56_scripts.rs | building_damage: Option<f64> | Freeze None; missing spell attributes serialize as null in metadata | Already unwrap_or(damage); no change |
| Rust scripts.rs | spell Option / crown_tower_damage / placement half | Crown None: GoblinBarrel/RoyalDelivery (neither admitted by legacy P16); live dispatch uses C56 metadata | Card spell lookup uses and_then/let Some; crown unwrap is outside live C56 path; placement unwrap guarded by building; no change |
| Rust leaf.rs / Python reward_model | leaf_elixir_share / entity HP, damage, interval | Optional share guarded; entity numeric fields normalized | Already unwrap_or(0.0) plus bounded denominators; no change |

The legacy P16 public opponent admits its declared base roster only. Its direct spell damage/radius/crown and Log
range arithmetic are numeric for that roster. The live/full-pool path dispatches to `c56_scripted` instead.
`PublicScriptedOpponent._bodies` only reads health from resolved visible troop/building payloads, whose health and
cost are required numeric fields; optional shield values already use `or 0`. The probe checks every body table row.

Native details: `c56_scripts.rs` uses `building_damage.unwrap_or(damage)`; its other spell fields deserialize as
numeric scalars from Python metadata. `leaf.rs` uses `leaf_elixir_share.unwrap_or(0.0)`; entity damage/HP/interval
are numeric normalized fields. `scripts.rs:417`'s crown-damage unwrap belongs to `public_choice`, reached only when
`meta.c56` is false; these released roots always use `meta.c56=true`, dispatching to `c56_choice`. The placement
`half.unwrap()` is guarded by `m.building`, which constructs `Some(half)`; the anchor minimum uses the nonempty anchor list exported for admitted unrestricted building cards. Other unwraps cover checked deadlines, serialization or completed rollout results, not optional card stats.
No native patch, and thus no native rebuild/parity-gate obligation, is introduced.

## Verification and release evidence

Development probe: **PASS**, 46,403 calls, 0 exceptions/panics, 7,080 exact C56 ranking comparisons.
Evidence: [none-stats-dev.json](receipts/none-stats-dev.json).

Exact game 2000024: seed `2613058993490888`; student `rl5-v10-fp.pt@0.5375`, K4C-r16 teacher, beta=0,
self opponent, full-pool spec `fullpool:11433651:freq=b53b02a1fde4`, from the BOT LEAD's read-only
`127x08:/mpac/sdicks02/jobs/clasher/bot-fullpool/G1/launch-1792133650.json` and `games-002.jsonl`.
The original ranking module reproduces the reported TypeError. The patched module completes at tick 3601,
winner seat 0, command SHA256 `fa51cd35e7ceca754336735355d75717dac0aea98947f01cc76b5839d2a39df9`;
564 teacher rows kept only in memory, no shard writes or sealing. Inputs and deck order are in
[replay-2000024-dev.json](receipts/replay-2000024-dev.json). The replay uses an isolated copy of BOT LEAD's
`repo-98f4e2b36313`, with this task's runtime.py and the tracked X4S/S1 dependencies added to that scratch copy.

K4L gate and released-root verification: pending; receipts will be appended after completion.

Commands use `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`, single-thread numerical libraries and `nice -n 15`.
Compute on 04/08 uses `/mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh` with leases of at most four.
The gate runner `tools/gate_none_stats.sh` uses `gate_k4l.sh`'s HEADLINE protocol and K4L candidate, cases 0–5
against R3a/v1, with current r1-total and patched r1-cards2 roots. The historical gate's hard-coded old job roots
are replaced by this task's isolated scratch roots. Its first scratch attempt lacked `sdefault`; those failed
import logs were retained separately and excluded from the final gate.

Release tool `tools/release_none_stats.py` copies immutable parent roots without hardlinks, applies only the two
committed engine Python files, preserves assembler receipts and the parent receipt, records every overlay hash and
a complete content/mode/symlink manifest digest, writes a new `RECEIPT.json`, and removes write permissions only
on the new root. Verification checks `Runtime(verify=True)`, every overlay/receipt, the full manifest, read-only
permissions, and parent-root content/mode/symlink invariance before and after.

Scratch job: `/mpac/sdicks02/jobs/clasher/cards/none-stats-r2-bchzbvd5`.
