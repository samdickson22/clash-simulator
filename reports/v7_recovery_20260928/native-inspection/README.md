# Saved native combat inspection

Opened development evidence only. No native calls, emulator, campaign rerun, or production-source changes were made for this inspection.

## Identity and tick convention

Configuration: `74d4eefbafb54a46609039370a985bf30f4475f2c6c686b6177f527e55178501`.
Native generation/state epoch: 2103. Native snapshot ticks are directly comparable with scalar snapshot ticks. A native event tick denotes the step start: damage at native event tick 424 appears in scalar post-step snapshot 425. Do not interpret the usual +1 as divergence.

Native actor | Scalar actor | Role
---|---:|---
5000002 | 2 | Owner 0 right Princess Tower
5000007 | 8 | Owner 1 Giant
5000009 | 12 | Owner 1 Hog Rider
5000010 | 15 | Owner 1 Skeleton A
5000011 | 16 | Owner 1 Skeleton B
5000012 | 17 | Owner 1 Skeleton C
5000013 | 21 | Owner 0 Musketeer
5000015 | 40 | Owner 0 Goblin A
5000016 | 41 | Owner 0 Goblin B
5000017 | 42 | Owner 0 Goblin C
5000018 | 43 | Owner 0 Goblin D

## Proven damage chain

The complete combat-event ring proves the 253 HP tower discrepancy is an additional Giant hit, not a damage-value discrepancy:

- Tick 503: Goblin A hits Giant for 125, 468 to 343 HP.
- Tick 507: Goblin C hits Giant for 125, 343 to 218 HP.
- Tick 509: Musketeer hits Giant for 217, 218 to 1 HP.
- Tick 513: Giant hits the tower for 253, 296 to 43 HP (sequence 2829838).
- Tick 514: tower projectile hits Giant for 109 requested/1 actual and kills it (sequences 2829840–2829841).

Scalar already kills the Giant at post-step 506, preventing that last hit. Tower snapshots still agree at tick 510 because the extra native hit occurs afterward.

## Earlier divergence

Native Skeleton C and scalar actor 17 match exactly through movement stop tick 432: [15666, 8198] in native coordinates. The native target reset at 428 and movement positions at 429–431 also match scalar. By native attack release 441, its position is [15689, 8269]; scalar pre-step 441 is [15666, 8407]. Thus the first observed drift is bounded after tick 432 and no later than tick 441.

Native phase event 444 places Goblin B at [17789, 7261], beyond the 17750 deployment inset. Scalar Goblin B remains [17750, 7261]. This is concrete evidence that native body pressure may move an actor beyond its initial deployment clamp. The scalar agent tested an in-memory replacement of this clamp. Independent comparison of its resulting trajectory against the first native phase observation for each actor/tick gives 204 matching positions and zero mismatches (`counterfactual-phase-check.json`). The Giant survives at 1 HP and the tower receives its final hit in this counterfactual. This supports the movement-boundary clamp as the cause of the observed chain.

Native Skeleton C changes target from Goblin C to Goblin B at event tick 454, then damages Goblin B at 464. Scalar retains Goblin C and damages it at post-step 463. Goblin C kills native Skeleton B at 459; Goblin B kills Skeleton C at 466; Goblin C kills Skeleton A at 486. The last Skeleton death happens at scalar post-step 481, six steps earlier than the native event's equivalent post-step 487, accelerating the Giant engagement.

## Evidence files

- `frames-420-540-rich-excerpt.json`: six saved frame excerpts with object state and complete combat/phase rings.
- `damage-events-420-540.json`: compact damage/death records including native identities, positions, amounts, and HP transitions.
- `phase-events-420-520.json`: deduplicated phase events from the saved rings, including movement samples and target changes between snapshot ticks.
- `artifact-hashes.json`: SHA256 of the source capture and diagnostic files.

Combat and phase rings at all six saved snapshots report complete true, zero overflow/rejections, and no sequence gap. Special movement, action movement, character state, and visibility rings at450 contain no events. The remaining-runtime ring contains lifetime and tower-aggro events but no additional samples for this narrow contact interval.

## Boundary persistence and native bounds

At native tick 444, Goblin B has position [17789,7261] in three hooks: movement_scale(120), effective_movement_speed(120), and movement_scale(100). At tick 445, both movement hooks report [17669,7259]. The (-120,-2) displacement is consistent with a full movement step starting at17789; clamping to17750 before that step would put x at17630. Together with the full local counterfactual agreement, this supports a persisted position beyond17750 rather than only a transient pre-clamp hook value.

Independently read retained `reports/calibration_development_20260915/native-terrain-move-object.txt`. The routine at0x115db8c reads old coordinates and adds the movement vector at0x115dbf4–0x115dc00. Crossing into an out-of-map positive x cell branches at0x115dc74–0x115dc7c to0x115dd80; the correction is oldCellX*500+499 at0x115dd80–0x115dd88. From the last valid cell35 this is17999. A negative crossing from cell0 branches at0x115dcf8 to0x115ddac and writes oldCellX*500=0. Corresponding y branches at0x115ded4 and0x115df00 follow the same rule. No250 inset appears in this routine. The reviewed contract is ordinary bounded movement from a valid cell; this does not claim behavior for arbitrarily large jumps through multiple cells.

All scalar `clamp_native_object_axis` consumers are movement operations: accumulated body pressure, knockback, death-spawn travel, ordinary movement, or external displacement. Actual spawning separately clamps to [250,arenaUnits-250] in `BattleState._spawn_troop` and must retain that rule. `recover_native_ground_position` separately applies that inset for its recovery routine. `BattleState.is_entity_position_in_bounds` still uses the inset before the repair and must be considered separately; it also has spawn-snap callers.

## Independent repair review

Reviewed the scalar repair to `clamp_native_object_axis` and `tests/test_native_outer_cell_pressure.py`. The moving-axis endpoint [0,size-0.001] agrees with the native integer-cell crossing behavior. Spawning still uses its explicit quarter-tile inset. The tests cover spawn-to-pressure movement, x/y endpoints, and197 distinct native actor/tick positions through the Giant's final hit. Independently checked that all197 fixture positions occur in the preserved native phase ring and its source SHA256 equals the retained capture. No native-contract or accidental spawn-semantics issue was found in this narrow review. The existing movement-bounds predicate also serves spawn snapping, ground validation, and Fisherman landing; changing those policies requires separate evidence.
