# B2 semantic-v1 Troop-history diagnostic

2026-10-16. Read-only bounded codex/gpt-6-astra high.
Task: `node:delegated-task:command%3Amcp%3Ac2371be3-b4fc-4c4c-9d4e-c37424334a7c%3Adelegate-task%3Ab2-semantic-troop-history-diagnostic-astra-20261016-1118`.
No edits, host access, engine imports, simulation, builds or descendants.

**This is a real Python/Rust continuation mismatch on a forced fixture state, with strong evidence that the triggering combination is unreachable through normal Zap/dash acquisition. It is not an expected-export correction, and it does not establish a reachable-gameplay native defect. The semantic result remains FAIL.**

1. **Responsible transition: frozen-route servicing after dash movement.** Python’s [Entity.finish_movement_tick](/mpac/sdicks02/repos/clasher-cards-b2/engine-cards/py/src/clasher/entities.py:389) updates facing and advances the retained route whenever the Troop is stunned, `_native_moving_when_frozen` is true, and a route remains. [Battle’s movement dispatch](/mpac/sdicks02/repos/clasher-cards-b2/engine-cards/py/src/clasher/battle.py:871) calls this in `finally`, including after `Troop.update_movement_component` returns from special movement.

   Rust’s [dash_movement](/mpac/sdicks02/repos/clasher-cards-b2/engine-cards/src/dash.rs:111) moves the entity and applies external displacement without servicing that route. [movement_one](/mpac/sdicks02/repos/clasher-cards-b2/engine-cards/src/lib.rs:2739) then returns before its frozen-route branch. This preserves native facing/direction/route while Python changes them.

2. **The recorded numbers identify that path precisely.** The retained head `[21,23]` means waypoint `(10.75,11.75)`. Starting at `(9,10.5)`, successive 500-unit dash steps produce waypoint-relative facing Y values `750,250,-250,-750`, exactly matching the receipt. At tick 3, the retained direction `(181,181)` projects the remainder `(1750,-750)` to `707`, below the route-consumption threshold `1001`. Python therefore removes that head and computes `(254,-28)` toward `[22,24]`; native retains `(181,181)` and the old head. These are the operations in [advance_native_ground_route](/mpac/sdicks02/repos/clasher-cards-b2/engine-cards/py/src/clasher/pathfinding.py:747). Position equality is entirely compatible with this metadata divergence.

3. **Fixture history explains why the branches overlap.** The [driver](/mpac/sdicks02/repos/clasher-cards-b2/reports/cards/b2/tools/probe_dash_semantic_v1.py:108) teleports, casts Zap, advances `lead` Python ticks, teleports again, and directly invokes `_launch_dash`. Warming can preserve walking navigation while Zap installs stun and `_native_moving_when_frozen`; [apply_stun](/mpac/sdicks02/repos/clasher-cards-b2/engine-cards/py/src/clasher/entities.py:987) can also clear ordinary combat targets. Thus “old target” need not mean a still-live ordinary target lock: retained navigation can survive independently.

   [_launch_dash](/mpac/sdicks02/repos/clasher-cards-b2/engine-cards/py/src/clasher/cards/bandit.py:131) sets the committed dash target/destination but neither validates stun/range/wind-up nor reconciles ordinary targets or navigation. It does not clear existing stun. This creates travel plus frozen-walking history.

   Normal acquisition requires an unstunned entity, an eligible target in the dash band, and completed wind-up; stun cancels charging, while travel rejects new status effects. The forced launch bypasses those conditions. **Retaining an old route alone is not proof of invalidity**—normal special movement can retain navigation. The decisive suspect is launching while pre-existing stun remains.

4. **Expected export is faithful for these fields.** [differential.entity](/mpac/sdicks02/repos/clasher-cards-b2/engine-cards/differential.py:380) exports actual retained facing; [live_entity](/mpac/sdicks02/repos/clasher-cards-b2/engine-cards/live_snapshot.py:74) exports actual route/direction and frozen status. No source-supported projection correction explains this discrepancy.

The limitation is specific: the supplied summary lacks the pre-launch root’s stun, frozen-moving flag, and target/navigation IDs. Residual Zap stun is a strongly supported inference from the exact numerical signature, not a directly recorded root observation. `first_bad.gate_queries` is also empty, so this row supplies no witnessed during-travel Zap guard query.

**Smallest safe next step:** preserve this failure and inspect an already-retained initial root, if available, for those few fields. Any later fixture revision should establish normal launch preconditions and coherent history, or explicitly classify this as synthetic-state robustness coverage; it must not erase caches merely to pass. If supporting this synthetic state is required, the narrow candidate is C1’s dash movement/finalization parity, separately reviewed—not a comparison exemption.

B2 owns fixture validity, target-guard coverage, and Clone bounds; C1 owns dash acquisition/travel mechanics. All meaningful history/navigation/facing, nonnull actual speed cache, aim, targets/hits/buffs, and descendant-cache checks remain strict. No files or engine sources changed; strict run3422841 and admitted run3586969 were untouched.

