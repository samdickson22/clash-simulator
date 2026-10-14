# Spawner hut fidelity: GoblinHut and FirespiritHut (research, read-only)
Host 127x05. Traces ran on 127x03 with the existing `debug_traj.py` / `debug_one.py`; outputs in
`/mpac/sdicks02/jobs/clasher/bot-div/huts/` on 03. Tick = 50 ms (38 ticks = 1900 ms).
Episodes: 1975101230 and 1975100700 (GoblinHut), 1975101141 (FirespiritHut). "Unknown" = not verified.
## Native data (gamedata.json, not a trace)
- GoblinHut 27000001 -> `GoblinHut_Rework`: hp 461, lifeTime 30000, deployTime 1000, spawnInterval 0,
  spawnNumber 0, spawnPauseTime 0. Death spawns 1 SpearGoblin (hp 52).
- FirespiritHut 27000010 -> `Furnace_rework`: **walking** (speed 60, hp 284, deploy 1000), no lifeTime.
  `onStartingActionData` interval **7000**, spawns FireSpirits (hp 90, kamikaze).
- The GoblinHut 2200 ms cadence, 6000 wake range, 1000 ms wait and 500 ms deploy are not in gamedata. They come from
  `reports/strategy_council_20260928/c56/engine/audit/B4_buildings_champions.md:6`, which cites
  `characters/goblin_hut_rework.toml`. That file is not in this checkout. Unverified.
## 1. What differs
### GoblinHut (ep 1975101230 unless noted)
- Cadence: truth hut 5000014 emits SpearGoblins at 4949, 4994, 5037 (gaps 45, 43 ticks = 2200 ms). Ours is also 2200,
  so the period matches once awake.
- First spawn after the hut appears (4886): truth 4949 = +63 ticks (~3150 ms). Ours 4981 = +95 ticks (~4750 ms).
- Wake: ours sleeps until an enemy kind 0/1 is within 6.0 + target radius, and resets the clock on each sleep.
  Truth wake timing unknown; enemy distance at truth spawn ticks not logged.
- Offsets: truth first positions for hut 5000014 are 1.30, 1.35, 1.50 tiles from the hut, all toward -y (enemy side).
  Ours (pair of 5000017) is 1.52 tiles, same side.
- Count, ep 1975100700, tick <= 3900: **truth 15, ours 12** (`debug_one.py`, 3 side-1 huts).
- Hut HP: ours equals truth exactly on hut 5000014 from 4886 to 5022. Lifetime decay (entities.py:4980) gives
  0.76 HP/tick = 30 s, consistent with native. The 37% HP-exact aggregate is probably not decay.
- Death spawn: detector adds one SpearGoblin (mechanic_detector.py:69-93), matching deathSpawnCount 1. Truth: unknown.
### FirespiritHut (ep 1975101141)
- Hut 5000011 first at tick 426 at (2499,29499); it walks (truth and rsim both move it).
- First FireSpirit: truth 464 = +38 ticks (~1900 ms). **Ours 505 = +79 ticks (~3950 ms), ~2.05 s late.**
- Period: truth 464, 565, 664, 765, 864 = 100 ticks = **5000 ms**. Ours 505, 605, 706, 807, 906, same period.
  Gamedata's 7000 is contradicted by truth; the 5000 in balance.py:879 stays.
- Spawn position: truth first spirit is 1.5 tiles straight ahead (2499,27999). Ours uses the zero-radius search
  (battle.py:2049) because the transform sets no spawnRadius (balance.py:865-883). Our position is not printed: unknown.
- Walking: ours moves later and along a different path. Distance to truth for hut 5000011: 117 at 494, 1356 at 528,
  1264 at 557, 1190 at 590 (rsim: 0 throughout). Cause unknown (deploy start or pathing).
- HP: exact to tick 827; at 859 ours is +109 HP vs truth (rsim 0).
- Count, ep 1975101141, tick <= 3900: **truth 9, ours 8** (two huts).
### Confound for both cards: our battle ends early
- Our game_over vs fixture end: 1975100700 3936 vs 5980; 1975101230 5534 vs 5909; 1975101141 4735 vs 5353.
- `bot/fidelity/run.py:84-91` freezes our state after game_over. Truth units alive then count as mismatches: frozen
  share 34%, 6%, 12%. This can explain much of the low hut alive/HP numbers. Why our battle ends early is unknown; it is
  a separate bug.
## 2. Root causes (ours vs native)
| # | Item | Ours (file:line) | Evidence | Native / truth |
|---|---|---|---|---|
| F1 | Furnace first spawn ~2.05 s late | balance.py:881 `spawnStartTime=3050`. Mechanics tick only after deploy (entities.py:4761-4792), so first = 1000 + 3050 | 505 vs 464 | ~1950 ms from appearance (truth) |
| F2 | Furnace period | balance.py:879 `spawnPauseTime=5000` | matches truth | gamedata 7000 (contradicted) |
| F3 | Furnace spawn offset | no spawnRadius -> zero-radius search (battle.py:2049) | truth 1.5 tiles ahead | unknown |
| F4 | Furnace walking | tidType character, speed 60 inherited (balance.py:872) | moves in both | yes. Audit B4 row 5 ("static building") is stale |
| G1 | GoblinHut wake | goblin_hut.py:27-36 radius 6.0 + target collision; reset on sleep | first spawn +4750 ms vs truth +3150 | audit "within 6000" (unverified) |
| G2 | GoblinHut deploy | goblin_hut.py:22 `deployTime=500` | not checked | audit 500 (unverified) |
| G3 | GoblinHut cadence/radius | goblin_hut.py:11-16 2200 ms, first 1000, radius 1.2, angle 20 | period matches | audit (unverified) |
| H1 | Harness freeze | run.py:84-91 | 34% of one fixture | n/a |
## 3. Fix sketch and verification
- F1: set spawnStartTime so the first spirit lands at hut + 1950 ms. If the clock starts at deploy end, use 950.
  Verify: `debug_traj.py v4-phase-a-1975101141 FirespiritHut 8` gives sim_first 464 (+-2 ticks), then 565, 664, 765, 864.
- F3: try spawnRadius ~1500 with angle 0; keep only if the first-spawn position matches the truth offset within 0.2 tile.
- G1: log enemy distance to hut 5000014 at truth ticks 4949, 4994, 5037 first. Then tune the wake gate. Keep the 2200
  cadence, which matches truth.
- H1: rerun the FIDELITY per-card table with post-game-over ticks excluded or reported separately, before judging hut HP.
- Counts: after fixes, `debug_one.py <ep> 3900` should give GoblinHut 15 vs 15 (1975100700) and FirespiritHut 9 vs 9 (1975101141).
- Open: native GoblinHut wake distance and deploy time (toml missing); native Furnace spawn offset; why gamedata says 7000 while truth says 5000.
