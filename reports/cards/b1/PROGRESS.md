# Batch B1 (arenas 7–10 troops) — progress (restart notes)

Worker: CARD LEAD engine implementation sub-agent. Worktree /mpac/sdicks02/repos/clasher-cards-b1 (branch cards/b1, from
7720915a8 = Batch A WIP). Edits only engine-cards/** and reports/cards/b1/**.

## Layout
- 08 jobs: /mpac/sdicks02/jobs/clasher/cards/b1/
  - base/ = engine-cards @7720915a8 (copy of batchA/tree, file-hash identical); out-base/ = its native build (batchA/out, 112c0649...)
  - tree/ = rsync of patched engine-cards; root/, rootstats/, baseroot/ like batchA (rootstats -> stats/gamedata.json)
  - fid/ = fidelity tools (copies of batchA tools; stats-spec.json = batchA rows + B1 rows; 08 only, never git)
- Fidelity table: adapter (cards-15535.1 + CLIENT16402_VALUES), same as Batch A.

## Log
- 2026-10-16T01:41:40Z started. Before = batchA/fid/final-mech.jsonl rows for B1 cards (base engine = my start). Launched s0-stats (stats overlay only, no B1 mechanics) on 08 (PID 2598461).
- s0-stats done (30/30): stats overlay alone => GiantBuffer 3/3 PASS, BattleHealer knight PASS. MiniZapMachine scratch values = adapter table 2200/1400 (16.402.19 overlay: 2300/1500).
- RoyalGiant: balance.py stomp fields (stopMovementAfterMS 640, waitMS 100, sightClipSide 2000, projectileStartRadius 1200) + traits mass 18/ignorePushback => 3/3 PASS (dev-rg). GoblinGiant same stomp fields; riders still missing.
- Dev loop: reports/cards/b1/tools/fid.sh TAG rootstats CARD... (05 -> rsync 08 b1/tree -> harness, 3 workers).
- 2026-10-16T01:50:18Z resumed after usage limit; s0 PID gone (finished). Applied Batch A's uncommitted serialization diff (skip_serializing_if on min_range/death_first_update/first_update) from clasher-cards. New native fields must use skip_serializing_if too.
- 2026-10-16T01:58:58Z GiantSkeleton: + GiantSkeletonBomb deathDamageRadius 3000/deathPushback 1800, mass/ignorePushback; residual 2-tick plain-bomb fuse (bomb lands death+59 vs RS +61) is C56-shared: control Balloon alone/knight show the same 372/374 => not fixed (C56 parity).
- BattleHealer: hover arm = Ghost's direct route (slower, wrong line) vs RS walker-with-priced-water; set trait hovering False (+mass 6) => 3/3 PASS with stats. Heal mechanics (spawn heal + on-hit heal) not implemented in ours (SpawnAreaEffect ignores healPerSecond) -> TODO via HealPulse (native Effect::Heal exists).
- MiniSparkys: + MiniZapMachine overrideAttackFinishTime/attackFinishTime 0, mass 4. alone PASS; knight 2 diffs (C56 Knight's clock under ZapFreeze stun), minions 5 diffs (Z3 loses its hit when its target dies: shared legacy retarget reset). Both C56-shared clocks -> residual.
- Tools: tr.sh/trace.py (side by side), SCRIPT=pytrace.py (ours attrs); ctl-pool.json for C56 controls; run_fid.sh now honours POOL.
- 2026-10-16T02:04:40Z SkeletonBalloon: (1) FlyDirectPaths (balance flyDirectPaths; card_types.fly_direct_paths; entities._native_movement_waypoint aims at target centre; native Stats.fly_direct in waypoint) -> barrel path exact; (2) container (TimedExplosive with children) staged release: units at fuse+50ms with _first_update_spawned(collide=False), hit at fuse+100ms (RS units_at_fuse_end) -> NATIVE TODO (c56.rs bomb_tick); (3) KamikazeTime drain floor(maxHP*50/KamikazeTime)/tick from fire (entities._kamikaze_drain; native lib.rs kamikaze_drain) -> barrel death exact. minions 14->4 diffs. Residual: death slide of children collides with the tower in ours (RS slide ignores bodies, stops at water) -> later skeleton geometry; shared slide code with C56 Golem -> not changed yet.
- 2026-10-16T02:17:34Z RoyalRecruits: SummonWidth 14000 (balance ENTRY_PATH_OVERRIDES) routes to native wide formation (legacy name line kept only without the column); line centre search ported (formations.py line_centre_client, battle.py _native_line_centre/_line_territory; native deployment.rs line_centre + Card.line_search, lib.rs deploy); right-lane zigzag mirror for wide lines >=5 (formations.formation_offset; differential mirror_x). Fidelity alone/minions PASS, knight = same-tick tower-hit ordering only. 13 taps identical to RS (tapcmp.py). Native==Python: scenarios + 15 taps both seats. Not handled: taps on a princess-tower tile (ours refuses, RS relocates).
- Native build b1/out sha c22b0243... (includes fly_direct, kamikaze_drain, container bomb_tick, line_centre). Native==Python OK on SkeletonBalloon RoyalGiant GoblinGiant BattleHealer MiniSparkys GiantSkeleton RoyalRecruits.
- Checkpoint commit. Remaining: GoblinGiant riders, Hunter pellets, ThreeMusketeers, BattleHealer heal pulses, SkeletonBalloon slide residual; then 66-card fidelity + C56 gate on 04.
- 2026-10-16T02:23:58Z Hunter: MultipleProjectiles fan (entities.py Troop._create_projectile_fan; Projectile.stop_on_hit; native projectiles.rs fire_fan + piercing stop, lib.rs Stats.fan/fan_radius/fan_delay_ms/fan_stop, Entity.stop_on_hit, piercing launch_delay hold; differential._fan_stats; live_snapshot stop_on_hit) + HunterProjectile row fields (projectileRadius 300, startExtra 650, checkCollisions, randomDelay 200) + Hunter projectileStartRadius 1000. knight PASS; alone/minions same volley totals, tick spread differs only by the random holds (RS draws its own stream). Native==Python (scenarios + 5 taps). Native sha a88744ba...
