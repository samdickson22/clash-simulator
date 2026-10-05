# Scalar movement bound repair

The v7 combat mismatch comes from applying the 250-unit spawn margin to moving bodies. `Entity.finish_movement_tick` calls `clamp_native_object_axis` after collision pressure. The old helper pinned the second deployed Goblin to x17750. Native lets it enter the remainder of the outer cell. That pressure difference changes adjacent Skeleton and Goblin movement, targeting, and attack times.

The first isolated scalar difference occurs at frame434. The second Goblin stays at17750 with the old helper and reaches17786 when movement can use the outer cell. Its adjacent Goblin also moves differently that frame. Native's first subsequent observed Skeleton position at438 is15788,7273. The old scalar position is15749,7313. Native's Goblin position at444 is17789,7261, followed by17669,7259 at445, confirming a full120-unit step from the position outside the spawn margin.

The in-memory experiment changed only the movement clamp to the full arena extent. It matched all 381 relevant native phase position hooks through520, representing 197 unique tick/entity/position observations. The corrected Giant remains at1HP at510, hits the right Princess Tower for253 at scalar frame514, and dies to the Tower at515. The tower ends with43HP, matching native. Native combat event tick t describes the interval ending at public/scalar frame t+1.

The production helper now clamps movement to0 through17999 on x and0 through31999 on y. Explicit quarter-tile spawning and spawn validation remain unchanged. All `entities.py` users of the helper consume movement results. The broader `BattleState.is_entity_position_in_bounds` predicate also serves spawning and Fisherman landing candidate checks and was left unchanged.

## Native source evidence

The retained disassembly is copied into `native-terrain-move-object.txt`. Its original is `artifacts/worktree-data/clasher-simulator-fidelity-20260913/reports/calibration_development_20260915/native-terrain-move-object.txt`.

- `115dc74` loads map width in half-tile cells. `115dc78` compares the next cell to that width, and `115dc7c` branches when the next cell is outside.
- `115dd80` loads500, `115dd84` loads499, and `115dd88` computes old-cell times500 plus499. Crossing right from cell35 therefore stops at17999.
- `115dcf8` branches on a negative next-cell index. `115ddac` loads500 and `115ddb0` computes old-cell times500. Crossing left from cell0 stops at0.
- `115ded4` through `115df08` apply the corresponding upper and lower y rules.

`LogicBattle::spawnObject` still uses the quarter-tile margin. The native Goblin is born at17750,7261 and later occupies17789,7261. Movement and spawning have different bounds.

## Validation

`tests/test_native_outer_cell_pressure.py` adds endpoint, spawn-preservation, body-pressure and native-prefix regressions. The fixture embeds the opened native initial state, commands, 13 ruleset differences, 197 unique phase positions, source-frame hash and tower HP checkpoints.

- 14 new tests passed, including fast and slow scalar paths.
- 73 existing native movement, spawn, collision, knockback and route tests passed.
- Restoring only the old helper in memory fails both new prefix tests at frame438 with the expected Skeleton position difference. Production source hash remained unchanged during this counterfactual test.
- `git diff --check` passed for the scalar changes.

Logs and scripts are retained alongside this report. This is opened development evidence. The original v7 campaign remains failed; this repair does not establish fresh acceptance or authorize training.
