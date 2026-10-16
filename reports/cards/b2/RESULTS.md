# Batch B2 spell mechanics results

Status: **C56 gate FAIL** on the requested frozen B2 tree (`4916d66b8`, handoff `745d18c2c`).
The original 04 sweep has finished: fixture records and native chains **410/577 identical
(167 different)**; roots **600/600 identical**. Failure was reported immediately, before
waiting for these final counts, and the Opus owner was woken with the one-hunk fix specification in [GATE-TRIAGE.md](GATE-TRIAGE.md).
No engine changes were made in this worktree by the test agent. A scratch diagnostic revert
was used only on 08. All requested fidelity, mixed repro, and original gate measurements are complete. The Opus owner has since committed the one-hunk engine fix as `aa8d28a76`;
that corrected source is not the frozen gate arm measured here.

## Inputs and completed fidelity sweep

Primary arm: full RoyaleSim 16.402 table (`--table 160402`), not the adapter's older Void values.
Host 08, `/mpac/sdicks02/jobs/clasher/cards/b2/`:

- `baseroot` / `base`: pre-B2 `7720915a8`.
- `root` / `tree`: B2 mechanics, byte-matched by rsync checksum against this worktree's engine-cards.
- `rootstats`: B2 mechanics plus scratch `fid/stats-spec.json` overlay in `stats/gamedata.json`.
- `fid/run_pool.sh` recorded PID 3069080 has exited; `fid/final.done` exists and reads `done`.
- Full files: `fid/final-{base,mech,stats}.jsonl`, each 196 rows / 66 cards. Source engine
  files in 08 `tree` and `gtree` also matched the worktree before owner fixes.

| Passing measured scenarios | Before | Mechanics | Mechanics + scratch stats |
|---|---:|---:|---:|
| B2 (10 cards) | 13/28 | 16/28 | 24/28 |
| Other cards (56 cards) | 41/168 | 41/168 | 41/168 |
| Full 66-card pool | 54/196 | 57/196 | 65/196 |

Mirror has one harness scenario, the other nine B2 cards have three each: **28**, not 30,
rows in this fidelity sweep. Tolerance and verdicts are the existing `summarize.compare()`
ones, including one tick for impact timing. Improvements in difference count can occur
without changing a scenario from DIFF to PASS.

JSON summaries are retained in [evidence/fidelity-summary.json](evidence/fidelity-summary.json)
and [evidence/mixed-summary.json](evidence/mixed-summary.json). Input SHA256 values:

```text
final-base.jsonl  fd6ff1d12efd480587a7cf79ac8beb68ce68e3fef8e1e125b5491a9f2e44a688
final-mech.jsonl  b5c6e4d2cb1ef815799e1d604b18c1d43e921d8e584037c0f3249767c9671f00
final-stats.jsonl 80499d7c2fe5d157b1f5207685e5b10017e8afaf6c1bec4881add935fe89109f
```

## Cause / fix by card

Mechanics and controlled observations below are from PROGRESS.md; the verdict counts are
independently recomputed from the final three-arm JSONL files.

| Card | Before → mechanics → stats | Cause / implementation | Scratch stat rows (outside git) / residual |
|---|---|---|---|
| Freeze | 1/3 → 1/3 → 3/3 | AreaEffectSpell reads data crownTowerDamagePerHit | Area lifeDuration 3500, buffTime 3500, crown damage 15 (add); extra towerfreeze controlled probe identical in owner's notes |
| Heal | 0/3 → 0/3 → 3/3 | No mechanic gap | HealSpirit hitpoints 84 |
| DarkMagic / Void | 1/3 → 1/3 → 3/3 | Scope area skips birth update (previously one tick early) | lv3 dps/crown 2720/38; lv2 1155/20; lv1 600/14 |
| Vines | 2/3 → 2/3 → 3/3 | Birth skip; catch clock from data; re-pick each catch; air-to-ground 2.1 s; grounded flier keeps air collision plane | Vines_AeO lifeDuration 1400, hitSpeed 250 (add) |
| Rage | 2/3 → 3/3 → 3/3 | Haste applies on landing; cap is life left + HitSpeed; capBuffTimeToAreaEffectTime | No stat overlay; owner's controlled application window matches 11..105 |
| Clone | 2/3 → 3/3 → 3/3 | Object-phase cast; 500 ms hold; 10-tick column-edge slide after movement; route dropped at slide end | Final harness rerun closes the pending Clone item |
| Graveyard | 0/3 → 1/3 → 1/3 | Birth skip; against_forward Y orientation; deploy +1 tick; F+7 acquisition delay; creation-tick first update | Cluster/support residual: Skeleton contact drift after death at t106/t204, described by owner as shared physics. Separately, an accidental RollingProjectile +50 ms hunk breaks C56 (see triage) |
| GoblinCurse | 2/3 → 2/3 → 2/3 | Birth skip; data-driven curse slow; converted Goblin deploy +1 tick | GoblinCurseDamage speedMultiplier -15 (add). Cluster residual: converted-Goblin river snapping and slot-ordinal artifact (owner attribution) |
| Snowball | 2/3 → 2/3 → 2/3 | Knockback and slow match in controlled probe; cluster retains a step toward the old waypoint after a 1.8-tile push | Shared route behavior, also relevant to C56 Fireball/Log; left unchanged / C56-blocked |
| Mirror | 1/1 → 1/1 → 1/1 | Native bomb children lookup uses payload key with name fallback for mirrored SkeletonBalloon | No overlay; level-11 C56 intended inert |
| Poison × dash (native-diff) | Separate interaction probe | Native area_targets skips dash travel; only BanditDash bodies carry it | Not a B2 fidelity-pool scenario; mixed games 75/416/133 now match |

Spell-area boundary probe (ours misses at r+0.5, RS hits to r+1.0) was left unchanged:
owner identified the RS AOE_HIT_TEST as a low-confidence guess, while ours follows strict
client intersects. It also affects C56 spells.

## Final per-scenario fidelity

Generated by `tools/table.py final-base.jsonl final-mech.jsonl final-stats.jsonl -- Freeze Heal
DarkMagic Vines Rage Clone Graveyard GoblinCurse Snowball Mirror`. Parentheses are the number
of measured differences; any following metric is the first difference, ours/RS.

| Card | Scenario | Before | Mechanics | Mechanics + stats |
|---|---|---|---|---|
| Freeze | tower | PASS (0) | PASS (0) | PASS (0) |
| Freeze | cluster | DIFF (21) tower_hits[0].tick 222/212 | DIFF (21) tower_hits[0].tick 222/212 | PASS (0) |
| Freeze | support | DIFF (13) tower_hits.count 7/8 | DIFF (13) tower_hits.count 7/8 | PASS (0) |
| Heal | alone | DIFF (6) HealSpirit[0].max_hp 230/215 | DIFF (6) HealSpirit[0].max_hp 230/215 | PASS (0) |
| Heal | knight | DIFF (1) HealSpirit[0].max_hp 230/215 | DIFF (1) HealSpirit[0].max_hp 230/215 | PASS (0) |
| Heal | minions | DIFF (1) HealSpirit[0].max_hp 230/215 | DIFF (1) HealSpirit[0].max_hp 230/215 | PASS (0) |
| DarkMagic | tower | DIFF (6) tower_hits[0].damage 48/97 | DIFF (6) tower_hits[0].damage 48/97 | PASS (0) |
| DarkMagic | cluster | DIFF (62) tower_hits.count 27/6 | DIFF (62) tower_hits.count 27/6 | PASS (0) |
| DarkMagic | support | PASS (0) | PASS (0) | PASS (0) |
| Vines | tower | PASS (0) | PASS (0) | PASS (0) |
| Vines | cluster | DIFF (48) tower_hits.count 26/23 | DIFF (9) enemy_hits[2].tick 70/74 | PASS (0) |
| Vines | support | PASS (0) | PASS (0) | PASS (0) |
| Rage | tower | PASS (0) | PASS (0) | PASS (0) |
| Rage | cluster | PASS (0) | PASS (0) | PASS (0) |
| Rage | support | DIFF (4) tower_hits[0].tick 194/190 | PASS (0) | PASS (0) |
| Clone | tower | PASS (0) | PASS (0) | PASS (0) |
| Clone | cluster | PASS (0) | PASS (0) | PASS (0) |
| Clone | support | DIFF (25) tower_hits.count 8/9 | PASS (0) | PASS (0) |
| Graveyard | tower | DIFF (17) Skeleton[0].ready 53/55 | PASS (0) | PASS (0) |
| Graveyard | cluster | DIFF (41) Skeleton[0].ready 83/85 | DIFF (16) enemy_hits.count 15/17 | DIFF (16) enemy_hits.count 15/17 |
| Graveyard | support | DIFF (79) Skeleton[0].ready 88/90 | DIFF (42) tower_hits.count 28/33 | DIFF (42) tower_hits.count 28/33 |
| GoblinCurse | tower | PASS (0) | PASS (0) | PASS (0) |
| GoblinCurse | cluster | DIFF (80) Goblin[0].ready None/112 | DIFF (77) Goblin[0].ready None/112 | DIFF (70) Goblin.count 8/6 |
| GoblinCurse | support | PASS (0) | PASS (0) | PASS (0) |
| Snowball | tower | PASS (0) | PASS (0) | PASS (0) |
| Snowball | cluster | DIFF (5) tower_hits[1].tick 187/185 | DIFF (5) tower_hits[1].tick 187/185 | DIFF (5) tower_hits[1].tick 187/185 |
| Snowball | support | PASS (0) | PASS (0) | PASS (0) |
| Mirror | mirror | PASS (0) | PASS (0) | PASS (0) |

## Other-card regressions

Across all 168 scenarios of the other 56 cards, both B2 arms have **exactly the same verdict
and full compare() difference list** as baseline. No passing scenario became DIFF, either
inside or outside B2. This fidelity-pool finding does not imply C56 parity: the separate
real-fixture gate caught BarbLog's 50 ms spawn delay regression, absent from this 66-card pool.

## C56 gate (frozen original B2)

Host 04, `/mpac/sdicks02/jobs/clasher/cards/b2/`. Exact launch:

```sh
REUSE_PINNED=1 setsid /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_job.sh 8 bash /mpac/sdicks02/jobs/clasher/cards/b2/fid/gate.sh
```

Own PID/PGID 2737392, held by a shell waiting on that exact PID; no pgrep/pkill used.
All Python gate work uses nice 15. Batch A's PID 2388512 was already gone and no Batch A job
was signaled or changed. `gate.pid`, `gate.log`, and `gate.exit` record this run; the exact-PID wait returned 0.
Fixtures ran 2026-10-16T02:20:23Z–02:46:34Z; roots and comparison finished afterward.

Root `rt` mirrors r1 symlinks except `engine-rs → gtree`, `src → gtree/py/src`, and
`gamedata.json → gtree/py/gamedata.json`. 04 gtree/gout were copied from frozen 08 copies.
Native SHA256: `df5443abf6d629fc34fded6fbc515ea40c70ecd6efe6693e379462500b617488`.
Pinned native: `681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b`.
Gate-tools and roots were copied from 04 Batch A and rsync checksums found no differences.

Pinned arm reused from the completed PASS Batch A gate: 577 fixture rows and four root
shards, each 150 records + a header (600 records, 300 sampled roots). Copied files, not
links. Same host, runtime r1, native SHA, gate tools, recorded fixture data, roots, sample
seed 20261015, sample 300, shards i/4, and PYTHONHASHSEED=0; root header has command/opponent
delay 27, horizon 160, interval 10, elixir weight 1.0. Runtime/data source timestamps predate
Batch A's run. Baseline Batch A itself passed 577/577 fixture records and 600/600 root records.

| Check | Result | Evidence |
|---|---|---|
| Fixture complete-record equality | **FAIL: 410/577 identical** | 167 different; first v4-phase-a-1975100701 |
| Rust-only native chains | **FAIL: 410/577 equal** | 1,010,680 ticks; zero errors in either arm; first digest divergence t1439 |
| Roots, full | **PASS: 300/300 identical** | Fixed sample of 300 recorded roots |
| Roots, cut | **PASS: 300/300 identical** | Same roots, hand/cycle config |
| Overall requested frozen B2 | **FAIL** | Fixture trajectory equality required 577/577 |

The final comparison is retained in [evidence/gate-compare.json](evidence/gate-compare.json);
input hashes and symlinks are in [evidence/gate-provenance.json](evidence/gate-provenance.json).
The 600 equal root records cover 9,336 rollout values, 1,800 select calls, 478 apply_discrete
cases, and 1,800 step checks across 12 games, absolute ticks 140..5570. Python/native full
fixture parity counts remain 429/577 in each arm; that count does not imply native trajectory
equality between arms.

Process exit status only indicates runner completion: the gate verdict is computed from
record equality and error counts in compare.json, not from a zero shell exit.

See [GATE-TRIAGE.md](GATE-TRIAGE.md) for precise owner fix and one-hunk bisect: all 2402
digest and snapshot hashes in the first failing fixture match pinned after reverting only
the RollingProjectile deploy-delay hunk in an 08 scratch gtree. Diagnostics detail/phase_step
confirm the Barbarian deploy/target/movement transition. A full 56-card C56 native-normalized
config export has only the four BarbLog timing differences; the scratch revert removes all
four ([evidence](evidence/c56-config-diff.json)). No frozen gate engine code was changed.

## Native-diff mixed repros

The old run failed at import (`ModuleNotFoundError: es_common`). `tools/run_mixed.sh` fixes
PYTHONPATH by including r1's `reports/strategy_council_20260928/engine-speed`, runs from
08 b2/root, uses frozen gout, and takes `cpu_job.sh 1` with nice 15. Summary output is
08 `fid/mixed-b2.json`; exited 0. The tooling now also retains per-game full diagnostics.

| Game | B2 outcome | Ticks | First mismatch |
|---|---|---:|---|
| 75 | MATCH | 3600 | None |
| 416 | MATCH | 3600 | None |
| 133 | MATCH, game over | 3254 | None |
| 509 | MISMATCH | 3600 | Digest, t341 |

Game 509: Python creates IceGolemite entity 49; native does not (`next_id` 50 vs 49).
The new entity/ID difference appears in the object phase in diagnostics.phase_step. It has
no exception/panic. Its signature matches the known IceGolemite config-export gap documented
in [native-diff RESULTS](../native-diff/RESULTS.md): `differential.config` creates the death
area only for the `IceGolem` alias, while this pool requests `IceGolemite`. The prior
native-diff report assigned game 509 to Mirror × SkeletonBalloon; this rerun reports its
new first failure without assuming it is the old cause. This is separate from the C56
BarbLog regression. Full evidence
08 `fid/mixed-509-details-game-509.json` (retained by an extra one-game diagnostic rerun).

## Review r1: dash-travel exclusion audit (native == Python)

Python is the reference: during Bandit / Boss Bandit dash travel `BanditDash.allows_effect` makes
`Entity.can_receive_effect` (and so `can_receive_area_damage`, `apply_slow`, `apply_periodic_damage`, forced
movement) false. `apply_haste`, the Heal Spirit pulse and Clone have no effect gate in Python and none in native
(kept). Only BanditDash bodies dash, so every guard below is C56-inert.

Probe `tools/probe_dash_paths.py` (127x08 `b2m/fid/dash-final-*.json`, native `58f99374`): for each source and each
offset L = -4..35 ticks between the cast and a forced dash launch (Python `BanditDash._launch_dash` toward the enemy
King Tower; L > 0 casts in Python before the export, L <= 0 exports first and casts in both engines), both engines
step 45 ticks; every tick compares battle_digest, the Bandit's hp / position / stun / slow count / periodic-buff count
/ hastes / freeze expiry / shield, and every scope area's state. "Exercised" = runs in which the Bandit was in dash
travel within 4 tiles of the cast while the spell object was alive or on the cast tick.

| Path (native site) | Probe source(s) | Native fix | Mismatches blue / red (of 40) | Exercised blue / red |
|---|---|---|---|---|
| area_targets: periodic damage, slow, pull (`c56.rs:area_targets`) | Poison, Earthquake, Tornado | B2: skip dash travel | 0 / 0 each | 40, 40, 24 / same |
| pull carried into the dash (`lib.rs:collide`) | Tornado (pull queued the tick before launch) | review r1: a dashing unit consumes its queued controlled vector (Python begin_movement_tick); was dropped | 0 / 0 (was 20 / 20) | 24 / 24 |
| scope_targets: Curse marks + conversion, Vines catch ranking, Void tier count (`scope.rs:scope_targets`) | GoblinCurse, Vines, DarkMagic | review r1: skip dash travel before counting / ranking | 0 / 0 each (old native: Vines 6, Void 6 offsets) | 40 / 40 each |
| scope periodic install (`scope.rs:scope_periodic`) | GoblinCurse, Vines | review r1: defensive dash guard | 0 / 0 | 40 / 40 |
| freeze (`scope.rs:freeze_for`) | Freeze, Vines snare | pre-existing guard | 0 / 0 | 40 / 40 |
| direct damage / stun (`lib.rs:damage`, `c56.rs:stun_target_mode`) | Zap, Arrows, Rocket | pre-existing guard | 0 / 0 each | 5, 31, 40 / same |
| knockback (radial and rolling) | Fireball, Snowball, Log, BarbLog | pre-existing | 0 / 0 each | 34, 27, 5, 5 / same |
| chain / ranked strike | Lightning, ElectroSpirit | pre-existing | 0 / 0 each | 14, 5 / same |
| spirit freeze | IceSpirit | pre-existing | 0 / 0 | 5 / 5 |
| rage haste (`scope.rs:haste_scan`) | Rage (own) | none: Python apply_haste has no gate either (kept) | 0 / 0 | 40 / 40 |
| heal (`scope.rs` Heal) | Heal Spirit (own) | none (Python HealPulse ungated) | 0 / 0 | 5 / 5 |
| clone | Clone (own) | none (Python CloneSpell ungated) | 0 / 0 | 5 / 5 |

"5" = only the five lockstep cast offsets (instant effects, or a body that leaves the 4-tile window at once); the
rolling Log/BarbLog contact with a dashing Bandit is therefore covered only at the cast tick.

## Review r1: Clone slide settling

`battle.py:_advance_clone_slide` and `clone.rs:advance_clone_slide` now settle each fixed step as RoyaleSim's
`spell::settle` does, with this engine's primitives: clamp to the arena (0..17999 / 0..31999); for a ground unit a
step into an alive building's footprint (|dx|, |dy| < building radius + own radius) is refused (settle's unresolved
fallback, the old point); then the river recovery the knockback uses (`recover_native_ground_position`, native
`recover_ground`). Timing unchanged (10 steps after the movement phase, route dropped on the last).
Probe `tools/probe_clone_bounds.py` (08 `b2m/fid/f-clone-bounds.json`), both seats, native == Python every tick:
Knight at (4.5, 0.5): copy ends at (3.719, 0.25) (was (5.38, -0.38)); Knight at (9.0, 14.6): the original's steps into
the river are recovered to land; Knight at (3.5, 8.6): the copy stops at y 8.036 at its princess tower's footprint.


## Review r2: complete saved entity-site inventory (2026-10-16 UTC)

The review-r1 table above is superseded as evidence of selector completeness: digest equality did not expose
Lightning ranking or remembered-hit-set differences. The r2 patch is WIP, built but **not yet verified**.
The existing verification launcher remains queued; none of the r2 rows below is a test PASS.

Original mechanical inventory (saved scanner): `cd engine-cards/src && python3 /tmp/b2sites.py`.
The saved `/tmp/b2sites.py` and `/tmp/b2sites3.txt` are preserved as the scanner and
[evidence/native-entity-sites-r2.tsv](evidence/native-entity-sites-r2.tsv). The actual raw scan contains
**84 matches**, including repeated hit-ID writes, phase dispatch and one non-entity route loop. This table
expands the handoff's provisional “39 selectors + 34 other sites” into every raw match rather than dropping
bookkeeping matches to meet that count. Multiline entity iteration is included. This is a regex inventory
plus manual pairing, not a claim that regex proves every possible selector was found. Native line numbers
refer to the current r2 WIP. Python paths below are relative to `engine-cards/py/src/clasher/`.

Python's `can_receive_area_damage` delegates to `can_receive_effect`; `BanditDash.allows_effect` excludes travel.
**Ordinary targetability, chain node selection, haste, healing and Clone use different gates**; a blanket
dash exclusion at those selectors would disagree with Python. “Static only” means paired by source inspection,
without a dedicated dynamic dash-contact test in this sweep. Source coverage is not proof of event coverage.

| Native site / function | Python counterpart | Guard / reason | Probe and current evidence |
|---|---|---|---|
| `astar.rs:31` `route` | native_pathfinding route cell initialization | Not an entity loop: regex false positive for route nodes. | Static only; no target admission. |
| `attacks.rs:22` `secondary_recipients` | mechanics/shared/multi_target.py:MultipleTargetAttack._ordered_secondary_targets | can_attack_target; dash is targetable; damage/status independently reject travel. Keep selector ungated. | Static pairing; no dedicated multi-target count probe. |
| `c56.rs:176` `bomb_tick` | entities.py:BombExplosion.update | can_receive_area_damage before blast recipients; explicit !dash_travel added. | No dedicated bomb/death-container dash overlap; Mirror scenarios queued. |
| `c56.rs:318` `chain_tick` | entities.py:ChainLightning._find_next_target / _can_chain_to / update | Secondary targetability permits dash nodes; visited_ids is recorded even when can_receive_effect rejects damage. Keep selection and record ungated. | electro_spirit, electro_dragon (queued). |
| `c56.rs:399` `chain_tick` | entities.py:ChainLightning._find_next_target / _can_chain_to / update | Secondary targetability permits dash nodes; visited_ids is recorded even when can_receive_effect rejects damage. Keep selection and record ungated. | electro_spirit, electro_dragon (queued). |
| `c56.rs:436` `area_targets` | entities.py:AreaEffect._apply_effects / _apply_damage | can_receive_effect / can_receive_area_damage excludes travel before slow/periodic/pull. | earthquake, poison, tornado (queued). |
| `c56.rs:498` `c56_area_tick` | entities.py:AreaEffect._apply_effects | Freeze recipient query uses can_receive_effect; explicit !dash_travel added to one-shot freeze scan. | freeze (queued). |
| `c56.rs:650` `ranked_strike_tick` | entities.py:RankedStrikeArea.update | can_receive_area_damage BEFORE HP ranking and struck_ids write; !dash_travel added. | lightning + mutant A deleting this guard (queued). |
| `c56.rs:670` `ranked_strike_tick` | entities.py:RankedStrikeArea.update | can_receive_area_damage BEFORE HP ranking and struck_ids write; !dash_travel added. | lightning + mutant A deleting this guard (queued). |
| `champions.rs:66` `bind_champion` | battle.py champion ability-owner bookkeeping | Live champion ownership binding; no damage/effect admission. | Static only; no new dash filter. |
| `champions.rs:82` `refresh_champion_owner` | battle.py champion ability-owner bookkeeping | Select owning champion body by group, not an effect recipient. | Static only; no new dash filter. |
| `champions.rs:115` `refresh_dead_champions` | battle.py champion ability-owner cleanup | Refresh group ownership after death; no target effects. | Static only; no new dash filter. |
| `champions.rs:126` `ability_owner` | battle.py champion ability-owner lookup | Identify ability owner; dash does not erase ownership. | Static only; no new dash filter. |
| `clone.rs:6` `clone_spell` | spells.py:CloneSpell.cast | Friendly alive non-clone Troop query; no can_receive_effect gate in Python. Keep ungated. | clone + B2 scenarios (queued). |
| `clone.rs:44` `slide_blocked` | battle.py:BattleState._advance_clone_slide blocked() | Building footprint geometry; buildings cannot dash. | Clone bounds queued; reviewed recovery/building case still needs dedicated assertion. |
| `deployment.rs:6` `prepare_placement_mask` | battle.py / placement.py building placement masks | Alive Building footprint cache and bounds, not damage targets. | Static only; no dash guard appropriate. |
| `deployment.rs:16` `prepare_placement_mask` | battle.py / placement.py building placement masks | Alive Building footprint cache and bounds, not damage targets. | Static only; no dash guard appropriate. |
| `deployment.rs:41` `child_position_clear` | battle.py child placement validation | Placement occupancy; no combat-effect admission. | Static only; no dash guard appropriate. |
| `deployment.rs:78` `recruit_positions` | battle.py recruit group placement | Building footprint geometry used for spawn positions. | Static only; no dash guard appropriate. |
| `hook.rs:36` `hook_candidate` | cards/fisherman.py:FishermanHook target selection | Targetability/range check, not can_receive_area_damage; dash targeting is permitted; hook movement has its own rules. | Static only; no dedicated Fisherman probe in current 31-source sweep. |
| `hook.rs:83` `hook_move_valid` | cards/fisherman.py hook movement destination validation | Alive Building footprint geometry; not effect recipients. | Static only; no dash guard appropriate. |
| `leap.rs:45` `leap_slam` | cards/mega_knight.py:MegaKnightSlam area damage | can_receive_area_damage; existing !dash_travel retained. | mega_knight; spawn-hit timing also electro_wizard (queued; event coverage to inspect). |
| `lib.rs:844` `grouped_spell` | dynamic_spells.py direct spell / entities.py projectile grouped splash | Damage/status queries use can_receive_area_damage / can_receive_effect; new !dash_travel precedes group hit_ids update. Group lookup/propagation only shares admitted IDs. | zap, fireball, arrows, rocket, snowball (queued; inspect actual group contacts). |
| `lib.rs:847` `grouped_spell` | dynamic_spells.py direct spell / entities.py projectile grouped splash | Damage/status queries use can_receive_area_damage / can_receive_effect; new !dash_travel precedes group hit_ids update. Group lookup/propagation only shares admitted IDs. | zap, fireball, arrows, rocket, snowball (queued; inspect actual group contacts). |
| `lib.rs:868` `grouped_spell` | dynamic_spells.py direct spell / entities.py projectile grouped splash | Damage/status queries use can_receive_area_damage / can_receive_effect; new !dash_travel precedes group hit_ids update. Group lookup/propagation only shares admitted IDs. | zap, fireball, arrows, rocket, snowball (queued; inspect actual group contacts). |
| `lib.rs:879` `grouped_spell` | dynamic_spells.py direct spell / entities.py projectile grouped splash | Damage/status queries use can_receive_area_damage / can_receive_effect; new !dash_travel precedes group hit_ids update. Group lookup/propagation only shares admitted IDs. | zap, fireball, arrows, rocket, snowball (queued; inspect actual group contacts). |
| `lib.rs:1010` `spirit_tick` | entities.py:Troop spirit impact splash | can_receive_area_damage / can_receive_effect on fresh damage/status queries; explicit !dash_travel added. | ice_spirit, fire_spirits (queued). |
| `lib.rs:1031` `spirit_tick` | entities.py:Troop spirit impact splash | can_receive_area_damage / can_receive_effect on fresh damage/status queries; explicit !dash_travel added. | ice_spirit, fire_spirits (queued). |
| `lib.rs:1073` `area_tick` | entities.py:AreaEffect._apply_effects | can_receive_effect excludes travel before writing slow_ms; explicit !dash_travel added. | poison, freeze (queued; legacy area path not independently forced). |
| `lib.rs:1148` `rolling_tick` | entities.py:RollingProjectile._damage_entities_at | can_receive_area_damage BEFORE hit_entities write; new dash_travel reject precedes both building and troop records. | log, barblog + mutant B deleting this guard (queued). |
| `lib.rs:1155` `rolling_tick` | entities.py:RollingProjectile._damage_entities_at | can_receive_area_damage BEFORE hit_entities write; new dash_travel reject precedes both building and troop records. | log, barblog + mutant B deleting this guard (queued). |
| `lib.rs:1179` `can_deploy_anywhere` | battle.py / placement.py deployment permission | Tower/building placement occupancy; no effect target. | Static only; no dash guard appropriate. |
| `lib.rs:1196` `can_deploy` | battle.py:BattleState.can_deploy_card | Deployment building/champion constraints; not effect admission. | Static only; no dash guard appropriate. |
| `lib.rs:1214` `can_deploy` | battle.py:BattleState.can_deploy_card | Deployment building/champion constraints; not effect admission. | Static only; no dash guard appropriate. |
| `lib.rs:1245` `footprint_blocked` | battle.py / placement.py placement footprint check | Alive buildings block geometry irrespective of effects. | Static only; no dash guard appropriate. |
| `lib.rs:1254` `payload_blocked` | battle.py / placement.py payload placement check | Building footprint bounds; no effect target. | Static only; no dash guard appropriate. |
| `lib.rs:1310` `index` | battle.py:entities.get(id) | ID resolution only; caller owns target validity. | Static only; no blanket dash guard (would break permitted locks). |
| `lib.rs:1317` `pending_lethal` | entities.py:_pending_damage_retargets_hit | Pending projectile reservation sum; not impact admission or hit recording. | Static only; no new dash guard. |
| `lib.rs:1368` `target_candidate` | entities.py target acquisition / fallback crown targets | is_targetable_by / can_attack_target permit ordinary dash locks; channel-specific ramp filter rejects travel. Crown fallback only buildings. | Troop sources exercise acquisition; no exhaustive targeting proof. |
| `lib.rs:1484` `target_candidate` | entities.py target acquisition / fallback crown targets | is_targetable_by / can_attack_target permit ordinary dash locks; channel-specific ramp filter rejects travel. Crown fallback only buildings. | Troop sources exercise acquisition; no exhaustive targeting proof. |
| `lib.rs:1497` `target_candidate` | entities.py target acquisition / fallback crown targets | is_targetable_by / can_attack_target permit ordinary dash locks; channel-specific ramp filter rejects travel. Crown fallback only buildings. | Troop sources exercise acquisition; no exhaustive targeting proof. |
| `lib.rs:1545` `occupied` | battle.py / native_pathfinding.py ground occupancy | Alive buildings populate path occupancy. | Static only; no dash guard appropriate. |
| `lib.rs:1813` `collide` | battle.py:BattleState._accumulate_troop_collision_for | is_in_transit excludes dash pressure bodies; queued controlled vector remains consumable while dashing (r1 fix). | tornado (queued). |
| `lib.rs:2463` `combat_one` | entities.py:Entity._snapshot_attack_area_targets_at | can_receive_area_damage excludes travel; explicit !dash_travel added to melee splash recipients. | valkyrie, mega_knight (queued; actual melee contact to inspect). |
| `lib.rs:2901` `tick_once` | battle.py movement building signatures | Alive Building IDs for path cache; no effect recipients. | Static only. |
| `lib.rs:2913` `tick_once` | battle.py:BattleState.step | Start-of-tick alive eligibility snapshot; no effect admission. | Scenario suites queued. |
| `lib.rs:2914` `tick_once` | battle.py:BattleState.step combat phase | Dispatch combat to alive actors; each selector guards recipients. | Scenario suites queued. |
| `lib.rs:2924` `tick_once` | battle.py:BattleState.step movement phase | Actor movement dispatch; Clone slide bypass retained. | Clone bounds + scenarios queued. |
| `lib.rs:2932` `tick_once` | battle.py:BattleState._advance_clone_slide | Slide actor update; no effect target admission. | Clone bounds queued. |
| `lib.rs:2937` `tick_once` | battle.py:BattleState.step building lifetime | Lifetime decay may spawn death payloads; buildings cannot dash. | First-update path suite queued. |
| `lib.rs:2950` `tick_once` | entities.py periodic damage update / battle.py step | Updates installed periodic buffs; admission is guarded separately. | poison, goblin_curse, vines queued. |
| `lib.rs:2957` `tick_once` | entities.py buff aging / battle.py step | Age haste/slow/freeze state on actors; no new effect recipients. | All buff-source rows queued. |
| `lib.rs:3036` `tick_once` | battle.py projectile impact phase live-set bookkeeping | Start-of-object live ID set used for dragon hook; not an area selector. C1 owns hook timing. | electro_dragon queued; C1 coordination required. |
| `lib.rs:3087` `tick_once` | entities.py:Projectile._collect_splash_targets | can_receive_area_damage before impact victim query; explicit !dash_travel added. | princess, ice_wizard, hunter queued. |
| `lib.rs:3127` `tick_once` | entities.py:Projectile._collect_splash_targets (zero-radius branch) | can_receive_area_damage on endpoint overlap; explicit !dash_travel added. | Troop projectile sources queued. |
| `lib.rs:3266` `tick_once` | battle.py post-object dead ID collection | Dead/spirit ID set for target cleanup, not live target acquisition. | Scenario suites queued. |
| `lib.rs:3272` `tick_once` | battle.py post-object target cleanup | Clear stale target references to dead/spirit bodies; dash is alive. | Scenario suites queued. |
| `lib.rs:3299` `tick_once` | battle.py dead-tower activation | Dead Tower owners wake Kings; no dash bodies. | Static only. |
| `lib.rs:3308` `tick_once` | battle.py projectile endpoint preservation on removal | Remember dead-body coordinates; not effect admission. | Scenario suites queued. |
| `lib.rs:3314` `tick_once` | battle.py projectile endpoint preservation on removal | Refresh pending homing aims from removed-body positions. | Scenario suites queued. |
| `lib.rs:3329` `tick_once` | battle.py game-over king check | Building-only win check. | Static only. |
| `lib.rs:3344` `tick_once` | battle.py overtime crown count | Building-only win check. | Static only. |
| `lib.rs:3359` `tick_once` | battle.py overtime minimum tower HP | Building-only win check. | Static only. |
| `lib.rs:3385` `activate_king` | battle.py tower activation | Wake friendly King Tower; buildings cannot dash. | Static only; no dash guard appropriate. |
| `lib.rs:3403` `damage` | entities.py:Entity.take_damage / damage ramp hooks | Existing dash immunity checked before damage; entity iteration interrupts other ramp beams after damage. | All damaging sources; ramp reset loop static only. |
| `lib.rs:3452` `death_effects` | mechanics/shared/death_effects.py:DeathDamage.on_death | can_receive_area_damage excludes travel; explicit !dash_travel added to death splash victims. | No dedicated death-blast overlap in current sweep. |
| `lib.rs:3575` `hex_digest` | es_common.py:battle_digest | Serialization/hash iteration; no selector. Digest alone misses hit sets. | Full-snapshot sweep supplements digest (queued). |
| `lib.rs:3800` `apply_action` | battle.py:BattleState.deploy_card | Deployment/champion availability checks; not effect admission. | Scenario action agreement queued; no dash filter. |
| `lib.rs:3813` `apply_action` | battle.py:BattleState.deploy_card | Deployment/champion availability checks; not effect admission. | Scenario action agreement queued; no dash filter. |
| `projectiles.rs:37` `rolling_character_hits` | entities.py:Projectile rolling character hit query | can_receive_area_damage BEFORE hit_entity_ids write; !dash_travel added. | bowler (queued; actual rolling contact to inspect). |
| `projectiles.rs:47` `rolling_character_hits` | entities.py:Projectile rolling character hit query | can_receive_area_damage BEFORE hit_entity_ids write; !dash_travel added. | bowler (queued; actual rolling contact to inspect). |
| `projectiles.rs:82` `projectile_splash_status` | entities.py:Projectile._apply_impact_effects | Fresh can_receive_area_damage query after synchronous damage/death spawns; explicit !dash_travel added. | ice_wizard, electro_wizard (queued). |
| `projectiles.rs:197` `piercing_hits` | entities.py:Projectile._damage_piercing_targets_at | can_receive_area_damage BEFORE hit_entity_ids write; !dash_travel added. | magic_archer, executioner (queued; C1 owns additional boulder/axe filters). |
| `projectiles.rs:220` `piercing_hits` | entities.py:Projectile._damage_piercing_targets_at | can_receive_area_damage BEFORE hit_entity_ids write; !dash_travel added. | magic_archer, executioner (queued; C1 owns additional boulder/axe filters). |
| `scope.rs:136` `haste_scan` | scope_spells.py Rage / entities.py:Entity.apply_haste | Friendly recipients; apply_haste has no can_receive_effect gate. Keep ungated. | rage (queued). |
| `scope.rs:167` `remember_cursed_dead` | scope_spells.py:GoblinCurseArea corpse bookkeeping | Scope existence / dead-body capture / update already-marked targets; no new curse admission. | goblin_curse (queued). |
| `scope.rs:174` `remember_cursed_dead` | scope_spells.py:GoblinCurseArea corpse bookkeeping | Scope existence / dead-body capture / update already-marked targets; no new curse admission. | goblin_curse (queued). |
| `scope.rs:180` `remember_cursed_dead` | scope_spells.py:GoblinCurseArea corpse bookkeeping | Scope existence / dead-body capture / update already-marked targets; no new curse admission. | goblin_curse (queued). |
| `scope.rs:218` `internal_spawn_valid` | scope_spells.py Graveyard / curse spawn-position validation | Alive Building footprint geometry, not damage recipients. | graveyard/curse scenarios queued; no dash filter. |
| `scope.rs:293` `scope_targets` | scope_spells.py:_targets | can_receive_area_damage BEFORE Void count, Vines ranking and Curse mark; r1 !dash_travel retained. | void, vines, goblin_curse (queued). |
| `scope.rs:489` `scope_tick` | scope_spells.py:HealPulse.update | Friendly Troop snapshot; Python healing has no effect gate. Keep ungated. | heal (queued). |
| `souls.rs:14` `collect_souls` | mechanics/champion/skeleton_king.py soul collection | Counts dead enemies, not live effect recipients. | Static only; no live dash guard appropriate. |
| `spawn.rs:32` `spawn_push_hook` | mechanics/shared/spawn_pushback.py:SpawnPushback.on_spawn | can_receive_forced_movement / can_receive_effect rejects travel; explicit !dash_travel added. | electro_wizard, mega_knight (queued; exact spawn-push coverage to inspect). |
| `spawn.rs:132` `production_tick` | cards/goblin_hut.py:GoblinHutProduction enemy proximity | is_targetable_by and sight/range gate production, not area damage; dash remains targetable. | Static only; no dedicated gated-production probe. |


The saved scanner had a word-boundary bug after `self.entities.len()` and did not match `hit_ids.extend`.
The corrected explicit-directory scanner additionally returns these **four** sites (**88 raw matches total**;
[expanded inventory](evidence/native-entity-sites-r2-expanded.tsv)). The old scanner and 84-row output remain
unchanged in evidence for provenance. No new engine selector defect was found in these four sites:

| Native site / function | Python counterpart | Guard / reason | Probe and current evidence |
|---|---|---|---|
| `lib.rs:870` `grouped_spell` | grouped projectile damage_group_hit_entity_ids update | Shares IDs from the guarded recipient list, no second admission. | Arrows / grouped direct, corrected harness unverified. |
| `lib.rs:1125` `rolling_tick` | entities.py:RollingProjectile._damage_entities_at | Indexed scan admission; dash guard precedes both hit-ID write sites already listed. | Log + mutation B, corrected harness unverified. |
| `lib.rs:1891` `avoidance_grid` | battle.py troop avoidance grid population | Spatial bookkeeping; collision recipient rules are in collide(), already audited. | Static pairing, Tornado pressure path. |
| `lib.rs:3239` `tick_once` | battle.py pending projectile reservation update | Post-object homing duration reservation, no damage recipient or hit-set write. | Projectile paths, no dedicated reservation-only dash assertion. |

Reproduce the expanded scan from the worktree root:
`python3 reports/cards/b2/tools/native_entity_sites.py engine-cards/src`.

### Full-snapshot sweep and mutation controls: pending

`tools/probe_dash_full.py` retains the 40 offsets (-4..35), two seats and 45 ticks per run,
adding 11 troop sources to the 20 spell/spirit sources. Each tick compares digest plus all live entity
`live_snapshot.live_entity` export keys against `native.snapshot()`: hit IDs, chain/strike targets,
periodic buff records, slow/haste records, freeze, scope state, HP, positions, routes and clocks.
It also checks entity IDs, player elixir/hand/cycle and next_id. The current script is **not a byte-identical
comparison of the entire root snapshot**: root RNG, pending casts, game flags, placement caches, player
refill/history and native-only keys are not all compared. Independent harness review is in progress.

Current canonicalization: floats round to 6 decimals; hit_ids compare as sets; absent native fields may
match Python default values; -1/0 are equivalent only for finish_tick/landed_tick/push_tick. Current
exclusions are birth, route_occupied and cooldown, plus Projectile age/attacked_current/lane/last_target/
started and Projectile stats max_hp/sight. The previous worker observed these in no-dash tower-arrow and
dash-without-spell controls (`b2m/fid/noise2.py`), but they remain comparison limitations, not proof that
those fields can never carry a mechanics bug. Hit IDs, shot targets and buff records are not excluded.

Frozen builds on 08:
- final `b2m/out4`: `7738f9d2c4c2b9f900fda60b69b70976faed186975662838b3b2af1f82a2e7ff`
- mutant A `b2m/mutA`: `ff74a2fc8cfb7e78c60d0c1eb9e0880aebab8fb010939b2fa9d0eb6cfe01ee33`
  (only ranked-strike dash guard removed from `treeA/src/c56.rs`).
- mutant B `b2m/mutB`: `2964dec34f8a0a29c9352e249e7e87e77adfce7bcdc908bdbb1443fb8b4265f3`
  (only rolling_tick dash guard removed from `treeB/src/lib.rs`).

Expected negative controls: A must fail Lightning; B must fail Log, including a hit-set-only difference
when digests agree. No detection result is available yet. `run_r2.sh` uses background children and `wait`
without collecting individual exit codes; **r2.done alone is a completion marker, never a PASS receipt**.
All expected JSON/log records, errors and mutation detections must be inspected before claiming success.

### Clone recovery revalidation

The r2 WIP makes one bounded recovery round in `clone.rs:advance_clone_slide` and
`battle.py:_advance_clone_slide`: refuse a proposed building overlap, recover to ground, then check both
building overlap and water again. Failure falls back to the old point. This addresses the reviewed
Cannon (8,14) / Knight (9.15,14.95) / slide [0,125,10] recovery case without an unbounded solver. The old
point is assumed legal; no new general initial-position solver was introduced. Current `probe_clone_bounds.py`
covers arena/river/tower cases but does not yet assert that exact combined water/building case; independent
review will check the bounded supplemental test needed. No new Clone validation result is claimed.

### Queue / gate disposition

At 2026-10-16T09:07:13Z, 08 PID/PGID **561530** is alive under `cpu_job.sh 8`, child **561552**
in `cpu_room.sh 8`. `lease-561530` is absent because it is still waiting for room; `fid/r2.done` is absent.
The launch command and hashes are in PROGRESS.md. C1 PID **1042473** remains independently queued under
`cpu_job.sh 4`; B2 did not modify it. Superseded 04 B2 gates 2123864 / 2553495 are absent.
No `b2-merge3` has been launched in this resume; it awaits reviewed scripts, verified r2 evidence and
lead coordination. B2 must integrate before C1; C1 owns new boulder/axe filters, B2 owns target exclusion.


### Sol resume: independent harness findings and corrected local version

**The queued r2 full-snapshot sweep is provisional, not an acceptance gate.** Independent harness review
found that enemy Log/BarbLog/ElectroSpirit/IceSpirit casts at (9,13.5) are illegal, while rejected casts
were silently retained as apparent successful runs. The old overlap counter can count such rejected casts
and unrelated tower arrows. This also invalidates r1 claims of rolling/Spirit event coverage in the table
above; those rows must be re-established. Merely producing r2.done cannot repair that gap.

The corrected scripts exist only in this worktree; they have **not** replaced the queued host files.
[evidence/queued-r2-probe.py.txt](evidence/queued-r2-probe.py.txt) and
[evidence/queued-r2-run.sh.txt](evidence/queued-r2-run.sh.txt) preserve the queued version.

- `probe_dash_full.py`: enemy rolling deployments move to legal (9,18.5), Spirits to (9,17.5), mirrored for
  the other seat. Every cast must succeed; all 40 per-seat run records retain acceptance/errors and first
  differences. Actual source-named Python guard queries during dash travel replace proximity counts.
  Heal receives an injured friendly Bandit, but healing-pulse overlap is not claimed without separate evidence.
- Complete Python root exports are canonicalized through `BattleState(snapshot(...)).snapshot()` **without
  stepping** (constructor checked in lib.rs: serde plus dimension validation). This supplies the actual serde
  defaults, comparing native-only optional state too, instead of treating arbitrary missing fields as defaults.
  Both-direction comparisons include pending casts, complete players, RNG, game flags, placement and champion
  bookkeeping. Static config is omitted from equality, with its source inputs hashed in the run identity.
  Only Troop cooldown/route_occupied and specifically Tower-arrow representation fields remain excluded;
  unrecorded birth and unset-tick normalization remain explicit. Changed game state is never normalized away
  merely because a digest agrees. Every discovered difference is retained with real paths and values.
- `probe_clone_recovery.py`: exact injected active-slide fixture, Cannon (8,14), Knight (9.15,14.95),
  [0,125,10], mirrored for red, ten ticks. Assert arena/water/building legality in each engine, blue fallback
  to the old legal point, digest/positions and slide completion. This complements public Clone-cast scenarios.
- `run_r2.sh` / `validate_r2.py`: require a fresh tag other than r2; exclusive identity before work; exact
  child PIDs and exit receipts; eight workers then three under the same outer lease (Clone checks sequential
  in one worker); exact expected JSON case/seat/offset/action counts; no probe exceptions; baseline success;
  mutant A must reveal Lightning RankedStrikeArea hit_ids in both seats; mutant B must reveal Log
  RollingProjectile hit_ids in both seats **while the digest agrees**. Only then write an atomic PASS receipt.
  The first-update validator explicitly allows zero actions only for its six declared setup-only fixtures.
  Identity hashes cover native libraries, all engine Rust/Python including top-level exporters, fid tools,
  pool.json, es_common.py and both gamedata arms; validate unchanged inputs again at completion.
- `test_r2_harness.py`: **8/8 stdlib-only local tests PASS**, 0.001 s. Checks include rejection/error handling,
  unrelated mutation failure rejection, duplicate offsets, native-only optional state, buffs/pending casts,
  hit-set ordering/duplicates, declared zero-action cases and multiline/range/extend inventory matching.
  Python AST parsing and `bash -n` PASS; no simulations/builds ran on 05.

Harness review r1 rejected the original script's evidence gaps. Harness review r2 rejected the first correction
for legitimate zero-action fixtures and omitted exporter/pool provenance; both were corrected. Final harness
review **APPROVED FOR BOUNDED TEST EXECUTION** (fresh Sol high; exact six-file hashes in
[evidence/harness-review-approved-20261016.json](evidence/harness-review-approved-20261016.json)). **No corrected dynamic parity, mutation-control detection or new C56 PASS is claimed.**
Engine review readiness awaits valid dynamic receipts and eventual B2→C1 integration coordination.

### Current authority / decisions (supersedes earlier blanket hold wording)

Sam's 2026-10-16 update permits routine confident reversible fixes and reviewed releases/pin changes within
existing ownership once meaningful independent review/parity/coverage gates pass, with exact receipts and
rollback. Earlier blanket Opus/promotion holds in this thread are retired, not erased. The present acceptance
blockers are invalid/incomplete evidence and required independent host-script review, not a promotion label.
B1 retains its GoblinGiant Clone attachment, BattleHealer Mirror/config/heal and ThreeMusketeers dependency
fixes. B2 retains spell dash exclusions / Clone slide bounds. C1 retains boulder/axe filters; B2→C1 order stays.
Coordination questions go directly to the CARD LEAD parent via t3_thread_send(mode=auto), with evidence,
recommendation and dependency status; no user-input tools. Active reviewers receive the same instruction.


### C1 integration carryovers (recorded before any merge)

C1 focused r2 `f68e5f80f` / native `631ac` has independent Sol approval. Its new shape must be audited
again after B2→C1 integration, without importing C1 queue/boulder fixes prematurely:

| Future integrated site | Python counterpart | Required follow-up | Current disposition |
|---|---|---|---|
| C1 `attacks.rs:22` `secondary_recipients` (ElectroWizard) | mechanics/shared/multi_target.py:_ordered_secondary_targets → Entity.can_attack_target | Preserve this exact candidate-count selector in the B2 class audit. Compare paired Python admission, reserved secondary IDs and downstream effects during dash travel; do not assume an area-damage gate applies to ordinary targetability. | B2-owned audit carryover; no integration yet. |
| C1 `c56.rs:309` `chain_release` (ElectroDragon) | entities.py:ChainLightning._release → _can_chain_to | New C1 release-time nearest-node selection and visited-ID write differ from B2's old chain_tick. Audit release/visited IDs, aim and eventual hit during dash; Python currently uses secondary targetability. | B2-owned audit carryover; no integration yet. |

Source inspection of both branches currently shows can_attack_target / secondary-effect targetability permits
Bandit travel while damage/status guards reject it. These rows are not silently treated as area-damage queries;
a future merged-state probe must establish the intended target/hit-ID semantics. The new C1 release shape is
explicitly pending integration validation, not covered by the old B2 chain sweep.


### Scheduling disposition update (supersedes the queued status above)

CARD LEAD authorized replacing the known-provisional frozen queue rather than waiting indefinitely.
At 09:30:50Z the independently reviewed scheduler confirmed exact owned PID/PGID/start/argv, waiting
cpu_room8 with no lease/output, then terminated **only** group561530. No live group, lease or claim
remained. Frozen files/logs are preserved; [supersede receipt](evidence/r2-superseded-20261016.json)
marks the arm **superseded-not-evidence**.

The corrected runner is now bounded to four workers (phases4/4/3) under cpu_job4/nice15, independently
reviewed with the one-shot scheduler. The staging attempt failed before extraction/launch because system
Python3.8 lacks Path.is_relative_to. No replacement job ran; the failed empty directory remains preserved.
[Failure receipt](evidence/r2v2-staging-failure-20261016.json). A separate narrowly scoped stage-only
compatibility recovery has been submitted for required independent review. No dynamic validation, mutation
detection, C56 gate or final engine acceptance result is claimed.


### Corrected bounded validation launch

The Python3.8 stage-only recovery received independent approval and ran once successfully. At
2026-10-16T09:33:56.816158Z it queued **PID/PGID3422841** on08 under cpu_job4/nice15, fresh
`b2-r2v2-20261016T0933Z`, tagr2v2. Four snapshot shards, then four mutation/FU/Clone workers,
then three scenario workers; source hashes equal the frozen already-built b2m/tree. Exact
[launch receipt](evidence/r2v2-launch-20261016.json) and
[stage-only approval](evidence/stage-recovery-review-approved-20261016.json).
At09:34:12Z it was waiting in cpu_room4 (child3422863), without a lease or outputs.
No corrected dynamic results yet. Final engine-review readiness, mutation detections and C56 parity
remain pending; no acceptance or promotion is claimed. The six engine WIP files remain preserved.


### 2026-10-16: strict run FAIL; separately versioned semantic proposal

PID3422841 admitted at approximately10:18:37Z and was terminal with no live PID/lease
at10:44:35Z. The original exact reviewed comparator remains unchanged, and its raw
FAILs remain FAILs. Terminal summaries and raw log copies are in
[evidence/r2v2-terminal-summary.json](evidence/r2v2-terminal-summary.json) and
[evidence/r2v2-raw-terminal](evidence/r2v2-raw-terminal).

| Strict shard | Completed case/seat summaries | Collector exit | Verdict |
| --- | --- | --- | --- |
| 1 | 16/16 | 0 | Raw snapshot mismatches retained |
| 2 | 16/16 | 0 | Raw snapshot mismatches retained |
| 3 | 12/16 | 1 | Config failed on unsupported Executioner name before final four rows |
| 4 | 14/14 | 0 | Raw snapshot mismatches retained |

The strict run cannot establish successful complete full-state parity. Digest-equal
raw failures include Python's unexported native historical `public_speed_base` cache
and tracking-projectile aim exported from a newer target location rather than the
committed endpoint. The original third shard's unsupported name stopped later
phases; first-update/Clone/scenario parity and both mutant controls were not run.
These absences remain explicit rather than being interpreted as passes.

CARD LEAD authorized a separate proposal under
`/mpac/sdicks02/repos/clasher-cards/reports/cards/reviews/B2-semantic-comparison-decision.md`.
[SEMANTIC-SNAPSHOT-V1.md](SEMANTIC-SNAPSHOT-V1.md) defines its field/class matrix,
source-bound descendant propagation proof, raw applicability ledger, independent
Troop base-speed comparison, committed-aim projection, unknown-class strictness,
negative controls, exact affected-run requirements and rollback. Eighteen local
stdlib controls pass; no affected dynamic execution occurred before independent
review. The original comparator and failed host run are immutable. The probe-only
aim correction does not repair the production shared exporter; that gap is explicit.

New collector uses canonical `AxeMan` for the existing `executioner` case label; a
source/data preflight checks all31 source names. A fresh affected run must retain
the same engine/native bytes, record applicability paths/raw values/reasons, detect
both-seat intended hit-set guard mutants (Log while its intended delta's digest
agrees), exercise actual non-Troop source→Troop child continuation without cache
leakage, and execute the unchanged parity phases once because the original aborted
before them. The exact proposal and affected scheduler/runner are undergoing
independent Sol-high review before execution.

No C56 gate, final engine approval or acceptance is implied by this proposal. The
six engine WIP files remain uncommitted. B2→C1 order and the two exact C1 selector
carryovers above are unchanged; no C1/B1 work has been imported.

Independent read-only Sol-high review **APPROVED FOR BOUNDED TEST EXECUTION** of the exact8 contract/tool files; [review receipt](evidence/semantic-v1-review-approved.json). Source/propagation/independent-state/count/mutation/scheduler controls passed inspection, including491 source identity checks. This approval precedes affected execution and supplies no engine acceptance or C56 result.
