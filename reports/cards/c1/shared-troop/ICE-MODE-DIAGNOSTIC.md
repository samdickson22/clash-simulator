Bounded source diagnostic, 2026-10-16. Task `node:delegated-task:command%3Amcp%3Ae000c21a-3b07-43d9-b09f-4bc38d1126f1%3Adelegate-task%3Ac1-ice-spirit-mode-readers-astra-20261016-1144`.
Read-only; this is not implementation review or acceptance.

**Conditionally yes:** synchronizing two runtime fields at Spirit launch can match Python’s exported mode without changing the direct flight calculation. It is **not yet proven mechanically neutral**, because `ordinary` still controls cleanup.

The retained false/true and 1/0 differences are consistent with stale native Stats, but do not establish the actual launch state, cause, or gameplay reachability. The [missing-root ledger](/mpac/sdicks02/repos/clasher-cards-c1/reports/cards/c1/SHARED-TROOP.md:7) explicitly lacks those captures. Equal digests do not establish full-state equivalence.

1. **Minimal conditional candidate**

   At the existing [native Spirit launch transition](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/src/lib.rs:2420), alongside `spirit=true` and `entity_kind=2`:

   - Set `stats.ordinary=false`.
   - Set `stats.projectile_slow_multiplier` to the carrier’s retained **slow-only movement multiplier**, reconstructed faithfully from its represented slow effects.

   Python [rejects kind 2 in `supported()`](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/py/src/clasher/ordinary_combat_clock.py:9), while [the exporter](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/differential.py:175) reads `e.slow_multiplier` directly for kind 2. These are runtime mode changes, not grounds for changing comparison or snapshot output.

   The slow value should be the minimum represented movement-axis slow, including `0.7` when the legacy slow is active, with **1.0 only when no effects exist**. Python’s [recomputation](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/py/src/clasher/entities.py:1262) takes that minimum without percentage rounding. The [snapshot representation](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/live_snapshot.py:44) separates nonstandard effects into `area_slows`; [uniform 0.7 effects](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/live_snapshot.py:105) become `slow_ms`.

   **Do not use `slow_percent(false)/100`.** That [helper](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/src/c56.rs:59) also includes `move_mode`, rounds to integer percent, and starts its minimum at 1.0. Python keeps [movement-mode composition separate](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/py/src/clasher/entities.py:1355). Do not bake haste, attack/spawn axes, or flight speed into this field. Exact capture must confirm the native representation reconstructs the actual Python scalar, including timer-boundary cases.

2. **Why ordinary flight can remain unchanged—and the decisive caveat**

   [Python launch](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/py/src/clasher/cards/ice_spirit.py:100) changes kind without clearing slows. Its [battle dispatch](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/py/src/clasher/battle.py:865) skips character movement and buff updates after launch; [object dispatch](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/py/src/clasher/battle.py:988) advances the committed jump only after the launch frame. Thus retained slow timers need not expire during flight.

   Native [Spirit flight](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/src/lib.rs:1028) directly reads Spirit speed, radius, damage, and stun. Its [status loop](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/src/lib.rs:3077) excludes Spirits, and [object dispatch](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/src/lib.rs:3128) routes them ahead of generic projectiles. Updating the two fields does not directly alter those calculations. Generic [projectile status](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/src/projectiles.rs:125), however, genuinely consumes the multiplier; it is not globally inert.

   **Cleanup is a concrete remaining reader.** [Native target-removal cleanup](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/src/lib.rs:3394) includes living Spirit carriers and switches between `started` and `clock.timeline>0` using `stats.ordinary`. Python [cleanup](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/py/src/clasher/battle.py:2445) also includes living Troop carriers, but its [callback](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/py/src/clasher/entities.py:1685) prefers an existing ordinary clock regardless of current kind.

   Therefore setting `ordinary=false` can change cleanup when `started` and positive timeline disagree. Do not delete/reset the retained clock to accommodate the flag. If captured continuation exposes this discrepancy, a separately justified narrow cleanup correction must preserve Python’s retained-clock decision. Two assignments alone cannot yet be accepted.

3. **Descendants, clone, and reload**

   Native Spirit-created [areas](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/src/lib.rs:1093) and [ElectroSpirit chains](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/src/c56.rs:259) clone configured templates rather than carrier Stats. Verify actual template presence, values, and descendants; this does not prove every configuration harmless. Generic [projectile children](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/src/projectiles.rs:207) instead copy their source, so their status inheritance remains a necessary negative control.

   Native [battle cloning](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/src/lib.rs:3766) preserves state, and [reload](/mpac/sdicks02/repos/clasher-cards-c1/engine-cards/src/lib.rs:3738) deserializes supplied Stats without launch synchronization. Consequently, a launch-only change does not repair an already-launched stale snapshot. Compare uninterrupted execution, clones, and equivalent reloaded roots explicitly.

   Gameplay Clone’s implementation in `src/clone.rs`, its `clone_snapshot.py` prototype construction, and other Spirits’ Python mechanics lie outside this bound. Their selection/reset/inheritance behavior remains unresolved; battle clone is not proof of Clone-spell correctness.

4. **Required witnesses before acceptance**

   - Immutable actual constructor/configuration and paired prelaunch, postlaunch, first-bad roots, bound to exact sources/native/tools; preserve blue lead0/t23 and all original failures.
   - Natural acquisition plus separately labeled forced controls: no slow, retained 0.7, overlapping unequal-axis slows, fractional movement slow, expiry boundary, and movement-mode-only restriction. Distinguish retained slows from mode and haste.
   - Target survives, dies during launch, dies during flight, or itself launches; finish allowed/disallowed, pending-lethal, and retained-clock cases where `started` disagrees with timeline. Compare all cleanup fields.
   - Full-state continuation through homing, fallback destination, pending reservations, impact, damage-before-status recipients, death-spawn recipients, and carrier removal; include optional area and ElectroSpirit chain descendants.
   - Battle clone/reload before launch and midflight; gameplay Clone before/during flight once its implementation is reviewed. Negatives: unlaunched Spirits, ordinary troops, generic status projectiles and their children.

No edits, imports, tests, simulations, or builds were performed. All strict FAILs and the C56 bit-identity requirement remain. Any implementation needs fresh independent review; existing f68/native631ac and launcher97171f5 approvals do not extend to it. The frozen prerequisite and B2-first ordering remain required before combined builds or coverage.
