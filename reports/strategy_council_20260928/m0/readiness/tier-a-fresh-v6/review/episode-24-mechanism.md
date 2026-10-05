# Episode-24 material failure (m260928909-episode-24): mechanism

**Diagnostic, development evidence only.** This does not change the v6 verdict: the frozen evaluator BLOCKED v6, and this review neither adds to nor removes from that decision.

- No source file, ledger or attempt artifact was changed. The fix was tested only as a monkeypatch in /tmp.
- One native job was replayed read-only on emulator-5582 (port 26790). The replay used the recorded prefix and the recorded reference command stream, did not use the controllers, and wrote nothing to the ledger.

## Verdict

- **The engines disagree on only two branches, both alternate_card (Prince at (15.5, 9.5), action 177):**
  - **balanced/balanced** is the win/loss reversal. Scalar wins 9410/6336; native loses 7876/7653.
  - **defense/balanced** has the same score on both engines (loss), but the enemy HP differs: 8322 in scalar against 7653 in native.
  - immediate_play is identical on both engines in all four conditions.
- **The task brief misreads `score_signs`.** In `training_readiness_v2`, `score_signs` compares the *reference* comparator with the *reference* candidate. So `[0,0,0,1]` only says that, in native, immediate_play beats alternate_card under defense/balanced. It is not a scalar-versus-native difference. The engines differ under balanced/balanced (index 1).
- **First material divergence: tick 1531**, which is 1191 ticks after the root (tick 340).
  - The unit is owner 1's **Giant** (native 5000033, scalar 84), which has just been nudged out of attack range of owner 0's right Princess Tower by body pressure from owner 0's still-deploying **Goblins** (played at 1520, Zapped by owner 1 at 1525).
  - Native step: (+70, −2) logic units. Scalar step: (+68, −5). The first difference is **(2, 3) units = 0.0036 tiles**.
- **Mechanism: a real movement/pathing rule difference** in which route node a troop uses when it resumes walking.
  - Native walks straight to route node (30,16).
  - Scalar rebuilds a fresh route from cell (30,18) and walks first to the adjacent node (30,17).
  - The context that triggers it: the Giant stopped at 1409 to hit the tower. It was frozen by owner 0's Ice Spirit from 1439 to 1461, which dropped its target. It re-acquired the tower while standing in range at 1462, then was pushed out of range at 1530.
- **Amplification:** the 0.0036-tile Giant difference changes the collision push on Goblin 5000042 at 1532 (0.036 tiles). The difference grows through Goblin/Skeleton contact to 0.1–0.4 tiles by 1580–1600, and the first HP difference appears at 1605. The first controller difference is at **1630**: owner 1 plays Ice Golem as action 1371 in scalar and 1370 in native, one tile apart.
  - Scalar: owner 0 takes a Princess Tower and wins 1-0 at 3601.
  - Native: owner 1 wins 0-1 in overtime at 4402.
- **Classification: a real mechanics bug that will recur, with chaotic amplification to an outcome flip in this one family.**
  - It is not transport or controller timing. All commands are identical and accepted until 1630, 99 ticks after the state diverges.
  - It is not a sub-tile chaotic seed. A mechanics rule difference produces the first difference, and native per-tick data reproduces that exact difference.
- **Fix check (monkeypatch):** a narrowly gated route-resume rule, variant H below.
  - It makes scalar ep24 alternate_card balanced/balanced and defense/balanced **frame-exact against native for the whole game**: 813/813 decisions and 813/813 frames within 0.001 tiles, final 7876/7653, winner 1.
  - Across all 512 v6 scalar branches it changes 14. **All 14 move toward native and none moves away.** 12 become frame-exact for the whole game.
  - Five outcomes change, and all five now equal native exactly.
  - In a re-evaluation (my reimplementation of the evaluator formula; the pinned evaluator was not run), ep24 regret goes from 0.25 to 0: scalar now prefers immediate_play, wait and displaced_placement, which tie. v6 would have **0 material failures**.
  - Tests: 1106 pass. The 3 failures are the pre-existing `test_hog26_scalar_deployment_ability` failures, which fail identically without the patch.
  - The exact native mechanism is not pinned down; see "Open detail".

## 1. Per-condition outcomes

Root owner is 0 and root tick is 340. Entries are own/enemy remaining HP; margin = (own − enemy) / 10928.

| condition | immediate_play: scalar | immediate_play: native | alternate_card: scalar | alternate_card: native |
|---|---|---|---|---|
| balanced/pressure | W 8844/7876 | W 8844/7876 | W 9274/8639 | W 9274/8639 |
| balanced/balanced | L 7876/7940 | L 7876/7940 | **W 9410/6336 (3601)** | **L 7876/7653 (4402)** |
| defense/pressure | W 8844/7876 | W 8844/7876 | W 9274/8639 | W 9274/8639 |
| defense/balanced | W 9242/7559 | W 9242/7559 | **L 7876/8322 (4461)** | **L 7876/7653 (4402)** |

Jobs (scalar/native):
- immediate_play: 768/769, 776/777, 784/785, 792/793
- alternate_card: 772/773, 780/781, 788/789, 796/797

wait and displaced_placement are identical to immediate_play on both engines.

How the regret arises:
- **Scalar.** immediate_play scores 0.75 with margin +0.0813. alternate_card scores 0.75 with margin +0.0892. Scalar therefore prefers alternate_card.
- **Native.** immediate_play scores 0.75 and alternate_card scores 0.50. Regret = 0.25, which is exactly the threshold.
- **Direction.** Scalar over-rates alternate_card under balanced/balanced (a win instead of a loss). Under defense/balanced it gives alternate_card a worse margin (−0.041 against +0.020).

Owner style has no effect in native for this family: alternate_card balanced/balanced and defense/balanced (781 and 797) are byte-identical decision streams. In scalar they share the same wrong trajectory, then split at 1915, where the balanced and defense owner-0 controllers act differently in the already-diverged state.

## 2. Alignment and first divergence

Method:
- **Scalar replay.** Running `run_readiness_v2._execute_job_body` from the v6 runtime snapshot reproduces the recorded scalar decisions byte-for-byte: job 780, plus all 24 diverging scalar jobs used in the census. A per-tick entity dump was added.
- **Native replay.** Reference job 781 was replayed on port 26790: configure, the recorded prefix, then the recorded `replay-schedule-card` stream, with `observe` every tick and `observe-rich` from 1520 to 1545. All recorded 5-tick native frames from 340 to 1560 were reproduced exactly (0 mismatches).

| tick | event |
|---|---|
| 340–1530 | Identical in position and HP for every body. This covers every 5-tick frame, plus every tick from 1500 to 1530. |
| 1405–1409 | Owner 1's Giant walks route `[(30,16)]` and stops at (15.229, 9.322) to hit owner 0's Princess Tower 5000002. Scalar clears its route on this stop. |
| 1439–1461 | Owner 0's Ice Spirit (played at 1405) freezes the Giant. Its target is dropped in both engines (native `targetEntityKey` is null from 1440 to 1460). |
| 1462 | The Giant re-acquires the tower while standing in range and resumes hitting. Neither engine moves it. |
| 1520–1530 | Owner 0's Goblins deploy at (15.5, 9.5), and owner 1's Zap hits them at 1526 (192 damage and a 0.5 s stun on two of them). Deploying Goblin 5000044 pushes the Giant by (+24, +23) per tick until it is out of range at 1530 (its hit landed at 1529). |
| **1531** | **First divergence.** The Giant restarts walking. Its collision contribution is (+24, +23) in both engines, and the avoidance scan returns −190 in both (the static probe hit is the staggered Goblin 5000044). The walking vector differs. **Scalar:** route `[(30,17),(30,16)]`, input (−11, −50) toward (15.25, 8.75), steered to (44, −28); total (68, −5); position (15.458, 9.373). **Native:** position (15.460, 9.376), total (70, −2). |
| 1532 | Goblin 5000042 is pushed by the Giant: (+52, +63) in native, (+29, +35) in scalar, so the Goblin is 0.036 tiles off. |
| 1535–1600 | Goblin and Skeleton offsets grow to 0.1–0.4 tiles. The first HP difference is at 1605 (a Goblin 121 against 202). |
| **1630** | **First controller divergence.** Owner 1 plays Ice Golem: action 1371 in scalar, 1370 in native. |
| end | Scalar: owner 0 wins 1-0 at 3601, 9410/6336. Native: owner 1 wins 0-1 at 4402, 7876/7653. |

### Native evidence for the route node

Native's (+70, −2) is reproduced exactly only by the combination "first node (30,16), avoidance −190, collision (24, 23)". The results for every candidate node × avoidance value, computed with the scalar `movement_component_vector_logic_units` and `_apply_native_avoidance` code, were:

| first node | avoidance | walk vector | total with collision | matches native (70, −2)? |
|---|---|---|---|---|
| (30,17), scalar | −190 | (44, −28) | (68, −5) | no; this is what scalar does |
| (30,17) | −200 | (45, −25) | (69, −2) | no |
| **(30,16)** | **−190** | **(46, −25)** | **(70, −2)** | **yes** |
| (30,16) | −200 | (48, −22) | (72, 1) | no |
| (30,15) | −190 | (47, −23) | (71, 0) | no |

At 1532 native (+69, −5) is again consistent with node (30,16). Scalar reaches (30,16) one tick later, after it pops (30,17) following its 1531 step.

The traced scalar calls at 1531:
1. `_native_movement_waypoint` is called and returns (15.25, 8.75); the route is `[(30,17),(30,16)]`, freshly rebuilt because the stop at 1409 cleared route and cache key.
2. The avoidance scan hits Goblin 118 as static (spawn stagger 0.1). `skip_native_ground_route_node_inside_static` does not pop (30,17): the distance is 511, against a radius of 500.
3. `_apply_native_avoidance(-11, -50, 52)` returns (44, −28).

## 3. Candidate fixes tested (monkeypatches only)

Four rules were tried. Each was run on job 780 against native, on all 512 v6 scalar branches, and on 45 route, stop, retarget, push, avoidance, collision and freeze test files (1055 tests).

| variant | rule | 780 vs native | 512 branches: action streams changed / toward / away | tests |
|---|---|---|---|---|
| A: pre-pop | After a stop, pop the first rebuilt node before the restart step if it is within 1001 units | Fixes 1531 | Breaks the prefix at tick 340 (Knight 0.12 tiles off): rejected | not run |
| D: retain | An ordinary in-range stop keeps the unconsumed route and cache key; restart resumes it | Exact | 266 / 11 / **254**; exact-HP 488→319 | **3 native fixtures fail** (`outer_cell_pressure_preserves_giant_final_hit`, `postpush_route_and_crown_lock`, `walking_archer_retargets_after_melee_kill`) |
| F: retain if frozen | D, but only if the unit was frozen while stopped | Exact | 32 / 11 / **21** | pass |
| G: F with same static target | F, and only if the stop was on its navigation target, which is a building, and the restart is toward that same target | Exact | 12 / 11 / 1 action; 8 of 10 state-only changes move away | pass |
| **H: G with stationary re-acquire** | **G, and after the freeze the unit must re-acquire and stand attacking the same target before it restarts** | **Exact** | **11 / 11 / 0**, plus 3 state-only changes, all toward | **pass (1106; only the 3 pre-existing hog26 failures)** |

The G failure case (ep27 job 870) separates G from H. There a Giant restarts toward the tower on the very tick its freeze ends, without a stationary re-acquire, and native walks to the fresh route's first node exactly as current scalar does.

### Variant H, all 512 v6 scalar branches

- 498 decision streams are byte-identical to the recorded ones.
- 14 change. Every one moves toward native. The table counts 5-tick frames within 0.001 tiles and 1 HP of native.

| branch(es) | unit, event | frames matching native, base → patched | outcome |
|---|---|---|---|
| ep24 alternate_card balanced/balanced (780) | Giant, the case above | 239/653 → **813/813** | W 9410/6336 → **L 7876/7653 = native** |
| ep24 alternate_card defense/balanced (796) | same | 239/813 → **813/813** | 8322 → **7653 = native** |
| ep03 wait balanced/pressure (98) | Hog Rider 324, restart 3732 | 490 → 943/944 | 8011/8021 → **7447/7986 = native** |
| ep16 alternate_card balanced/balanced and defense/balanced (524, 540) | Hog Rider 260, restart 3338 | 591 → **789/789** | 7704 → **7669 = native** |
| ep21 immediate_play, wait and displaced × `*/pressure` (672, 674, 678, 688, 690, 694) | Giant 118, restart 1245 | 547 → **697/697** | already equal; now frame-exact |
| ep13 displaced_placement balanced/pressure and defense/pressure (422, 438) | Hog Rider 68, restart 1306 | 671 → **702/702** | unchanged (equal) |
| ep18 alternate_card defense/balanced (604) | Giant 278, restart 3738 | 960 → 993/1009 (first divergence 3740 → 4730) | unchanged (equal) |

Totals:
- Exact-HP agreement with native goes from 488/512 to 493/512.
- Same-score agreement goes from 511/512 to 512/512.

All affected units target buildings (Giant, Hog Rider) and were frozen by Ice Spirit while hitting a tower.

### Proposed minimal fix (not applied)

The change goes in `src/clasher/entities.py`, in `Troop.update_movement_component`. At present the stop branch (around lines 3080–3094) clears `_native_ground_route_cells` and `_ground_path_cache_key` on every stop, and the restart branch (around lines 3113–3126) rebuilds.

Proposed rule:
1. When a troop attacking its navigation target, a building, is frozen and then re-acquires that same target while standing in range, prepare the walking route at that moment. That is: build it from the current cell and apply the existing `advance_native_ground_route` reached test (< 1001) once, without travel.
2. Keep that route and cache key.
3. When the troop restarts toward the same target, the existing same-goal cache path in `ground_path_waypoint` resumes the route instead of rebuilding.

The monkeypatch used (`/tmp/ep24v6/patch_reacq.py`, sha256 `cbab1795…58642`) implements the equivalent "stash the unconsumed route at the stop, re-install it on restart" form.

The torch movement adapter consumes the scalar route fields. Whether it needs a mirror change should be checked when the fix lands.

### Open detail

Two native mechanisms give identical routes in all 6 distinct H events in v6, so the v6 data cannot tell them apart:
- **H1:** the pre-stop route is retained across the freeze.
- **H2:** the route is rebuilt at the stationary re-acquisition, and the reached node is popped then.

`/tmp/ep24v6/h2probe.jsonl` shows saved = H2 for every one. A per-tick native probe of a constructed case (tower target, freeze, re-acquire, then a push out of range from a different cell) is needed to choose between them before landing.

### Proposed regression test

Build a fixture from the port-26790 per-tick replay of native job-00781 (`/tmp/ep24v6/native-781/native_ticks.jsonl.gz`, sha256 `4e7f18d3…9cb2b`). Replay episode-24 from `prefixes/episode-24` with the recorded alternate_card stream and assert:

- Giant 5000033 at (15390, 9378) at 1530, (15460, 9376) at 1531 and (15529, 9371) at 1532;
- Goblin 5000042 at (16376, 10388) at 1532.

This fails on current scalar and passes with H.

## 4. Scalar/native reversal census (all v6 families, 512 pairs)

**Win/loss reversals: 1** (0.2% of pairs), which is ep24 alternate_card balanced/balanced:
- The state diverges 1191 ticks after the root, with a first difference of 0.0036 tiles.
- The mechanism is the restart route node above.
- The controller diverges at 1630.
- Variant H removes it.

There are **23 same-score pairs with different final HP**, from 13 distinct trajectories. "State div" is the first 5-tick frame with a body more than 0.001 tiles or 1 HP off; "action div" is the first differing controller action.

| family / branches | root | state div (Δ from root) | action div | fixed by H |
|---|---|---|---|---|
| ep02 wait bp (66) | 310 | 5390 (+5080), Ice Spirit 0.035 | 5675 | no |
| ep02 immediate_play bb, db (72, 88) | 310 | 2985 (+2675), Goblin 0.50 | 3110 | no |
| ep03 wait bp (98) | 1285 | 3735 (+2450), Goblin 0.012 | 4145 | **yes** |
| ep03 wait bb (106) | 1285 | 1400 (+115), Goblin 0.14 | 1465 | no |
| ep08 displaced bb, db (270, 286) | 95 | 2575 (+2480), Goblin 0.12 | 2800 | no |
| ep10 immediate_play bp, dp and wait bp (320, 322, 336) | 95 | 420 (+325), Ice Golemite 0.073 | 735 | no |
| ep10 alternate_card bp, dp (324, 340) | 95 | 3780 (+3685), Archer 0.063 | 4345 | no |
| ep12 displaced bp, dp (390, 406) | 95 | 150 (+55), Goblin 0.84 | 225 | no |
| ep14 immediate_play, wait and displaced dp (464, 466, 470) | 530 | 5100 (+4570), Skeleton 0.027 | 5185 | no |
| ep16 alternate_card bb, db (524, 540) | 385 | 3340 (+2955), Goblin 0.006 | 3395 | **yes** |
| ep24 alternate_card db (796) | 340 | 1535 (+1195), Goblin 0.036 (per tick: 1531, Giant 0.0036) | 1630 | **yes** |
| ep26 immediate_play bp, dp (832, 848) | 120 | 5385 (+5265), Tesla present only in native | 5390 | no |
| ep26 alternate_card bb (844) | 120 | 4180 (+4060), Hog Rider 0.003 | 4205 | no |

Only the ep24 pair flipped a win/loss. Its first difference is among the smallest in the table, but the flip happened because the difference arose mid-fight, 99 ticks before a close controller decision in a game decided 1-0 against 0-1 in overtime. The other same-score divergences were not investigated; the three H does not touch are the likely next targets:
- ep12 displaced, 55 ticks after the root;
- ep03 wait bb, 115 ticks after the root;
- ep10 immediate_play/wait, 325 ticks after the root.

## Artifacts

Everything is in `/tmp/ep24v6/`:
- Replay and probe scripts: `replay.py`, `native_probe.py`.
- Analysis scripts: `align.py`, `census.py`, `summarize.py`, `agg.py`, `fidelity.py`.
- Traces: `trace_col.py`, `trace_giant.py`, `trace_scan.py`.
- Patches: `patch_prepop.py`, `patch_retain.py`, `patch_frozen.py`, `patch_static.py`, `patch_reacq.py`, `patch_h2probe.py`.
- Results: `allreacq_summary.json` (and the other variants), `census.json`, `pytest_*.log`, `native-781/native_ticks.jsonl.gz`.
