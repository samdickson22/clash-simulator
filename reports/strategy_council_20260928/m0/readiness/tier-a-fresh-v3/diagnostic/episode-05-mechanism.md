# Episode-05 scalar/native reversal: mechanism

**Diagnostic, development evidence only.** This is a read-only analysis of recorded branches. No emulator or adb was used, and no source was changed.

## Verdict

- **First material divergence: tick 2369.** The owner-1 King Tower fires its first shot after activation at a different Goblin in each engine.
  - Native: the King locks onto Goblin `5000046` during the activation first-hit phase, keeps that lock, and fires at it.
  - Scalar: the King picks no target until the 700 ms first-hit delay has finished. It then picks whichever Goblin is nearest at that moment, which is `5000045`.
- **Mechanism:** King Tower target acquisition during activation (targeting). This is a scalar bug, not a controller or transport effect.
- **Classification:** a real mechanics bug that will recur. Each time it fires the effect is small (which swarm unit dies first). In this family chaotic amplification turned it into a win/loss reversal.
- **Fix check:** a monkeypatch that applies the proposed fix only in a /tmp replay makes scalar reproduce the native branch exactly. All 964 decisions match, the final tower HP is identical (7091/5881) and the winner is the same. The patch leaves 30 agreeing branches in 8 families unchanged.

## Pair analysed

| | job | condition | candidate | result |
|---|---|---|---|---|
| scalar | `branches-scalar/job-00160` | balanced/pressure | immediate_play (Archers, action 1796) | loss, own 6966 / enemy 8934, ends at tick 3601 on crowns 0-1 |
| native | `branches-reference-shard0-of8/job-00161` | balanced/pressure | immediate_play (Archers, action 1796) | win, own 7091 / enemy 5881 at 6001 (overtime), crowns 1-1 at 6001 |

Owner 0 is the "pressure" controller. Owner 1 is the root owner. All 6 reversals share one continuation: wait and displaced also converge on this trajectory. This is shown by replay below.

## Alignment (tick-by-tick, 5-tick decision frames plus a per-tick scalar replay)

1. **Ticks 1185-2365: the two engines match.** For every object on every decision frame:
   - positions agree within 0.05 tiles;
   - HP fractions agree within 0.02;
   - tower HP is identical;
   - both controllers take identical actions, and every native command receipt is `ok`.

   So scalar replays the prefix to the root faithfully, and the continuation stays faithful too.
2. **Context.** Owner 0 attacks in the left lane with a Giant, a Dark Prince and Goblins (Goblins deployed at 2135). This destroys owner 1's left Princess Tower at about 2290. That activates the owner-1 King, and the activation clock is identical in both engines:
   - `activation_duration` 3300 ms ends at 2355;
   - `activation_first_hit_delay` 700 ms ends at 2369;
   - the first King projectile appears at 2369-2370 in both engines.
3. **Native King (rich telemetry, `targetEntityKey` / phase runtime):**

   | tick | King target | attackTimelineMs | nearest Goblin (distance in tiles) |
   |---|---|---|---|
   | 2355 | stale `5000002`, the dormant placeholder | 0 | 5000046 1.87 vs 5000045 2.59 |
   | 2360 | **5000046** | 550 | 5000046 1.95 vs 5000045 2.31 |
   | 2365 | **5000046** (kept) | 800 | *5000045 2.00* vs 5000046 2.04 |
   | 2370 | projectile `4000131`: source King, **target 5000046** | 1050 | *5000045 1.91* vs 5000046 2.09 at launch (2369) |

   Native therefore acquires the target inside the first-hit phase, in ticks 2356-2362. The nearest-Goblin order flips at 2363. Native keeps the lock and fires at the Goblin that is now further away.
4. **Scalar King (per-tick replay of job-00160).** `target_id` is `None` through 2368. At 2369 it acquires the nearest Goblin (163, which is native 5000045) and fires. Scalar's projectile at 2370 is at (7.346, 29.099). That is exactly where native's *second* King shot (4000134, at 5000045) is at 2390. The two engines fire the same two shots in the opposite order.
5. **What follows:**
   - **2373 (first tower-damage difference).** In scalar, Goblin 5000046 survives and gets one extra hit on the owner-1 King. King HP is 4074 in scalar and 4199 in native.
   - **2381-2420.** Which Goblin survives changes when the owner-1 Dark Prince (deployed at 2360) switches targets. Owner 0's Dark Prince then dies at 2408 in scalar and about 2418 in native.
   - **2555: first controller divergence.** This follows from the state difference and is not a cause. Owner 0's Zap on owner 1's fresh Goblins lands at (3.5, 20.5) in scalar and (2.5, 19.5) in native. Every command is accepted in both engines.
   - **After 2555.** In native, owner 1's left-lane attack destroys owner 0's left Princess Tower at about 3550. Crowns go to 1-1 and the game goes to overtime; owner 1 wins on tower HP at the 6001 horizon. In scalar that tower survives at 1989, so owner 0 wins 1-0 at 3601. The enemy-HP gap of about 3052 is that one Princess Tower.

## Scalar code responsible

In `src/clasher/entities.py`, `Building._update_active_combat` returns early while the first-hit phase is running. The code is:
`if self.activation_first_hit_delay_remaining > 0: ... if remaining > 1e-9: return`
This return comes before the target-selection block. The code comment calls this phase the "post-aim phase", but the aim step never runs. As a result the King selects `get_nearest_target` only at the tick the phase completes.

The torch simulator mirrors this. In `src/clasher/torch_sim/combat.py`, `first_delay_return` excludes the attacker from `base_actionable`, so it needs the same change. The existing King fixtures do not constrain which target is chosen. `native_king_wakeup_stun_15_535_86.json` and `test_native_king_activation_completion.py` test first-shot timing with a single stationary target only.

## Proposed minimal fix (not applied)

During the first-hit phase, run the building's normal target selection and keep-lock logic before the early return. Do not advance the attack clock. Timing stays exactly as it is; only the identity of the target is locked early.

In outline, in the `activation_first_hit_delay_remaining > 0` branch, before `return`:

```python
target = battle_state.entities.get(self.target_id) if self.target_id is not None else None
if (target is None or not self._is_valid_target(target, is_current_target=True)
        or not self.is_within_target_keep_reach(target)):
    target = self.get_nearest_target(battle_state.entities)
    if target is not None and not self.can_attack_target(target):
        target = None
    self.target_id = target.id if target else None
```

When the phase completes, the existing block keeps this target because it is still valid and within keep reach. The torch_sim combat step needs the same change.

Open detail: native data here is at 5-tick resolution. It pins acquisition to ticks 2356-2362, which is somewhere inside the phase. It does not show whether the search happens on the first tick of the phase or keeps running until a target is found. The patch acquires at the first tick of the phase and re-acquires only if the lock becomes invalid. A per-tick native probe should confirm this before landing, especially for a target that enters range partway through the phase.

### Evidence that it is the whole story

I replayed scalar from the capture using the live controllers, the same way `run_readiness_v2.execute_job` does. The fix was applied as a monkeypatch in /tmp only.

- **Baseline replay** reproduces recorded scalar job-00160 exactly: 6966/8934, winner 0.
- **Patched replay, balanced/pressure:** all 964 decisions for both owners are identical to native job-00161. Final towers are owner 0 Princess 2121 and King 3760, owner 1 Princess 2892 and King 4199. That gives 7091/5881 and winner 1, exactly as native.
- **Patched replay, defense/pressure:** 7091/5881, matching native job-00177.
- **No regressions in branches that already agreed.** The patch changes nothing in 30 agreeing branches:
  - episode-05: alternate_card balanced/pressure and defense/balanced, immediate_play balanced/balanced;
  - episodes 00, 03, 07, 22, 02 and 19: immediate_play in both balanced/pressure and defense/balanced.

  Every one of these still matches its recorded scalar result, and every one except ep07 balanced/pressure matches native.
- **Existing tests:** the 85 King and tower tests pass with the patch loaded as a pytest plugin. The files are `test_native_king_activation_completion`, `test_native_king_wakeup_stun`, `test_native_public_king_projectile`, `test_native_tower_retreat_hit`, `test_native_walking_archer_retarget`, `test_hog26_*` and `test_match_rules`.
- **Separate issue:** episode-07 balanced/pressure differs between scalar and native (7123/4246 against 6771/7172), and the patch does not fix it. It is a different mechanism and has not been investigated here.

## Proposed regression tests

1. **Unit test (fast, no capture).** Create fixture `tests/fixtures/native_king_activation_target_lock_15_535_86.json`. It holds the King and Goblin rows from native job-00161 frames 2355, 2360, 2365 and 2370, with the source decisions sha256 `0a033ab43f9134483417594841ae1260d88f96464b3be597cf2e6adee292b5b5`.

   Test steps:
   - Build a `BattleState` with two owner-0 Goblins. Spawn them with `deploy_delay_override=0` at their 2360 positions: B (the native lock) at (7.140, 29.595) and A at (6.707, 28.692).
   - Call `king.activate()`, then set `activation_delay_remaining` to one tick.
   - Drive `king.update_combat_component`. After the first-hit phase begins, move A to (7.100, 29.212) and B to (7.291, 30.195), their positions at 2366-2370, so that A becomes nearest.
   - Assert that the first King projectile's target is B and that it launches at the unchanged tick.

   This test fails on the current scalar and passes with the fix.
2. **Trajectory test (slow).** Replay episode-05 from `prefixes/episode-05` with balanced/pressure controllers and root action 1796. Assert that:
   - the first owner-1 King projectile targets the Goblin at (7.291, 30.195);
   - owner-1 King HP is 4199 at tick 2375;
   - optionally, the full action stream and terminal HP (7091/5881) equal reference job-00161.

   Both the capture and the reference decisions are sha-pinned in `branch-plan.json` and `result.json`.

## Classification

**This is a real mechanics bug and it will recur.** Every King activation with two or more candidate targets can hit it if the nearest-target order changes during the 700 ms first-hit window. That is common with swarms and with troops that walk around the King. Each time it happens the effect is small: the King kills a different unit first. This family's win/loss reversal comes from chaotic amplification of that small difference: one extra Goblin hit leads to a Dark Prince retarget, then a different Zap placement, and finally a lost Princess Tower. That amplification is why only this one family shows it among 414 pairs.

It is not a transport or controller-timing artifact. Command timing and acceptance are identical, and the controller diverges only 186 ticks after the state does.
