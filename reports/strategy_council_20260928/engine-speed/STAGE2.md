# Stage 2: GO for the 16-card Rust core

2026-10-03. Python remains the authoritative reference. Stage 2 passes all requested gates on the final build. No training or search backend integration was made, and no commits were created.

## Final gates

| Gate | Final result |
|---|---|
| At least 64 full public-script games | 64 terminal games, 298,540 tick boundaries, zero digest/action/RNG mismatches |
| Full horizon | 22 games reach tick 6001; all other games end at their reference outcome |
| At least 2,000 live imports | 2,048 random roots, 409,600 paired continuation ticks, zero mismatches |
| Arbitrary placements | 8,177 accepted public-mask tile placements, 523,328 paired ticks, zero mismatches |
| At least 30x step speed | Python 1320.703, Rust 66142.325 ticks/core-second, 50.081x |
| Clone below 20 microseconds | Maximum per-root mean 5.720 us; median 1.350 us, p95 3.140 us |

Each clone measurement averages 100 calls. Sampled roots contain up to 23 entities. Clone continuations leave both parents unchanged. All 37 regressions pass, including the ten frozen stopped-route variants in both scalar and fast-path modes and import of a resumable stopped route. The 4,600 MT draw checks and 2,000 A* routes also pass. Cargo formatting and focused Ruff correctness checks pass.

The same unchanged `es_common.battle_digest` format is used throughout, with all 624 MT words and the index compared independently. The admission digest does not serialize every private clock; the live-import continuation tests check their effects over 200 further ticks. Diagnostic snapshots retain additional internal fields.

## Coverage and implementation

Added Skeletons, Goblins, Cannon, Tesla, Zap, Fireball, Log, HogRider, Prince, DarkPrince, IceGolem and IceSpirit to the existing Knight/Archers/Giant/Musketeer core. Each increment passed focused differentials before the next card family. Python behavior was never changed to fit Rust.

Full games use training/development roles_v2 decks and Hog 2.6, 64 seeds and all combinations of balanced, pressure and defense. Both Python PublicScriptedOpponents choose from Python public observations; the same mask-checked action reaches both engines. Every game runs to the actual reference terminal state, up to 6001 ticks. Timers surround only stepping, with action generation, imports and comparisons excluded. Jobs use nice 10 on the shared Mac mini, with at most two heavy task processes.

Live import restores ordinary and Crown clocks, activation phases, route caches, frozen stopped routes, projectiles and removed-target endpoints, status/charge/shield state, rolling hit ledgers, death areas, player refill queues and pending casts. JSON uses exact float round trips. The 2,048 roots are 32 reproducibly sampled nonterminal ticks per real game; 1041 are sampled after that tick's actions. Each imported clone executes the next 200 recorded-action ticks against a Python clone. Only per-root metadata and failing diagnostics are saved.

Placement validation exhausts every legal mask tile for each pilot card and seat from fresh roots, then tests real replay pocket roots. Both seats have 39 troop pocket tiles tested, using Skeletons and IceGolem, with additional Log pocket coverage. Each accepted placement receives 64 paired continuation ticks. An explicit Hog-versus-Cannon fixture additionally exercises 15 airborne ticks across 500 matching ticks.

## Root causes and regressions

1. Friendly-building route invalidation. The old native cache compared only goal cells. When a friendly Princess died, Python rebuilt or retained the path using occupancy deltas and refreshed the retained heading for a moving troop. Rust kept the old heading, consumed a waypoint one frame early and diverged at Skeletons case 3 tick 697. Match `src/clasher/pathfinding.py:658-743`, especially heading retention at 725 and741. Regression: `test_friendly_crown_removal_refreshes_retained_route_heading`. Original failing phase trace: `engine-rs/evidence-stage2/swarm697.json`. Focused regression and card gate pass.

2. Target-removal finish admission uses the current ordinary hit timeline, not the historical fact that the attacker began an earlier hit. A moving Goblin had timeline 0 after stopping its hit but Rust retained `started=true` and installed 250 ms finish work when the target disappeared. Match `src/clasher/entities.py:1698-1724`. Regression: `test_completed_hit_then_movement_does_not_install_finish_on_removal`; phase trace `engine-rs/evidence-stage2/goblins2049.json`. Focused regression and card gate pass.

3. Ordinary buildings do not get the Crown-only two-tile sight bonus or directional-clipping exemption. Cannon exposed the old blanket Building check when Knights acquired a Cannon at tick 142 instead of retaining their Crown navigation objective. Match `src/clasher/entities.py:1986-2044` and `src/clasher/balance.py:31-32`. Regression: `test_ordinary_building_does_not_receive_crown_sight_bonus`.

Cannon port uses `entities.py:4985-5014` for integer hundredth-HP lifetime decay after movement and before deployment timers; `ordinary_combat_clock.py:9-37` for ordinary versus Crown attack clocks; `placement.py:67-104` and `battle.py:2706-2753` for static anchor/footprint rules. Focused Cannon gate passes.

4. Troop anchor search around live buildings. Successful troop commands can relocate to another tile before the one-unit symmetric snap. Ported ring encounter/tie order, terrain checks, current territory and footprint rejection from `src/clasher/placement.py:16-63`, `battle.py:1195-1217` and `arena.py:124-172`. Cannon case 0 tick 400 now places Knight behind the occupied Cannon footprint. Regression: `test_troop_anchor_relocates_around_live_cannon`. Arbitrary-tile coverage is still a later gate.

5. Retain raw facing vectors and normalize only at the avoidance query. Rust stored an already-normalized256-unit vector and normalized it again, moving the probe by one logic unit at an obstacle boundary. Tesla case 0 tick 843 treated a static contact differently and changed Archer steering. Match `src/clasher/entities.py:302-310,3265-3269,4332-4335`. Regression: `test_avoidance_normalizes_retained_heading_once`; trace `engine-rs/evidence-stage2/tesla843.json`.

Tesla port follows `src/clasher/cards/tesla.py:13-113` and `entities.py:4770-4797` for hiding, target visibility and final deployment-frame combat. Object updates process projectiles before characters, matching `battle.py:935-943`.

6. A swarm child gets its own lane from its pre-snap formation coordinate. The old Rust code assigned the anchor's lane to both Archers. Center Hog fixture case 6 exposed a right-side Archer choosing the left Princess at tick 261. Match `src/clasher/battle.py:1925-1935,2001-2003`, `arena.py:69-83`. Regression: `test_center_swarm_children_keep_their_own_lane`; trace `engine-rs/evidence-stage2/hog261.json`.

7. Backwards-route target retention. A Knight routed away from its target to cross the river; once the target left sight, Python retained the lock while Rust switched to a Crown objective. Cache whether any route node is farther from the target than the route origin, and retain that distant target during active backwards movement with no visible alternative. Match `src/clasher/pathfinding.py:619-630,743` and `entities.py:3788-3808`. Regression: `test_backward_walking_retains_distant_target_without_visible_alternative`; trace `engine-rs/evidence-stage2/hog1616.json`.

8. Activation-shot work subtraction. Crown cooldown carry must retain only attack work remaining after the activation first-hit phase consumes this interval. The new slow/carry implementation spent50 ms twice, leaving0.95s instead of1.0s after the tick 732 activation shot, then firing early at 751. Match `src/clasher/entities.py:4828-4882`. Regression: `test_king_activation_does_not_bank_extra_interval_work`; `probe_king.py` and `icegolem751.json` reduce the cause.

9. Homing payloads retain removed targets' final positions. A target moved after a shot was created and died before the new shot's first flight tick. Python's retained object reference aims at the final location; Rust's saved launch endpoint was stale. Publish removed-body final positions to surviving homing shots before cleanup. Match `src/clasher/entities.py:5246-5254` and `battle.py:965-980`. Regression: `test_new_homing_shot_keeps_removed_targets_final_position`; trace `engine-rs/evidence-stage2/icegolem690.json`.

10. Spirit launch removes character locks at cleanup. The live self-projectile still exists, but Python sends target-removal callbacks to observers after the launch interval. Match `src/clasher/battle.py:2382-2390`. Regression: `test_spirit_launch_releases_character_locks_at_cleanup`; trace `engine-rs/evidence-stage2/icespirit89.json`.

11. Discard distant committed-hit payloads. A Knight retained its hit timeline while a Hog escaped, but the due hit's final distance check must discard damage beyond attack reach plus1500 units. The clock still completes. Match `src/clasher/entities.py:2180-2229,3906-3929`; direct area attacks follow the configured exception. Regression: `test_committed_hit_discards_payload_after_target_escapes`, public-script case 1 tick 1459.

12. Frozen walking still advances retained route nodes. Python's finish-movement work refreshes facing and checks the waypoint projection after external pressure, even with no travel. The skipped node changed Knight displacement by one logic unit on thaw in real game 3 tick 1798. Match `src/clasher/entities.py:388-440` and `pathfinding.py:747-785`. Regression: `test_frozen_walker_consumes_reached_route_node_without_travel`; `match3_1798.json`.

13. The late-overtime hand-refill interval is350 ms after 240s, not500 ms. The stale interval first changed the public hand at real game 3 tick 5363. Match `src/clasher/balance.py:44-48` and `player.py:94-109`. Regression: `test_overtime_hand_refill_uses_350ms` checks the4800 boundary and the next queued refill.

14. Stunned deployment suppresses avoidance scans. The deployment exception applies only while unstunned; otherwise the stored steering value decays. Rust scanned during a Zap and lost the value that Python used for the first Hog movement at match4 tick 112. Match `src/clasher/entities.py:3270-3280`. Regression: `test_stunned_deployment_decays_avoidance_without_scanning`; `match4_112.json`.

15. Deployment completion during stun enters frozen walking. Python sets the retained moving-while-frozen flag when deployment reaches zero, even if the unit has never moved. Its neighbors use that flag in their direction-dot checks. Match `src/clasher/entities.py:3683-3694`. Regression: `test_deployment_expiry_enters_frozen_walking_state`; first internal drift111, public drift128 in game 4.

16. Deployment body pressure clips river edges. Python forces terrain clipping while deployment remains positive; a negative crossing stops on the half-cell edge and a positive crossing one unit before it. Rust let a Skeleton drift20 units into water. Match `src/clasher/native_tilemap.py:232-261` and `entities.py:418-433`. Regression: `test_deployment_body_pressure_clips_adjacent_river_cells`, game 4 tick 131.

17. Spawned formation members clamp to the quarter-tile object boundary. A legal Skeleton anchor at 17.5 produced a child beyond18.0; Python clips it to 17.75 before insertion. Match `src/clasher/battle.py:1947-1975`. Regression: `test_swarm_child_spawns_clamp_to_quarter_tile_boundary`, game 4 action285.

18. Movement bounds differ from spawn bounds. After spawning at 17.75, a troop may move as far as17.999. Rust reused the quarter-tile spawn margin for later motion, changing ordered body pressure. Match `src/clasher/native_tilemap.py:191-197`; preserve the separate250-unit recovery clamp at 200-209. Regression: `test_moving_bodies_can_leave_quarter_tile_spawn_margin`; first observed game 4 tick 286.

19. Relocated ground formations clip to their column's forward deployment edge. Resolve the furthest public territory row that is walkable and unoccupied, apply the owner snap, then clamp each child before object bounds. Match `src/clasher/battle.py:1337-1383,1944-1946`. Regression: `test_relocated_swarm_clips_to_column_forward_deploy_edge`, game 4 action2660 around Tesla.

20. Idle ordinary buildings stop the hit timeline while retaining load. Cannon reacquisition resumed timeline 3950 in Rust and fired, while Python had stopped the old hit and began a new timeline 150. Ordinary buildings also use the clock-phase windup reach condition, unlike Crown cooldown clocks. Match `src/clasher/entities.py:2158-2179,4916-4928`. Regression: `test_idle_cannon_clears_hit_timeline_but_preserves_load`; game 12 tick 4092.

21. Homing impact rechecks hidden-building immunity. A Musketeer projectile retained its Tesla target but arrived while Tesla was underground. Python skips the217 damage at impact; the stored target does not bypass this check. Match `src/clasher/entities.py:5669-5685`. Regression: `test_homing_impact_respects_tesla_hidden_state`; game 62 tick 2291, object phase.

22. Live-import floats must preserve every bit. Default serde_json parsing changed post-spend elixir0.009999999999999787 to 0.009999999999999789. Enable its float_roundtrip feature so JSON import preserves the Python subtraction result exactly. Python semantics: `src/clasher/player.py:79-90`. Regression: `test_live_import_preserves_post_spend_float_bits`. Found at game 45 root 450 after 1444 successful imports.

23. Spirit and ordinary homing endpoints have different removal behavior. A Spirit uses its cached jump destination when its target ID disappears; ordinary homing projectiles retain the removed object's final position. Restrict root 9's removed-position publication to ordinary Projectile objects. Python semantics: `src/clasher/cards/ice_spirit.py:46-59`, compared with `entities.py:5246-5254`. Regression: `test_spirit_keeps_cached_endpoint_when_target_dies_on_launch_frame`. The focused live-state fixture launches a Spirit while a Giant moves and dies to Fireball in the same interval; pre-fix Spirit coordinates differ on the next tick.

24. Preserve the frozen stopped-route cache through live import and native stepping. A Giant can stop on a Crown, freeze, reacquire in its saved stop cell and later resume the saved route after body pressure moves it out of reach. The general importer and native engine omitted this latent state. Match `src/clasher/entities.py:3017-3036,3086-3108,3154-3221`. Regression: `test_frozen_stop_route_variants_and_live_import` runs all ten pinned pilot variants in scalar and fast-path modes and imports the resumable control root. The initial implementation incorrectly treated windup as the stopping condition; the reference condition is active movement or a nonempty route. Original failure is the control at 415 in `frozen_stop_failure.json`.

## Stage 3 plan and estimate

Allow 6-10 engineer-days after this GO: 3-4 for the public v4 observation projection and mask, 1-2 for PublicScriptedOpponent scoring and stable ties, and 2-4 for srp rollout scheduling, reward potential, differential reduction and profiling. Import immutable card/token metadata once, preserve owner rotation, confidence fields, entity ordering and public card history, then run candidate rollouts entirely in Rust.

Require observation bytes and selected actions to match on at least 200 recorded roots, then complete rollout trajectories and planner choices on at least 200 srp calls. Measure whole calls on identical candidates and horizons, targeting at least 20x end-to-end speedup. The earlier 3-5-day estimate did not include the full observation work explicitly.

## Artifacts, preservation and reproduction

Final receipts: `results/stage2_matches_final3.json`, `results/stage2_snapshots_r3.json`, `results/stage2_placements_final2.json`, `results/stage2_primitives.json`, and `results/stage2_manifest.json`. The snapshot driver exit receipt is zero. Final logs are `logs/stage2_final_games3.log`, `logs/stage2_regressions_complete.log` and `logs/stage2_placements_final2.log`.

All loaded Python oracle source hashes match the starting snapshot. A concurrent external edit to `src/clasher/rl/council_pilot.py` was observed and preserved; that module is not loaded by this validation stack. This task wrote no Python engine/RL or protected pilot/C56/OQ data. No unrelated processes were stopped. Cargo intermediates are cleaned after builds, with the tested extension retained; crate and results remain below 1 GiB.

Build with `bash engine-rs/build.sh`. Run the final game sequence with `bash engine-rs/evidence-stage2/final_games.sh` and the live-import sequence with `bash engine-rs/evidence-stage2/run_snapshots.sh`. Use `pilot/detach.sh` as documented in PROGRESS.md for long runs. `stage2_placements.py` accepts `--games-receipt` and `--full-gate` to bind its replay to the accepted build. Source/binary fingerprints prevent accidental reuse after relevant changes.

No known mismatch or blocker remains within the requested Stage 2 scope. C56 and native srp integration are separate later work.
