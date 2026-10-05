# External review: Hasty-CR compared with clasher

Date: 2026-09-28. Reviewer: external-review subagent, working read-only on clasher. The only clasher file written is this report.

- Upstream: https://github.com/hastylmao/Hasty-CR, cloned to `/Users/sam/Desktop/code/external/Hasty-CR` at HEAD `913608b4dc7772008402493b27dc29020fe51718` (2026-08-30). The history has 23 commits starting from a squashed "Initial release" dated 2026-08-27, so earlier claims can only be checked against their docs.
- Execution environment: a separate venv, `/Users/sam/Desktop/code/external/.venv-hasty` (Python 3.12.13; numpy, pytest, pillow, opencv-headless; no torch). Nothing was installed into clasher's `.venv`.
- **Their engine will not run from a clean clone.** It reads APK-extracted client data from `tmp/gamedata/csv_logic`, which is gitignored (`sim/gamedata.py:2173, 2625-2645`). To run it I copied our decoded Null 15.535.x logic (`~/.cache/clasher-native-reference/decoded-logic-1e505767`, 4.8 MB) into their ignored `tmp/` directory. Their loader read 202 cards from it without modification.
  - Consequence: every Hasty-CR number I measured uses *our* card data, plus the tower tables they ship in `data/royaleapi`. None of it uses their live-client snapshot.
- Probe scripts are in `/tmp/hasty_bench/` and are not part of either repository.

Unless prefixed with `clasher:`, paths below are relative to the Hasty-CR root. Clasher paths are relative to `/Users/sam/Desktop/code/clasher`.

---

## 0. Executive summary

- **License:** MIT (`LICENSE`), which permits copying with the notice kept. It covers their original code only, and several bundled or depended-on assets carry other terms (§1).
- **Simulator:** both engines use a 50 ms tick and 1000 units per tile.
  - Theirs is pure-integer Python. On an identical random-play Hog 2.6 workload it is **about 5.4x faster** than our scalar engine: 9,140 vs 1,678 ticks/s on this M4 Pro, single process.
  - Ours is anchored to the native 15.535.86 reference. Theirs is anchored to decoded client tables plus wiki, VOD and live observation.
  - For the 16 pilot cards I found **five places where they deviate from native data or rules and we do not**:
    1. tower anchors one tile forward and the King off-centre;
    2. a different tower level curve;
    3. shield overflow spilling into HP;
    4. the Log ignoring `PushbackAll`;
    5. no Tesla hide/reveal.
  - They also omit gait stop/wait timing.
  - **Nothing I found in their engine points to a bug in ours for the pilot cards.** Two items deserve cheap native confirmation (§2.5).
- **Pathfinding bug:** their "lane-commitment" bug meant a unit whose lane's Princess Tower had fallen walked diagonally to the *other* Princess Tower instead of the King.
  - **Our simulator does not have it.** We implement the native x-based fallback-crown selection with lane and age guards (`clasher: src/clasher/entities.py:2571-2629`), assign lane IDs at deploy, and pin the behaviour with native 15.535.86 fixtures (`clasher: tests/test_native_crown_fallback.py`, 10/10 passing).
  - A direct probe of the same scenario sends Hog, Knight, Giant and Musketeer to the King through their own bridge.
  - We also do not have their related "cross-map building pull" bug.
- **RL:**
  - Their stack: a 20.2M-parameter feed-forward CNN with a flat 2,321-way masked action, trained with BC from their rule bot, then PPO with a value warm-up and target-KL, against a scripted-plus-snapshot league, on one fixed Hog 2.6 deck at level 11 from one seat.
  - Our planned stack is stronger on memory, critic isolation, reward invariance, scope and evaluation.
  - What we should borrow: **critic warm-up after the scripted warm start**, **turning our already-implemented target-KL guard back on**, **behaviour-based training alarms**, and their **opponent-mix lessons**.
- **Sim-to-real:**
  - Their detector is Ultralytics YOLOv8s trained on KataCR's dataset. The 0.959 mAP50 is measured on that dataset's own validation split. No weights are shipped.
  - Capture is `adb screencap`: about 406 ms at full resolution, 117 ms at 540x960.
  - Taps are one `adb shell input tap` subprocess each, with no acceptance check.
  - Most useful to us: their measured latency budget, the `screenrecord` h264 + PyAV capture path, side as an explicit measurement, and hand-slot abstention.
  - Ultralytics is AGPL-3.0, which affects them and our existing `tv-replay` extra.
- **Evaluation:** 93.3% / 86.7% / +0.78 are 56/60 and 52/60 greedy, bottom-seat games, fixed deck, seed 8000. The "rule engine" is the BC teacher and half the training diet. The meta decks are the training pool. Seed 8000 is also the supervisor's rollback gate.
  - The rule-engine gain over the clone is real *inside their simulator* (Wilson intervals don't overlap).
  - The meta-deck gain is not significant.
  - No live RL result exists.

---

## 1. License

**The license is MIT.** `LICENSE:1-21` reads "Copyright (c) 2026 HastyCR contributors", and `pyproject.toml:10` has `license = { file = "LICENSE" }`. MIT permits use, copying, modification, merging, publishing, distribution, sublicensing and sale, provided the copyright and permission notice are kept in all copies or substantial portions. There is no warranty, and no patent grant beyond what is implied.

**What MIT does not cover.** Treat each of these separately:

| Item | Evidence | Status |
|---|---|---|
| Ultralytics YOLO | Runtime dependency `ultralytics>=8.3` (`pyproject.toml:29`), imported at `scripts/train_detector.py:43` and `scripts/brain/vision.py:168` | AGPL-3.0. Distributing or network-serving the vision pipeline brings AGPL obligations, and Ultralytics claims trained weights too unless you hold an enterprise licence. **clasher already pins `ultralytics==8.1.24` in its `tv-replay` extra** (`clasher: pyproject.toml:29`), so this is not new exposure, but do not import their detector code into the core package. |
| Detector training data | `vendor/CR-Detection-Dataset/images/part2` (`scripts/prepare_yolo_dataset.py:37`), from wty-yy (KataCR) | Not listed in `vendor/manifest.json` or `research/REFERENCE_LICENSES.md`. The dataset licence and the Supercell art in it are undocumented. |
| Vendored and upstream bots | `vendor/manifest.json`: ClashAI UNLICENSED; py-clash-bot NC-CL-1.0 AND CC-BY-NC-SA-4.0; BuildABot, KataCR and CRBot-public MIT | Their live stack uses BuildABot for card, elixir and tower reads (`scripts/brain/vision.py:24-25`). They say deck archetypes were "adapted" from ClashAI without copying code (README footer). Anything touching ClashAI or py-clash-bot is not safely MIT. |
| Game data | `data/royaleapi/*.json` (published stat tables), extracted client CSV/TOML (not shipped) | Supercell and RoyaleAPI terms apply, not MIT. |
| VOD tracks and media | `data/vod/tracks/*` from YouTube matches; `demo.mp4`, `docs/assets/*` | Derived from third-party video and Supercell visuals. |

**Verdict: MIT, so code copying is legally permitted with notice retention for their original code** (engine, trainer, supervisor, capture helpers). For clasher, I still recommend **ideas-first adoption**. Their engine semantics diverge from our native reference (§2), and copying their code into the frozen-runtime path would require re-validating it against native evidence. If code is copied, for example `scripts/studio/devicecap.py`, which imports only `subprocess`, `threading`, `numpy` and PyAV (`scripts/studio/devicecap.py:26-33, 59, 119`), keep the MIT notice in the file header and record provenance.

**Side note for Sam.** They reviewed your public `samdickson22/clash-simulator`, noting that "README claims MIT but the referenced LICENSE file is absent; treat as study-only", and say they copied nothing (`research/samdickson_analysis.md:1-3, 21-23`). If you want that repo to be reusable, add the LICENSE file.

---

## 2. Simulator

### 2.1 Representation and tick

| | Hasty-CR | clasher |
|---|---|---|
| Tick | 50 ms (`sim/arena.py:58`). They argue every client timing field is a multiple of 50 (README "Inside a tick") | 50 ms native logic tick (`clasher: src/clasher/kinematics.py:8-9`; `battle.py:123`) |
| Position units | Integer millitiles throughout, frozen `Point(int,int)`, `math.isqrt` distances (`sim/arena.py:25, 61-94`) | Float tiles in `Position` (`clasher: src/clasher/arena.py:10-15`), converted to integer logic units at native-sensitive points (`kinematics.py:10-11, 54-61`; `logic_math.py` fixed-point sin/atan tables; 250-unit native movement substeps, `kinematics.py:11, 100`) |
| Movement speed | Raw `Speed` x 1000/60 mt/s, as integers (`sim/entities.py:33-37`). Medium = 1.0 tile/s, Hog = 2.0 | Serialized per-tick speed plus native gait normalisation. Units with `StopMovementAfterMS`/`WaitMS` get active-stride speeds (Giant 52, Ice Golem 52, Golem 54) (`clasher: src/clasher/gamedata_normalization.py:16-31`) |
| Pathing | BFS flow field on an 8-connected 18x32 tile grid, cached per goal tile (`sim/pathfind.py:1-60`) | Native grid route and route-goal-cell reproduction with building cost cells (`clasher: src/clasher/pathfinding.py:93, 177, 305, 515`), plus native avoidance grid |
| Tick phases | Seven fixed phases, each emitting normalised events (README) | Native combat, movement and hitpoint component order (`clasher: battle.py:755-1000`) |
| Reference | Decoded client tables, wiki dimensions, one live match, a 10-match VOD sample, and cross-checks against Jason's simulator (`docs/VOD_CALIBRATION.md`) | Null's 15.535.86 native reference emulator with fixtures, as the approved strategy requires |

### 2.2 Card-data source

- **Hasty-CR:**
  - Pulls the APK over adb and LZMA-decodes the shipped CSV/TOML (`scripts/extract_game_data.py:1-60`, with a hard-coded MuMu Windows adb path). The output directory is ignored.
  - Overlays RoyaleAPI "combat rules" and published stat tables (`sim/gamedata.py:10-23, 596-640`).
  - Takes tower HP and damage per level from `data/royaleapi/cards_stats_building.json` and `cards_stats_projectile.json` (`sim/towers.py:1-25`).
- **clasher:** `gamedata.json` plus a native-decoded logic snapshot. The effective game-data SHA is pinned in the runtime snapshot (handoff §"Completed evidence").
- **The tower level curve differs.** Their stack at their "level 11": Princess 3,584 HP / 128 damage and King 6,144 / 128. clasher at level 11, per our native anchors: Princess 3,052 / 109 and King 4,824.
  - Their own docstring lists the Princess curve "... 2968, 3262, 3584 ..." (`sim/towers.py:6-9`). None of those equals the native level-11 value.
  - Per-card stats agree much more closely: Knight 1,766 in both when fed our data. Their live-client figure is 1,789 (`docs/SIM_MECHANICS.md`, "On outside sources").
  - So the tower-to-troop ratio at "level 11" differs by roughly two tower levels. That changes Hog hit counts (§2.4, probe 1).

### 2.3 Geometry: a concrete divergence from native

| Object | Hasty-CR (y-down frame, `sim/arena.py:180-183`) | Same point in our y-up frame | clasher / native 15.535.86 |
|---|---|---|---|
| Own Princess | tile(3,24), tile(14,24) = (3.5, 24.5), (14.5, 24.5) | y 7.5 | (3.5, 6.5), (14.5, 6.5) |
| Enemy Princess | (3.5, 7.5), (14.5, 7.5) | y 24.5 | (3.5, 25.5), (14.5, 25.5) |
| King | tile(9,28) = (9.5, 28.5); enemy (9.5, 3.5) | (9.5, 3.5) | (9.0, 3.0), (9.0, 29.0) |
| River | Tile rows 15-16 impassable except on bridges (`sim/pathfind.py` `walkable`) | same | Rows 15-16 (`clasher: arena.py:110-127`; walkability checked at y 15.1-16.9) |

- Their Princess Towers sit **one tile closer to the river** on both sides. Princess-to-princess distance is 17 tiles against native 19.
- Their King is offset 0.5 tile towards the right lane and 0.5 tile forward.
- They state that arena geometry "lives in the engine binary" and was taken from published wiki dimensions instead (`tests/test_arena_geometry.py:1-19`). Our tower anchors come from native frames; see the tower list in `clasher: tests/fixtures/native_crown_fallback_15_535_86.json`.
- This affects crossing times, which tiles tower range covers near the bridge, King activation geometry, and the pocket after a tower falls.

### 2.4 Mechanics probes on the pilot cards, run in both engines

Scripts: `/tmp/hasty_bench/mech_ours.py`, `mech_theirs.py`, `dp_theirs.py`. The frames are mirrored so placements are matched *relative to the river*. Because their towers sit a tile forward, absolute distances to towers differ.

| # | Scenario | clasher | Hasty-CR | Reading |
|---|---|---|---|---|
| 1 | Lone Hog on an undefended Princess Tower (King asleep) | 7 hits, 2,219 damage | 6 hits, 1,902 damage (their `sim.check` prints the same) | Driven by the tower curve in §2.2. Their only live measurement also saw 7 hits unblocked (commit 5568739). |
| 2 | Lone Ice Golem at a Princess Tower | 168 damage | 168 damage (`sim.check`) | Agree |
| 3 | Musketeer walks into a Cannon | Musketeer untouched, Cannon dead in 4.9 s | Untouched, 5.1 s | Agree |
| 4 | Prince vs Musketeer from 6 tiles | Prince wins, 4.4 s | Prince wins, 3.2 s (`sim.check`, different setup) | Qualitatively agree |
| 5 | Ice Spirit on Knight | 1.10 s freeze | 1.1 s freeze (`sim.check`) | Agree |
| 6 | Log over Giant | 268 damage; **Giant knocked back about 0.5 tile** | 275 damage; **Giant not moved at all** (`sim.check`: "a Giant is not pushed at all") | **They diverge from native data.** `LogProjectileRolling` has `Pushback = 700` and `PushbackAll = true` (`decoded-logic-1e505767/characters/logprojectile.toml:36-37`). We honour it (`clasher: src/clasher/balance.py:760-764`). Their pushback code gates only on `not target.ignore_pushback` (`sim/engine.py:930, 973, 1346, 1394, 1863`) and never reads `PushbackAll` (zero grep hits in `sim/`). |
| 6b | Log over Knight | About 0.3 tile net displacement against forward motion, applied over several ticks | 0.75 tile, instantaneous | Both push; profiles differ |
| 7 | Princess Tower cadence | 109 damage every 15-16 ticks (0.8 s), first shot after acquisition | 128 every 0.8 s after a 1 s windup (`sim.check`) | Damage follows §2.2; cadence agrees |
| 8 | Hog, then Hog with 3 Skeletons dropped at the bridge | 7 hits unblocked; **2 hits blocked**, first hit delayed 0.20 s | 6 hits; 2 hits blocked, first hit delayed 0.85 s | Their one real match: **7 unblocked, 2 blocked** (commit 5568739). Their engine produced 4 blocked at that time. Our count matches that single real observation, but placements weren't matched, n = 1, and levels are unknown. |
| 9 | Dark Prince vs Knight, 1v1 | **Dark Prince wins with 190 HP**: the shield absorbs two whole Knight hits | **Dark Prince dies** at 11.1 s: the 202-damage breaking hit spills 163 into HP | **Rule difference.** Theirs: `soaked = min(shield, amount); amount -= soaked` (`sim/entities.py:675-684`). Ours: "A shield consumes the entire hit that breaks it" (`clasher: src/clasher/mechanics/shared/shield.py:36-43`), mirrored in the torch backend (`torch_sim/simple_modifiers.py:261`; `tests/test_torch_simple_tower_combat.py:233`). Ours matches the documented CR rule. |
| 10 | Prince vs Knight / Hog vs Knight | Prince wins at 8.0 s; Knight kills Hog | Prince wins at 8.1 s; Knight kills Hog | Agree. Their README's "charging units still deadlock" refers to Battle Ram and similar blocked by a Knight (`docs/RL_SPRINT4_DECISIONS.md:43-71`); I did not reproduce a Prince deadlock in either engine |

**Mechanics present in native data and ours but missing from theirs, for pilot cards:**

- **Tesla hide/reveal.** Native `HideTimeMs = 800` and `UpTimeMs = 800` (`characters/tesla.toml:16, 41`). We implement `HideWhenIdle` (`clasher: src/clasher/cards/tesla.py:7-23`). Their only hide timer comes from Goblin Drill relocation data (`sim/gamedata.py:1488`, `sim/engine.py:3109`), so their Tesla is always exposed.
- **Gait stop/wait for Giant and Ice Golem.** Native `StopMovementAfterMS = 640` and `WaitMS = 100` for Giant (`characters/giant.toml:39, 43`). We model it (`gamedata_normalization.py:16-31`); they have zero references. Average speed matches, but stride phase and pause timing do not.
- **Native fallback-crown selection** (§3).

**Mechanics they model that we lack for pilot cards:** none I could identify. Their extra breadth (evolutions, heroes, champions, tower troops such as Dagger Duchess) is outside the pilot scope. The tower-troop variants in `sim/towers.py` could matter if ladder opponents in a future live phase use them. That belongs to the later broad-scope stage, not the pilot.

### 2.5 Does anything suggest a bug in *our* pilot-card mechanics?

**No.** Every divergence I found goes against native data or the documented rule, not against us. Three items are still worth a cheap **native diagnostic** as development evidence. These are not acceptance evidence and not fitting, and none blocks Tier A:

1. **Shield-breaking-hit absorption** (Dark Prince vs Knight). I found no 15.535.86 fixture that isolates it. The rule is implemented consistently across our backends, but it currently rests on game knowledge rather than a native frame.
2. **Hog + 3 Skeletons body-block delay.** Our 0.20 s first-hit delay comes from native avoidance. Their single live clip is the only external real-game number for the most important Hog 2.6 interaction.
3. **Log vs `ignorePushback` units.** Worth one native frame check, since we rely on an override that re-adds `pushbackAll` omitted from the compact payload (`clasher: balance.py:760-764`).

### 2.6 Speed

Workload: identical in both engines. Hog 2.6 mirror, both seats making a random attempt every 500 ms with probability 0.45 and a fixed placement list, until game end or tick 6001. Ten seeds, single process, M4 Pro, Python 3.12.13. Scripts `/tmp/hasty_bench/ours.py` and `theirs.py`.

| Engine | Ticks | Seconds | Ticks/s | Successful deploys |
|---|---|---|---|---|
| Hasty-CR `Match` | 41,663 | 4.6 | **9,140** | 1,038 / 3,778 |
| clasher `BattleState` (default) | 41,550 | 24.8 | **1,678** | 993 / 3,747 |
| clasher `BattleState(fast_path=True)` | 41,550 | 34.5 | 1,203 | 993 / 3,747 |

- Their documented rates: about 4,700-5,100 ticks/s single-process with their rule policy (`docs/OVERNIGHT_FIDELITY_SPRINT.md:23, 85`); 8.9 matches/s on 8 workers (`docs/RUN_JOURNAL.md:509-510`); PPO 614-2,048 env-steps/s at 500 ms per decision on an RTX 4070 Ti SUPER with 8 cores (`docs/RL_SPRINT4_STATE.md:44-64`).
- Our council path is 45.77 learner decisions/s at 250 ms each (`clasher: reports/strategy_council_20260928/m0/benchmark/README.md`). That is about 11 game-seconds per second per learner stream, against their roughly 300-1,000.
- **But the engine is not our main bottleneck.** At 45.77 decisions/s x 5 ticks = 229 engine ticks/s, and our raw engine rate is 1,678 ticks/s, so simulation is only about 14% of wall time in the council benchmark. Model forward (p95 32.9 ms), full-prefix recurrent reconstruction and observation building dominate.
  - A 5x faster engine would buy at most about 12% in the current council path.
  - It would buy much more for readiness branch studies (512 branches, scalar-root studies) and for future multi-worker actors.
- **Where our engine spends its time** (cProfile, one seed, 11.1 s, `/tmp/hasty_bench/ours.prof`):
  - 18.3M `getattr` calls (1.07 s self time);
  - 1.9M `tiles_to_logic_units` float-to-int conversions;
  - `get_nearest_target` 3.27 s cumulative, of which `_is_valid_target` is 1.82 s;
  - `is_expected_to_die_from_projectiles` 0.99 s;
  - `unit_mass` 0.46 s;
  - troop collision accumulation 1.28 s.
- **Techniques worth adopting later:**
  1. Store positions and radii as native integers on the entity, so the float/int conversions disappear. Their `sim/arena.py` notes (lines 1-12, 75-94) explain the same rationale and the win from `math.isqrt`.
  2. Resolve per-entity traits once at spawn into slots instead of repeated `getattr` probing.
  3. Cache target candidate lists per tick.
  4. Share cached flow fields per goal tile. We already cache routes, but route-goal computation still shows in the profile.
  5. Investigate why `fast_path=True` is **slower** than default on this workload. I report it without diagnosing it.
- None of these should touch the frozen runtime before Tier A. All would need native-parity re-validation.

---

## 3. The pathfinding bug found in a human match

**What it was** (commit `29f6afb`, 2026-08-28; test docstring `tests/test_lane_commitment.py:1-26`; `sim/arena.py:130-160`; `sim/engine.py:2440-2491, 3728-3780`):

- Ground units picked the globally nearest enemy crown tower by straight-line distance.
- With the near Princess Tower down, a Hog at the back of the right lane measured the far Princess at about 20.7 tiles and the King at about 22.1, so it walked diagonally across the arena to the far lane. 1,614 tests missed it because every pathing test started from a full board. It was "reported from live play" by a human; no replay is in the repository.
- Their fix filters crown towers by the unit's *current* half of the board (`lane_of(p) = left if p.x < 9.0`), treats the King as belonging to both lanes (1.5-tile centre band), and demotes other-lane towers to an `offlane` last resort.
- Re-measured win/loss counts did not change (README Results note). Tower and play statistics shifted slightly between `reports/fixedsim_audit_cont.json` and `reports/eval_fixed_cont_6106112.json`.
- A sibling bug, found the same way: a building-targeter (Hog) or any troop could be pulled by a building across the map. A Hog at (14,26) walked 8.5 tiles towards a Cannon at (3,13), against a 9.5 sight range. They fixed it by gating the pull on sight range (`sim/engine.py:2441-2463`).

**Could our simulator have it? No.** Evidence:

- **Native selection logic.** `_preferred_fallback_crown_targets` (`clasher: src/clasher/entities.py:2571-2629`, active because `LOGIC_XPOS_BASED_TOWER_TARGETING = True` at `balance.py:127`) reproduces the native routine:
  - Start with the nearest King.
  - Choose one Princess by minimum |dx|. Skip other-lane Princesses if the unit has been deployed for under 500 ms **or only one Princess remains**.
  - Take the Princess only if its octagonal distance, `max(dx,dy) + (53*min(dx,dy) >> 7)`, is strictly smaller than the King's exact distance. Otherwise take the King.
  - With one Princess left in the other lane, this always returns the King.
- **Lane IDs** are assigned once at deploy from the native path tilemap (`clasher: battle.py:1987, 2263`), not recomputed from the unit's current x as Hasty does.
- **Native fixture.** `clasher: tests/fixtures/native_crown_fallback_15_535_86.json` contains four native placements (x = 3.5, 8.5, 9.5, 14.5), with the left enemy Princess destroyed, and records which tower each unit targets. The x = 3.5 and 8.5 placements go to the King at (9000, 3000); the other two go to the surviving right Princess. `tests/test_native_crown_fallback.py` passes 10/10 in both the scalar and fast paths.
  - Caveat: the fixture is labelled `role: development`, with 1 physical root and 0 independent acceptance roots.
- **Direct probe of their scenario** (`/tmp/hasty_bench/lane_probe.py`): enemy right Princess destroyed; Hog at (14.5, 2.5) and (15.5, 9.5), Knight at (14.5, 2.5), Giant at (12.5, 9.5), Musketeer at (13.5, 5.5). Every unit targeted the King at (9.0, 29.0) and crossed by the right bridge. The Hog reached the King area without crossing lanes.
- **Building pull is sight-gated** in our `get_nearest_target`. Buildings enter candidates only if `is_within_sight` (`entities.py:2491-2500`); crown towers are the only out-of-sight fallback (`entities.py:2506-2569`). So their cross-map pull bug is also absent.
- **Their fix is only an approximation of native behaviour:**
  - it uses current position rather than deploy lane;
  - it has no 500 ms age guard;
  - it has no Princess-versus-King distance comparison when both Princesses stand.
  - A centre-deployed unit, or one that drifts across x = 9 while fighting, can still diverge from native there.

**The lesson that does transfer:** their test suite was blind because every pathing test started from a full board. Our Tier A families and Tier B targeted probes should deliberately include **post-tower-loss boards**, pocket placements and centre placements. The fixture above covers one board with four placements.

---

## 4. RL comparison

### 4.1 Hasty-CR stack

- **Network** (`sim/train_ppo.py:101-123`): Conv 8→32→64→64 over 32x18, flattened to 36,864, concatenated with Linear(47→128), then Linear(36,992→512), then a policy head of 2,321 and a value head of 1.
  - **20,195,506 parameters**, 94% of them in the flatten→512 layer.
  - Shared trunk, no recurrence, no frame stack. Their own audit says the rule bot's real advantage over the policy is memory (`reports/rl_sprint4/BRAIN_INFORMATION_ADVANTAGE.md:39-42`; `MEMORY_HYPOTHESIS.md:4-7`).
- **Observation** (`sim/env.py:76-155`): eight planes (ally/enemy counts, HP/1000, air, buildings) and 47 scalars. The scalars are own elixir, time capped at 180 s, elixir multiplier, four Princess fractions (King excluded), own hand as a one-hot over the fixed 8-card deck, and the next card.
  - Opponent hand and elixir are deliberately excluded (`env.py:30-33`). There is no privileged critic.
  - Exact per-unit HP is observed in simulation, but live play substitutes full card HP (`scripts/brain/rl_policy.py:23-27`), so train and deploy differ.
  - **Bug:** for the top seat, board planes are mirrored but the left/right tower scalars are not swapped (`env.py:142-147` vs `adapter.py:72-75`). Learned league opponents see their lanes crossed.
- **Action space:** 1 hold + 4x576 tiles + 16 ability slots = 2,321, masked to −inf (`env.py:59-64`; `train_ppo.py:131-140`). Greedy argmax at evaluation and live (`train_ppo.py:165`; `rl_policy.py:207`). Decisions every 500 ms (`env.py:66`).
- **BC** (`sim/clone.py`): the teacher is the hand-written `BrainPolicy`. Default 400 episodes (README: 4,000), 8 epochs, AdamW lr 1e-3, holds subsampled to 25% (`clone.py:101, 130-134`). Cross-entropy on masked logits only; the value head stays random. Validation is split by sample, not episode (`clone.py:153-156`). Recorded validation accuracy is 0.77 (`docs/RL_SPRINT3_STATE.md:13`).
- **PPO:** code defaults `train_ppo.py:61-73`. The runs that were used: lr 5e-5, entropy 0.03 on a hold-then-anneal schedule, 4 epochs x 4 minibatches, gamma 0.997, lambda 0.95, clip 0.2, target-KL 0.02 with early epoch stop (`:280-289, 572-579`), value warm-up for 300k steps with the policy frozen at lr 1e-3 (`:290-306, 409-418`), and 10-16 envs (`docs/RL_SPRINT4_DECISIONS.md:11, 203-207`).
- **Reward** (`env.py:212-243, 500-539`): chip = 10 x change in Princess fraction; crown = 3 per crown; ±10 for a win; elixir weight 0. Not potential-based, and the King is excluded. They later measured r(return, win) = 0.967 (`RL_SPRINT4_STATE.md:73`).
- **KL anchor to the clone:** commit `00946cd`, code at `train_ppo.py:226-240, 541-566`. The benefit is stated as unmeasured, and the supervisor never enables it.
- **Opponents:** per episode, one of `brain` / `meta` / `mirror` / `simple` (`env.py:323-345`); `brain_share` splits scripted episodes (`vecenv.py:101-115`). The league snapshots past selves at each eval, samples uniformly at temperature 0.7 / 1.0 / 1.3, and always keeps the first snapshot (`vecenv.py:73-78, 106-129`). There is no PFSP and no exploiters.
  - **Bug:** snapshot deletion sorts lexicographically (`train_ppo.py:634-636`), so `step10000000` sorts before `step2000000`.
- **Scope:** one fixed deck (Hog 2.6), bottom seat only, level 11 (`env.py:69-70, 258, 263, 395`).
- **Compute:** one RTX 4070 Ti SUPER with 8 cores. The headline checkpoint `fixed_cont_6106112.pt` has 6.1M steps of undocumented lineage; "thirty million steps" is cumulative across runs. 2h06m per 6M steps (`RL_SPRINT4_DECISIONS.md:308`).
- **Supervisor** (`scripts/rl_supervisor.py:11-26, 99-110, 247-393, 562-586`): it watches evaluation behaviour, not loss. It trips on:
  - win rate well below the clone's;
  - Hog share collapse;
  - plays per match blowing out;
  - score drift;
  - log silence;
  - low disk;
  - a held-out audit every 3M steps.
  On a trip it rolls back to the best checkpoint and steps down a four-rung ladder that lowers entropy, lr, target-KL and self-play share.

**Documented lessons:**

- A random critic after BC dropped a 75% clone to 35%, three times (`train_ppo.py:297-299`; README flag table).
- Unbounded epochs walked the clone off a cliff (`train_ppo.py:286-289`).
- Entropy 0.01 collapsed; 0.10 randomised the policy (`RL_SPRINT4_DECISIONS.md:16-39`).
- The body-block deadlock voided every checkpoint up to that point (`:43-71`).
- Training only against meta decks gave 16.7% against the rule engine; a 50/50 mix gave 93.3% (`:96-129`).
- 70% self-play raised meta-deck win rate while the rule-engine win rate fell from 41.7% to 16.7% over 10.3M steps (`:133-173`).
- A plateau at 43% from 4.4M steps (`RL_SPRINT3_STATE.md:21-33`).

### 4.2 Side by side with clasher

| | Hasty-CR | clasher (code as it stands; approved plan in brackets where it differs) |
|---|---|---|
| Actor | CNN + MLP, 20.2M, shared trunk | Entity attention (width 128, 4 heads, 4 layers) + LSTM 256, **2,604,979 parameters** (measured) |
| Critic | Shared, public observation | Separate 2-layer privileged encoder, isolated from actor (`clasher: src/clasher/rl/model.py:1150-1165, 2856-2868`) |
| Memory / belief | None | LSTM, 4 history slots, 8 seen-card slots, opponent-state auxiliary heads (`model.py:1174-1221, 1594-1600`) |
| Actions | Flat 2,321 | Factorised type x tile attention, 2,306 joint (`model.py:1223, 1290-1305`) |
| Decision interval | 500 ms | 250 ms (5 native ticks) |
| Warm start | BC from rule bot, holds subsampled | ≤500k complete-game public-script decisions with natural waits, split by deck family (`clasher: src/clasher/rl/council_warmstart.py:61-66, 137-155, 280-292`) |
| Critic after warm start | Random, then 300k-step value warm-up | Random (`imitation.py:2561-2564`), **no warm-up** |
| PPO | 4x4 epochs/minibatches, gamma 0.997, target-KL 0.02 | 2 epochs, gamma 1, lambda 0.95, lr 1e-4, clip 0.2, **target-KL 0 (off)** (`clasher: src/clasher/rl/council_pilot.py:447-462`; implemented at `train_recurrent.py:2302-2304`) |
| Reward | Tower chip / crown / win, not invariant | ±1 terminal + 0.05 potential shaping, gamma 1, zero terminal potential, zero-sum |
| Anchor | Optional, unmeasured | Implemented, forced to 0 (`council_pilot.py:309-310`) |
| League | 40-50% scripts + uniform past selves, first snapshot kept | First 1M: 50% script / 50% initial. After: 25% script / 50% historical / 25% current (`clasher: src/clasher/rl/council_opponents.py:221-227`). **`initial` is not sampled after the first million** |
| Decks / levels | One deck, level 11, one seat | 16-card scope, 19 training decks with separate development and acceptance roles, mixed levels after 1M, alternating seats |
| Evaluation | 60 greedy games, one seat, fixed seed, training opponents | ≥512 paired-seat stochastic games (T = 1), held-out decks, clustered intervals, 3 seeds x 2 arms |
| Environments | 10-16 | Capped at 8, 4 locally [plan: 64] |
| Recurrence | n/a | Full-prefix replay under current weights [plan: 32-step burn-in] |
| Supervisor | Behavioural triggers plus auto-taming rollback | Per-update logs only |

### 4.3 What worked for them that we should consider

1. **Critic warm-up after the scripted warm start.** This is their most important lesson: a random critic destroyed a good clone three times. Our separate critic avoids trunk contamination, but the scripted arm still starts PPO with a random value function, flat lr and no KL guard. Two options:
   - a policy-frozen critic phase, counted in the decision budget and applied to both arms;
   - fitting the critic to Monte Carlo returns from the warm-start games.
2. **Target-KL early stop.** It already exists in our code (default 0.03), but the pilot forces it off. With 2 epochs the risk is smaller, but it is cheap insurance, provided it applies to both arms.
3. **Behaviour-based alarms.** Per-card share collapse, plays-per-match blowout, wait-rate drift, script-opponent win rate inside the training log, and periodic fixed-matrix audits. Keep rollback **manual**: their automatic "taming" ladder changes hyperparameters mid-run, which would break a pre-registered recipe.
4. **Opponent-mix evidence.** Our league phase has 75% learned opponents, close to the 70% self-play that cost them 10M steps. Keeping the initial policy and scripts visible inside the historical slice, and watching script win rate during training, catches the drift sooner.
5. **Entropy tuning by factor.** We already log type and location entropy separately and can set coefficients per head (`train_recurrent.py:2854-2866`). Watch location entropy in the scratch arm.
6. **Budget accounting for learned opponents.** Learned opponents cut their throughput to about a third. Our league phase adds CPU LSTM forwards for opponents (`council_opponents.py:321-342`).

### 4.4 What we already do better

- Recurrent public memory with belief heads.
- An isolated privileged critic.
- Potential-invariant shaping.
- A factorised, 8x smaller actor.
- Deck and level diversity with split roles.
- Paired-seat stochastic evaluation with ≥512 games and replication.
- Exact prefix reconstruction.
- Hashed, per-match frozen opponents.
- Warm-start hygiene: complete games, natural waits, deck-family splits.

---

## 5. Sim-to-real bridge

**Detector:**

- Ultralytics YOLOv8s by default, 640 px, 150 epochs (`scripts/train_detector.py:32-77`).
- 201 class slots, 153 present in validation. Side (player) is split out into `sides.json` (`scripts/prepare_yolo_dataset.py:5-15, 107, 137`).
- Data: KataCR's CR-Detection-Dataset part 2, 5,551 train / 1,388 val (`RUN_JOURNAL.md:1064-1066`).
- **0.959 mAP50** (P 0.949, R 0.926, mAP50-95 0.754) is measured on that dataset's validation split, never on MuMu frames (`RUN_JOURNAL.md:1063-1070`).
- Small sprites have loose boxes: mAP50-95 is 0.594 for Ice Spirit and 0.616 for Skeleton (`:1083-1087`). The validation split may share frames from the same videos; I could not check this because the dataset is absent.
- **Weights are not shipped** (`*.pt` gitignored; `tests/test_rl_policy.py:227-228`).
- A side classifier (small CNN, about 93k crops) replaces colour rules, which scored 52.8% on units in our half, and position rules, which scored 59.0% (`scripts/train_side_classifier.py:8-27`). Below 0.55 confidence it falls back to board half (`vision.py:251-258`).
- Unknown units are silently dropped; projectiles and effects are excluded (`vision.py:47-52, 169-181, 229-231`).

**Capture, actions and latency:**

- Capture uses `adb exec-out screencap` (`scripts/screencap_fast.py:26-81`). Each tap is a separate `adb shell input tap` subprocess: card tap, 80 ms sleep, target tap (`scripts/cr_bot.py:476-478`; `mumu_overnight_bot.py:80-85`). There is **no minitouch or scrcpy** and no acceptance check.
- Loop time is 416.9 ms at 1080x1920, 90.5% of it screencap, and 185.9 ms at 540x960 (`RUN_JOURNAL.md:720-742`). Policy inference is 2 ms.
- The studio already uses `adb exec-out screenrecord --output-format=h264` with PyAV at about 50 fps full resolution (`scripts/studio/devicecap.py:100-135`). That path is far better but not used by the bot.
- A fixed MuMu 1080x1920 linear pixel-to-tile map (`scripts/brain/arena.py:38-60`).
- Hand reading: normalised cross-correlation per slot, abstaining if the top two scores are within 0.04, with duplicate resolution and a 4-frame majority (`scripts/brain/cards.py:1-26, 89-103`; `hand.py:29-67`).
- Elixir and tower bars come from BuildABot and a custom bar reader. **Unit HP is never read.** The clock is wall time since match start (`cr_bot.py:419-426`).
- Windows and MuMu only: hard-coded adb path and serial, plus an emulator package guard before taps (`scripts/emulator.py:26-71`).

**Usefulness for our live adapter** (`clasher: src/clasher/rl/structured_live_adapter.py`, `causal_vision.py`, `live_inference_contract.py`):

1. **Latency budget.** Our adapter uses `cadence_ms = 400` and `maximum_gap_intervals = 2` (`structured_live_adapter.py:166-167`). Full-resolution screencap at about 406 ms would keep tripping the cadence guard. Adopt the screenrecord h264 + PyAV capture (MIT, small, no AGPL imports), and use a faster tap channel with accepted-play verification, which our `own_last_play` design needs anyway.
2. **Side as a measured quantity with its own confidence.** `PublicVisualDetection` already carries `belonging` (`causal_vision.py:18-28`). `VisionEntity` has one `confidence` field (`live_inference_contract.py:169-181`). Their numbers justify a separate side confidence and warn against a board-half fallback.
3. **Hand-slot abstention** maps onto our `own_hand_confidence = 0`. Duplicate-slot resolution is worth copying as an idea.
4. **Emulator package guard and mask-empty diagnostics** (`hold_reasons`, `rl_policy.py:228-235, 304-315`).
5. **Their opponent-cycle model** (`scripts/brain/opponent.py:11-26, 87-102`) could generate *evaluation labels* for our `cycle_plays_until_available` target. It must not be an actor input.
6. **A VOD method for measured perception error:** fit a per-match affine transform from detected crown towers, dropping fits whose residual exceeds 0.75 tiles, with a typical residual of 0.36 tiles (`docs/VOD_CALIBRATION.md`). This fits the strategy's "measured correlated perception errors" requirement.

**Where their bridge conflicts with our contract:**

- They substitute full HP; our contract requires `None` with zero confidence (`live_inference_contract.py:128-138, 315-320`).
- Their inputs carry no confidence.
- Their opponent history is accumulated outside the policy; ours forbids that (`live_inference_contract.py:47-88`; `structured_live_adapter.py:187-192`).
- They use a wall clock; we use OCR'd clock with confidence.
- Their mask depends on a noisy tower HP read and can open illegal placements after a phantom zero. Ours must fail closed.
- They drop unknown entities silently.
- Their encoding is fixed to one deck.

---

## 6. Evaluation claims

**Source:** `reports/eval_fixed_cont_6106112.json`, seed 8000, greedy (`scripts/evaluate_pilot.py:69, 76`), 60 games per opponent. The Wilson 95% intervals are my calculation.

| Policy | vs rule engine | vs meta decks |
|---|---|---|
| Clone | 11/60 = 18.3% [10.6, 29.9] | 47/60 = 78.3% [66.4, 86.9] |
| Trained, 6.1M | **56/60 = 93.3% [84.1, 97.4]** | **52/60 = 86.7% [75.8, 93.1]** |

The +0.78 crown differential (49−2 over 60) is the rule-engine figure; against meta decks it is +0.68.

**Assessment:**

- **Held out means seeds only.** A seed changes only deck shuffles (`sim/match.py:132, 170-172`). The rule engine is deterministic and the agent greedy, so each game is one deterministic trajectory per shuffle.
- **The rule engine is not held out.** It is the BC teacher (`sim/clone.py:63-80`), half the PPO diet (`--brain-share 0.5`), and the supervisor's evaluation opponent (`scripts/rl_supervisor.py:800`). Their own log says "both audited opponents are now in-distribution" (`docs/RL_SPRINT4_DECISIONS.md:126-129`), contradicting the README's "opponents never trained against" (`README.md:384`).
- **The meta decks are the training pool.** Both use `deck_pool()` (`sim/meta_decks.py:82-113`); there is no split.
- **Seat and deck are fixed.** The agent always plays Hog 2.6 from the bottom seat. By their own measurement the bottom seat is worth about 10 points to the rule engine (`RUN_JOURNAL.md:2161-2168`), so the 93.3% is against the rule engine in its weaker seat.
- **Seed reuse.** Seed 8000 is the supervisor's rollback gate (`rl_supervisor.py:302-333`), which makes it validation data. The "fresh" seed-9000 200-game set steps by 1000 as well and contains 59 of the 60 seed-8000 games.
- **Significance.** The rule-engine improvement over the clone is significant (intervals disjoint). **The meta-deck improvement is not** (intervals overlap).
- **Minor inconsistencies:**
  - README 86.7% vs 81.7% in the decisions log for the 50/50 mix (`RL_SPRINT4_DECISIONS.md:106`).
  - "Every number came back identical" holds for wins and losses only.
  - The robustness probe patches a throwaway environment and returns identical numbers under every perturbation (`scripts/robustness_probe.py:45-73, 131`).
  - `run.ps1:53-62` defaults live play to a checkpoint trained before the body-block fix, which their own log calls void.

**What "the simulator marking its own homework" implies:**

- Opponents, reward, legality and evaluation all come from one engine.
- Three policy-relevant engine bugs were found only by a human watching: the body-block deadlock, the cross-map building pull, and lane commitment. Each invalidated checkpoints (`RL_SPRINT4_DECISIONS.md:43-71, 254-278`).
- Their only real-game calibration contradicts their engine on the Hog, the core card of their deck: a blocked Hog landed 4 hits in simulation and 2 in reality (commit `5568739`), and observed Hog speed is 27% below the engine's (n = 36, `docs/VOD_CALIBRATION.md`). §2.3 shows their tower geometry is off by a tile.
- The only live RL sample is five matches against a person, reported as behaviour only: Hog share 3-5% and 266-360 holds per match (`rl_policy.py:174-178, 228-235`). "No trained policy has beaten a human" (`README.md:390`). Their rule bot loses about two-thirds of ladder matches (`RUN_JOURNAL.md:689, 713`).
- **For us:** this is exactly the failure our Tier A regret check, Tier B transfer check, fixed evaluation matrix and prospective freezes are designed to prevent. It is external support for keeping them.

---

## 7. Recommendations, ranked

"Fit" refers to the approved strategy (`reports/strategy_council_20260928/strategy.md`, SHA `2be09f05…`). All items are **ideas**; no code is needed except where noted. Anything that changes pilot hyperparameters or the league schedule must be decided **before the post-admission launch** and applied to both arms. Synthetic optimizer checks may run now; gameplay fitting may not start before Tier A.

| Rank | Recommendation | Expected benefit | Cost | License | Fit / conflicts |
|---|---|---|---|---|---|
| 1 | **Critic warm-up for the scripted-warm-start arm.** Either N decisions with the policy frozen (value-only updates), or regress the critic on Monte Carlo returns from the ≤500k warm-start games. Mirror a same-length critic phase in the scratch arm, or record the asymmetry. | Protects the main arm from the early collapse they hit three times (75% → 35%). Directly affects the pilot's warm-start-vs-scratch conclusion. | Low to moderate: a flag in `train_recurrent.py`, a synthetic test now, and a config entry. | Idea only | **Pilot, decided before launch.** Changes the approved recipe, so record it as an implementer routine choice or get coordinator sign-off. Synthetic checks are fine pre-Tier A. No policy fitting before admission. |
| 2 | **Re-enable the existing target-KL guard** (for example 0.02-0.03) in both arms. Log early-stop counts. | Cheap insurance against large updates, especially just after the warm start. | Very low: one config value (`council_pilot.py:460`). | n/a | **Pilot config.** Same caveat as #1. |
| 3 | **Behavioural training alarms.** Per-card play share, plays and waits per match, script-opponent win rate inside training, the fixed-matrix audit at set decision counts. Rollback stays manual; no automatic hyperparameter "taming". | Catches silent degradation and specialisation early. Their 70%-self-play collapse would have been caught. | Low to moderate: metrics already partly logged (`train_recurrent.py:2264-2268, 5063-5066`). | Idea | **Pilot.** Automatic taming would conflict with the pre-registered recipe, so exclude it. |
| 4 | **Keep initial and script policies visible in the league after 1M.** Include the 1M-decision initial policies in the "historical" 50% (currently `initial` is not sampled after phase one, `council_opponents.py:221-227`). Track script win rate as a guard. | Guards against the specialisation they measured (16.7% vs 93.3% depending on the mix). | Low | Idea | **Pilot.** Compatible with the approved 25/50/25 split if the initial policies are counted as historical checkpoints. Confirm with the coordinator if in doubt. |
| 5 | **Targeted probes from their human-found bugs**, added to development native checks now and to the frozen Tier B targeted probes later. Post-tower-loss lane choice (centre and pocket placements); building pull versus sight range; body block (Hog + Skeletons / Ice Golem / Knight); charge-unit blocking (Prince / Dark Prince vs Knight); Log vs `ignorePushback` units; shield-breaking-hit absorption. | Cheap coverage of exactly the failure modes a Hog-heavy policy would exploit. Resolves the §2.5 open items with native evidence. | Low: native probe configs already exist in this style. | Idea | **Before Tier A as development evidence** (never acceptance), and **Tier B** as targeted probes. Do not use them to tune simulator parameters toward their VOD numbers; that would be gameplay-free but still reference-unverified "fitting". |
| 6 | **Live capture and control path:** `screenrecord` h264 + PyAV (about 50 fps) instead of screencap (about 406 ms); a faster tap channel with accepted-play verification; emulator-package guard; `hold_reasons`-style mask diagnostics; side confidence separate from position confidence; hand-slot abstention. | Makes our 400 ms cadence contract reachable and our confidence/missingness contract honest. | Moderate | `devicecap.py` is MIT (copy with notice). Avoid their Ultralytics code in the core package (AGPL). | **Later:** live-adapter track during or after the pilot. No conflict with the public-information actor, provided their HP and opponent-history shortcuts are not adopted. |
| 7 | **Scalar engine speed-ups:** native-integer entity state, traits resolved at spawn instead of `getattr`, per-tick target candidate caches. Also investigate `fast_path=True` being slower. | ≤12% in the current council path, where the engine is 14% of wall time; larger gains for readiness branch studies and future multi-worker actors. The engine is 5.4x slower than theirs on equal work. | Moderate to high, plus native-parity revalidation | Idea (their code has different semantics) | **Later**, after the pilot or in the next runtime snapshot cycle. Must not modify the frozen runtime used for Tier A. |
| 8 | **VOD calibration methodology** (per-match tower-anchored affine fit, residual gates, forward-only segments, preliminary labels for n < 20) for our human-observation audit and measured perception errors. | Principled noise model for perception and a human-play reference. | Moderate | Idea. Their `data/vod` derives from YouTube, so check terms. | **Later / human-observation track.** Their "observed speed" numbers must not be used to adjust our simulator; native reference stays authoritative. |
| 9 | **KL anchor to the warm-start policy** | Unknown; they never measured it | Very low (already implemented) | n/a | **Follow-up ablation only.** Enabling it in the primary comparison would confound the warm-start-vs-scratch arms. |

**Explicitly not recommended:**

- Their simulator data or mechanics: tower geometry one tile off, a different tower curve, shield overflow, Log ignoring `PushbackAll`, no Tesla hide, no gait. Each contradicts native data.
- Their CNN and flat-action architecture, and their tower-chip reward.
- Greedy single-seat evaluation.
- Their RoyaleAPI tower tables.
- Their live HP substitution and externally accumulated opponent history. Both violate our public-contract rules.

---

## Appendix: reproducibility

- **Clone:** `/Users/sam/Desktop/code/external/Hasty-CR` @ `913608b4`. Venv: `/Users/sam/Desktop/code/external/.venv-hasty`. Their data root is a copy of our decoded logic at `Hasty-CR/tmp/gamedata/csv_logic` (ignored by their git).
- **Speed:** `cd Hasty-CR && ../.venv-hasty/bin/python -B /tmp/hasty_bench/theirs.py 10`, and `cd clasher && .venv/bin/python -B /tmp/hasty_bench/ours.py 10`.
- **Mechanics:** `mech_ours.py`, `mech_theirs.py`, `dp_theirs.py`, `lane_probe.py`, `musk.py` in `/tmp/hasty_bench/`. Probe 3 in `mech_ours.py` spawns the Cannon as a troop; the valid building version is the inline rerun reported in §2.4.
- **Our fixture test:** `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_native_crown_fallback.py` gives 10 passed.
- **Their predictions:** `../.venv-hasty/bin/python -m sim.check`, run on our data plus their tower tables.
