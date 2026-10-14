# Miner / MightyMiner divergence (read-only diagnosis)

Engine: clasher-bot a82dc380b; `cards/miner.py`, `entities.py`, `balance.py` are byte-identical on 127x03 and 127x05.
Units: positions in native millitiles (ours printed on the same scale); HP is raw (Miner max 1210).
Scripts (scratch, 127x03): `/mpac/sdicks02/jobs/clasher/bot-div/miner/` (cmp.py, summ.py, instr.py, tgt2.py, towers.py, rich.py).
Episodes: v4-phase-a-1975100702 (main), -105, -120, -124 (summary). Full dir names required by `debug_traj.py`.

## 1. What differs

Miner 5000010, ep …702 (truth | ours | RoyaleSim; RoyaleSim matches truth on every tick shown):
- Start: both first seen at t2476. Truth (9197,4276), ours (8901,3642). Both have travelled from King (9000,3000); ours is 1 tick along a straight line.
- Route: truth follows a bent path (9.2,4.3)→(9.2,8.8)→(9.1,10.1)→(6.1,13.4)→(4.3,18.6)→(4.3,23.8)→(5.5,25.5). Ours is one straight line King→destination. Worst gap 2297 units (2.3 tiles) at t2502: truth (4256,19293), ours (6304,20334).
- Speed: both 650/tick (truth 4550 units in 7 ticks; ours the same).
- Arrival: truth t2513 at (5500,25500); ours t2511 (instrumented travel = 1.75 s = 35 ticks).
- Emergence: ours SPAWN t2530 (travel 1.75 s + emergence 1.0 s = Miner deployTime 1000 ms). Truth spawn ≈t2530–2531. **Timing matches.**
- Damage: truth is hit by BOTH princess towers, 5000004 at (3500,25500) and 5000005 at (14500,25500). At t2528 both have targetEntityKey=5000010. Hits (truth): 2532, 2544, 2547, 2559, 2563, 2575, 2580, 2591, 2595, 2607, 2612 (109 each, 11 hits, last hp 11 at t2621).
- Damage (ours): one tower only. Hits at 2549, 2566, 2583, 2598, 2614, 2632 (every ~16 ticks = princess 0.8 s cadence). Ours alive to t2676.
- First hit: truth +2 ticks after spawn; ours +19 ticks.

Across 20 Miner units in ..702/705/720/724 (summ.py):
- Spawn/travel start tick identical in every unit.
- Ours first hit is later than truth's by ~10–25 ticks in most units (e.g. 5000010: 2549 vs 2532; 5000030: 2932 vs 2917; 5000065: 3711 vs 3692).
- Ours outlives truth's death tick by 0 to +72 ticks in every unit (5000010 +55; 5000088 +72).
- Truth hit ticks interleave two streams (~6–8 tick gaps); ours is one stream.
- MightyMiner 5000055 (..724): first hits 4111 truth vs 4108 ours, which fits; its aggregate gap (53.9 vs 73.2) is NOT diagnosed here.

HP level / damage per hit: NOT a cause. Max HP 1210 in both; 109 per hit in both; no crown-tower damage involved (princess hits only). The HP gap comes from hit count and timing only.

## 2. Root causes (ours vs native)

A. Path (confident). `src/clasher/cards/miner.py:39-61` (`on_attach`) sizes travel as straight-line King→destination via `spawn_path_travel_tick_count` (`kinematics.py:78`). `miner.py:98-115` (`on_deploy_tick`) then steps straight at 650/tick. Native walks a pathfound route. Durations coincide only by luck (ours arrives 2 ticks early).

B. Second tower never engages in ours (symptom confirmed; mechanism UNKNOWN). Native princess 5000005 targets the Miner at center distance 9.00 (= sight/range 7.5 + tower radius 1.0 + Miner radius 0.5; `ADD_CHARACTER_RANGE_TO_RADIUS`, `balance.py:30`). Our reach formula also gives 9.0 (`entities.py:1877-1891`); for the left tower our `can_attack_target` returns ok=True at distance 1.999 (reach 9.0). But for the right tower (14.5,25.5), `can_attack_target` is never called with the Miner in t2505–2560 (tgt2.py logged only the blue princess at (14.5,6.5), dist 19, always False). So the Miner is dropped before the attack check, probably in candidate gathering (`entities.py` ~2430–2500, fast-path `iter_entities_in_radius` radius, or `sight_reach` at `entities.py:2005`). Exact line: unknown.

C. First-hit lag of ~19 ticks (mechanism UNKNOWN). Left tower's check at t2531 returns ok=True, yet its first damage is t2549. Native first hits t2532. Candidates: tower attack timeline / windup, or the tower was busy with another target. Not probed.

D. Not causes: spawn time (matches), speed (matches), arrival (±2 ticks), HP and damage per hit, emergence delay (deployTime 1000).

## 3. Fix sketch and harness verification

1. Path: replace the straight segment with the native spawn route for underground travel (same waypoint source the native uses; `arena` native path helpers exist, e.g. `native_path_id_at`). Travel ticks = route length / 650, and `on_deploy_tick` follows waypoints. Owner: miner.py + `c56_champions.py:63-72` (MightyMiner uses the same straight-line code).
2. Second tower: log `get_nearest_target` candidates for tower 5000005 at t2531 (entities.py ~2430–2500) and check whether the Miner is filtered before `can_attack_target`.
3. First-hit lag: trace tower 5000004's attack timeline for t2531–2549.

Verification (127x03, nice):
- `bot/fidelity/debug_traj.py v4-phase-a-1975100702 Miner 6` — target: positions within 0.3 tile of truth (currently up to 2.3), first hit within ±2 ticks, two interleaved hit streams.
- `summ.py` on the four episodes — target: hit ticks and death tick within ±5 of truth.
- Re-score the fidelity table: Miner was 47.6% within 1/4 tile, 33.7 HP-exact; target ≥85%.
- Also `bot/fidelity/test_fidelity.py`.
