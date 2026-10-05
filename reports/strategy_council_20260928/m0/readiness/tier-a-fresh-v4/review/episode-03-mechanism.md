# Episode-03 material failure (m260928907-episode-03): mechanism

**Diagnostic, development evidence only.** This does not change the v4 verdict. The frozen evaluator BLOCKED v4, and this review adds nothing to or removes nothing from that decision. The fix below was tested only as a monkeypatch in /tmp. No source, ledger or attempt artifact was changed. One native job was replayed read-only on emulator-5582 (probe port 26790) to get per-tick native evidence. That run used the recorded command stream, did not use the controllers, and wrote nothing to the ledger.

## Verdict

- **Which candidate scalar mis-scores:** alternate_card only (Fireball at (13.5, 14.5), action 1417), and only in the two `*/pressure` conditions. Scalar scores wait exactly right in all four conditions.
- **First material divergence: tick 207.** It is the owner-1 **Musketeer's first walking step after the root Fireball's pushback ends**. Native steps toward route node (28,32). Scalar steps toward (27,34).
- **Mechanism:** a scalar route-bookkeeping bug in `Troop._update_knockback_movement` (movement/pathing).
  - At 197 the Musketeer retargets to owner 0's Cannon while it is being pushed. The reset-hit branch builds a ground route for the Cannon, but it does not update `_native_navigation_target_id`, which still holds 2 (the Princess Tower).
  - At 198 the target switches back to Princess Tower 2. Because the stale id matches, scalar skips the rebuild and keeps the Cannon route `[(27,32),(27,31)]` for the rest of the push.
  - Native rebuilds for the tower at 198.
- **Amplification:** the step-207 error is 0.04 to 0.10 tiles. At 297 it flips a knife-edge avoidance check on an owner-1 Archer (probe distance 977 against a threshold of 1000), which gives a drift of about 1 tile. The Log pushback at 313, then the Skeleton spawn displacement at 345, carry it further. The first controller divergence is at 395. The end result is a win/loss reversal.
- **Classification: a real mechanics bug that will recur.** Each occurrence is small, and chaotic amplification turned it into an outcome reversal in this family. It is not transport or controller timing: all commands are identical and accepted until 395, 188 ticks after the state diverges.
- **Fix check (monkeypatch):**
  - Patched scalar reproduces native job-00101 exactly: all 1166 decisions, per-tick positions from 175 to 460 with a difference of 0, and terminal HP 9240/9238 with winner 0.
  - Across all 512 v4 scalar branches, 491 are byte-identical. Of the 21 that change, every one moves closer to native and none moves away. 4 outcomes change, and all 4 now equal native exactly.
  - Ep03 regret drops to 0.
  - 904 movement, pushback, route and interaction tests pass. The 1 failure, `test_inferno_ramp`, also fails without the patch.

## 1. Per-condition outcomes

Root owner is 0, root tick 175. Margin = (own − enemy) / 10928.

| condition | wait: scalar | wait: reference | alternate_card: scalar | alternate_card: reference |
|---|---|---|---|---|
| balanced/pressure | L 8231/10858, −0.2404 | L 8231/10858, −0.2404 | **L 7876/8857, −0.0898** | **W 9240/9238, +0.0002** |
| balanced/balanced | W 7658/5818, +0.1684 | W 7658/5818, +0.1684 | L 7540/6334, +0.1104 | L 7540/6334, +0.1104 |
| defense/pressure | L 8231/10858, −0.2404 | L 8231/10858, −0.2404 | **L 7876/8857, −0.0898** | **W 9240/9238, +0.0002** |
| defense/balanced | W 7658/5818, +0.1684 | W 7658/5818, +0.1684 | L 7540/6334, +0.1104 | L 7540/6334, +0.1104 |

Jobs:
- scalar wait: 98 / 106 / 114 / 122
- reference wait: 99 / 107 / 115 / 123
- scalar alternate_card: 100 / 108 / 116 / 124
- reference alternate_card: 101 / 109 / 117 / 125

How the regret arises:
- **Scalar.** wait has mean score 0.5 and mean margin −0.0360. alternate_card has mean score 0.0. Scalar therefore prefers wait.
- **Reference.** Both candidates have mean score 0.5. Margins are −0.0360 for wait and +0.0553 for alternate_card, so alternate_card is best. Margin regret is 0.0913, over the 0.05 threshold.
- **The mis-scored pair.** Only scalar alternate_card under `*/pressure` disagrees with the reference. Scalar has owner 1 taking a Princess Tower in overtime (tick 4720). Native is 0-0 at 6001, and owner 0 wins on tower HP by 2.
- **Effect of the fix.** If scalar matched reference on that one pair, it would score alternate_card at 0.5 with margin +0.0553 and prefer it, and regret would be 0.

Owner style has no effect in this family. The balanced-owner and defense-owner decision streams are byte-identical in both engines, so the four conditions are really two distinct continuations.

Separate issue, not investigated: displaced_placement under `*/balanced` also reverses (scalar 8520/8394 L, reference 9191/7288 W). It does not drive the failure and the patch does not change it. The ep03 `*/balanced` branches also keep a later divergence at tick 3715 or after, which is a different mechanism; scores still match there.

## 2. Alignment and first divergence

Method:
- A scalar replay through `run_readiness_v2._execute_job_body` reproduces recorded job-00100 exactly (decompressed decisions are byte-identical), with a per-tick entity dump added.
- For per-tick native evidence, reference job-00101 was replayed on port 26790: configure, the recorded prefix, then the recorded `replay-schedule-card` stream, with `observe` every tick from 175 to 460 and `observe-rich` on selected ticks. All 58 recorded 5-tick native frames in that window were reproduced exactly.

| tick | event |
|---|---|
| 175-206 | Identical in position and HP for every body. The Fireball lands at about 196 (Ice Golem 1315→517, Musketeer 721→33, both Skeletons die). The pushback on both engines ends at the same point (13.994, 17.631) at 205, with the same rebound at 206. |
| **207** | **First divergence.** Musketeer native 5000010 (scalar id 11): native (14.001, 17.549), scalar (13.957, 17.558), a difference of 0.044 tiles. |
| 208-213 | Native (14.039, 17.504), (14.055, 17.447), (14.064, 17.388) and so on. Scalar (13.943, 17.500), (13.957, 17.442), (13.971, 17.384). The peak difference is 0.098 tiles at 209. It settles to about 0.03 while the Musketeer stands attacking the Cannon (225-265). |
| 270-295 | The Archers (deployed at 225) pass the Musketeer. The Musketeer's x offset turns into a y lag of 0.045 on Archer 5000016 by 295. |
| **297** | **Amplifier.** Scalar Archer (id 23) consumes route node (27,30) one tick later than native. Its avoidance scan at 297 therefore still faces (379, −936), toward the Musketeer, which is stationary and counts as approaching. The probe-to-Musketeer distance is 977 against a limit of 500 + 500 = 1000, so scalar sets avoidance to +200 and the Archer slides sideways by (−64, −17). Native has already turned toward (26,29), facing away from the Musketeer; its estimated probe distance is about 1138, so no avoidance triggers. |
| 300-340 | The Archer offset grows to 0.21-1.08 tiles. The owner-0 Log (played at 285) pushes it at 313. |
| 345 | The owner-0 Skeletons (played at 340) spawn with a different formation. One spawns on the other side of the displaced Archer, up to 0.67 tiles off. |
| **395** | **First controller divergence.** Owner 1 plays Cannon (action 1915) in scalar and Knight (237) in native. Every command before this is identical and accepted. |
| end | Scalar: owner 1 destroys owner 0's right Princess Tower in overtime and wins at 4720. Native: 0-0 at 6001, owner 0 wins 9240/9238. |

### Native evidence for the route at 207-210

These cell centres come from `pathfinding._cell_center`. The per-step direction is taken from consecutive native positions.

| step | native displacement | matches unit vector toward | implied native route |
|---|---|---|---|
| 206→207 | (+11, −58) | (28,32) centre (14.25, 16.25): (+11.1, −57.9) | stale route with first node (28,32) |
| 207→208 | (+38, −45) | (28,34) centre (14.25, 17.25): (+37.8, −45.3) | rebuilt from cell (28,35) |
| 208→209 | (+16, −57) | (28,33) centre: (+16, −57) | next node, (28,34) popped |
| 209→210 | (+9, −59) | (28,32) centre | next node, (28,33) popped |

Scalar A* from (28,35) gives exactly `(28,34),(28,33),(28,32),…`, and from (27,33) toward the tower it gives `(28,32),…`. Native is therefore consistent with the following sequence:

1. At 198 native rebuilds the tower route from cell (27,33). During a push no nodes are consumed, so the first node stays (28,32).
2. At 207 native keeps that route, because the goal cell is still (27,25). It walks toward (28,32).
3. At 208 the Musketeer's x has crossed 14.0. The approach-goal cell becomes (28,25), so native rebuilds from (28,35).

Scalar instead carries the Cannon route into 207. The goal key changes from (27,31) to (27,25), so it rebuilds from (27,35) and walks through (27,34) and (27,33).

The traced scalar calls confirm the bug:
- At 197, `ground_path_waypoint` is called from `_update_knockback_movement` for target 20 (the Cannon) and gives `[(27,32),(27,31)]`.
- At 198, no call is made even though the movement target is now 2. The stale `_native_navigation_target_id` is 2, so the check `self._native_navigation_target_id != self._movement_target_id` is False.

## 3. Proposed minimal fix (not applied)

In `src/clasher/entities.py`, `Troop._update_knockback_movement`, in the reset-hit branch around lines 3338-3350, record the navigation target whenever a route is built. `_native_movement_waypoint` already does this:

```python
                    ground_path_waypoint(
                        battle_state, self, combat_target.position,
                        target_entity=combat_target,
                        backwards_reference=combat_target.position,
                    )
                    self._native_navigation_target_id = combat_target.id   # added
                    self._native_natural_movement_active = True
```

Once the id is recorded, the existing "new walking target needs a route" block rebuilds when the target changes during the push. No timing or constant changes. The torch adapter hands pushed entities to the scalar `Troop` path (`knockback_active` bodies are not ordinary candidates), so it appears to need no separate change. That should be confirmed when the fix lands.

The monkeypatch used is `/tmp/ep03v4/patch_navid.py`, sha256 `2da63bab…ddd55`. It wraps `_update_knockback_movement` and sets `_native_navigation_target_id = target_entity.id` for any `ground_path_waypoint` call made inside it.

### Patched-replay results

- **ep03 alternate_card balanced/pressure (job 100) and defense/pressure (job 116):**
  - All 1166 decisions for both owners equal native job-00101 / 00117.
  - Positions are identical at every tick from 175 to 460 and at every decision frame to 6001.
  - Terminal towers are 2884/1532/4824 against 1432/2982/4824, giving 9240/9238 with winner 0, exactly as native. (Baseline: 7 of 1166 frames matched native.)
- **All 512 v4 scalar branches replayed with the patch.**
  - 491 decision streams are byte-identical to the recorded ones.
  - 21 change, in episodes 03 (12), 06 (2), 09 (1), 13 (4) and 21 (2). None moves away from native:
    - 10 become frame-exact against native for the whole game: ep03 alternate_card `*/pressure`, ep06 alternate_card `*/balanced`, ep13 alternate_card (all four conditions) and ep21 wait `*/pressure`.
    - The other 11 match native at more frames, and the first divergence moves later (215 to 5720, and 210-220 to 3715). Ep09 wait defense/balanced stays at 2245 but matches native at 678 frames instead of 673.
  - Terminal outcomes change in 4 branches, and all 4 now equal native exactly. Two are ep03 alternate_card `*/pressure`. The other two are ep21 wait `*/pressure`: margin 3207→2649 against native 2649; score was already equal.
  - Same-score agreement with native goes from 505/512 to 507/512. Exact-HP agreement goes from 482 to 486.
- **Counterfactual evaluator run (diagnostic only).** Pinned `evaluate`, ledger opened `mode=ro` with `query_only`, the 4 changed scalar outcomes substituted:
  - Ep03 becomes scalar-preferred alternate_card with regret 0, and there are no material failures.
  - The ep04 wait (0.0409) and ep14 displaced (0.0084) above-floor events remain unchanged. They are a separate review.
  - This does not rescue v4: fixing the scalar requires a new prospective attempt.
- **Tests.** With the patch loaded as a pytest plugin, 904 tests pass. They cover the native pushback, Log, Fireball, route, retarget, avoidance and path tests (including `test_native_postpush_route_and_crown_lock`, `test_native_knockback_*`, `test_native_push_steering` and `test_native_route_*`), plus `test_enabled_spell_interactions`, `test_enabled_troop_interactions` and `test_paths`. The one failure is `test_inferno_ramp::test_inferno_tower_ramp_resets_on_retarget`, which fails the same way without the patch.

### Proposed regression test

Build a fixture from native job-00101, per-tick frames 195-212 (decisions sha256 `64b0b3ef…0c5e`), in the same style as `native_postpush_route_and_crown_lock_15_535_86.json`. Replay episode-03 from `prefixes/episode-03` with the recorded alternate_card command stream and check:

- Musketeer positions (14001,17549), (14039,17504), (14055,17447) and (14064,17388) at 207-210;
- Archer 5000016 at (13360,16022) at 297.

This fails on current scalar and passes with the fix.

## Classification

**A real mechanics bug that will recur.** It fires whenever a troop's target changes during a physical push while the stop-hit/reset-hit branch is in use (Fireball, Log and Snowball-style pushes on troops that retarget, often to a nearby building). Each occurrence is small: the troop takes one to three wrong route steps after the push, about 0.1 tiles. In this family it was chaotically amplified through a threshold-sensitive avoidance check into an outcome reversal. The fix is backed by per-tick native evidence and reproduces native exactly in every changed branch. It was not tuned toward the outcome: the patch is a one-line bookkeeping correction, identified from the traced call sequence before its effect on the outcome was known.

Artifacts: `/tmp/ep03v4/` holds `replay.py` (scalar replay with dump), `native_probe.py` (the port 26790 replay), `patch_navid.py`, `compare.py`, `fidelity.py`, `counterfactual_eval.py`, `allpatched_summary.json` and `native-101/native_ticks.jsonl.gz`.
