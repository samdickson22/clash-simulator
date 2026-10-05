# C56 engine audit

Updated 2026-10-03. This is a code, current native-data and scalar-test audit. No new native scenario has run, so “match” means no discrepancy found in the inspected paths, not native admission. Existing bundle notes describe the pre-repair state. Current runtime assets take precedence over the older decoded APK catalog. Evidence and hashes are in `live_asset_evidence.json`.

The table covers the 40 additions to P16. “Repaired” records work across both engine-track sessions. Residual severity retains timing or geometry uncertainty even where the large defect was repaired. Tornado is a suspected consequential rule question, not a demonstrated defect.

| Bundle | Card | Verdict | Repaired | Evidence and remaining question |
|---|---|---|---|---|
| B1 | Barbarian Barrel | small | no | B1_spells_control.md; ../scenarios/manifest.json, B1_BarbLog; crown damage and roll timing |
| B1 | Arrows | match | no | B1_spells_control.md; ../scenarios/manifest.json, B1_Arrows |
| B1 | Tornado | consequential, unconfirmed | no | B1_spells_control.md; B1_tornado_king controls in scenarios/manifest.json; no proximity-wake change without trace |
| B1 | Electro Spirit | small | no | B1_spells_control.md; chain hop timing |
| B1 | Lightning | small | no | B1_spells_control.md; projectile flight and shield-aware target ranking |
| B1 | Poison | small | no | B1_spells_control.md; 8/9 tick phase and versioned crown damage |
| B1 | Rocket | match | no | B1_spells_control.md; ../scenarios/manifest.json, B1_Rocket |
| B1 | Earthquake | small | no | B1_spells_control.md; live/versioned damage comparison pending |
| B1 | Royal Delivery | small | no | B1_spells_control.md; water placement and spawn timing |
| B2 | Baby Dragon | small | no | B2_air_splash.md; live/catalog projectile damage difference |
| B2 | Minions | small | no | B2_air_splash.md; deploy delay/formation |
| B2 | Bats | small | no | B2_air_splash.md; deployment geometry |
| B2 | Minion Horde | match | no | B2_air_splash.md; six-body formation/stagger |
| B2 | Balloon | match | no | B2_air_splash.md; 3 s death bomb data |
| B2 | Wizard | small | no | B2_air_splash.md; projectile origin and mass need native confirmation |
| B2 | Valkyrie | small | no | B2_air_splash.md; finish-animation behavior under target death |
| B2 | Princess | small | no | B2_air_splash.md; projectile vs character splash radius |
| B2 | Firecracker | small | no | B2_air_splash.md; deflection fields remain unmodelled |
| B2 | Dart Goblin | match | no | B2_air_splash.md; BlowdartGoblin data path |
| B3 | Elite Barbarians | small | yes | B3_ground_melee_swarm.md; native mass repaired, movement tweak unresolved |
| B3 | Berserker | small | yes | tests/test_scope_engine_cards.py; damage/range/mass repaired; ActionBerserk phase needs trace |
| B3 | Mini PEKKA | match | no | B3_ground_melee_swarm.md |
| B3 | Skeleton Army | small | no | B3_ground_melee_swarm.md; deployment geometry |
| B3 | Goblin Gang | match | no | B3_ground_melee_swarm.md; mixed swarm data/stagger |
| B3 | Rascals | small | yes | B3_ground_melee_swarm.md; masses repaired, second-group stagger remains |
| B3 | Golem | match | no | B3_ground_melee_swarm.md; existing gait/death-spawn paths |
| B3 | Royal Hogs | match | no | B3_ground_melee_swarm.md; wide split formation |
| B3 | Wall Breakers | match | no | B3_ground_melee_swarm.md; kamikaze commit/death path |
| B3 | Fire Spirit | small | yes | tests/test_scope_engine_cards.py; one kamikaze splash repaired, flight timing needs trace |
| B3 | Royal Ghost | small | no | B3_ground_melee_swarm.md; reveal-at-hit vs reveal-at-range unresolved |
| B4 | Furnace | small | yes | live_asset_evidence.json; tests/test_scope_engine_cards.py; walking troop and live 5 s spawns; first phase and forward offset provisional |
| B4 | Goblin Hut | small | yes | live_asset_evidence.json; tests/test_scope_engine_cards.py; range wake, 1 s delay, 2.2 s cadence, 0.5 s deploy; wake/sleep and angle need trace |
| B4 | Inferno Tower | match | no | B4_buildings_champions.md; existing ramp/reset paths |
| B4 | X-Bow | small | no | B4_buildings_champions.md; turret rotation not modelled |
| B4 | Bomb Tower | match | no | B4_buildings_champions.md; delayed death bomb |
| B4 | Miner | match | no, verified | live_asset_evidence.json; runtime and device backup both -80%; 39 L11 crown damage retained and regression-tested. Old -75% finding withdrawn |
| B4 | Goblin Barrel | match | no | B4_buildings_champions.md; flight + three goblins |
| B4 | Mighty Miner | small | yes | tests/test_scope_engine_cards.py; lane tunnel + delayed 332-damage bomb; first cast/tunnel/emergence phase remains native-unverified |
| B4 | Goblinstein | small | yes | live_asset_evidence.json; doctor-owned tether, eight 94-damage pulses, dead-monster anchor; width/hit phase/duplicate-copy rules need trace |
| B4 | Archer Queen | match | no | B4_buildings_champions.md; existing cloak/cast/cooldown tests |

Counts: 15 match, 24 small, 1 suspected consequential. Eight cards repaired in this track, including partial repairs with residual questions. Miner required verification, not a mechanics change.

## P16 and extraction boundary

Phase 1 freeze was published at 2026-10-03T05:22:00Z after 15 scope tests and two checks of 15,949 state boundaries, each with zero mismatches. The data agent acknowledged its copy at 05:23:43Z. Champion repairs and controller changes are later than that extraction copy. `ENGINE_FREEZE_READY` preserves the Phase 1 hashes and is not rewritten for Phase 2.

## Screen attribution

The baseline screen completed all 1,897 unique matches from 1,900 input rows, with three duplicate tags and zero errors. There are 1,191 finite first-contradiction times and 706 null times. The 43-column design has full rank; residual RMSE is 50.05 s. `SCREEN_ATTRIBUTION.md` and `screen_attribution.json` contain all 40 coefficients, HC3 standard errors, counts, sensitivity fit and source hash.

| Priority | Card | Conditional seconds | HC3 SE | Finite-event presence |
|---|---|---:|---:|---:|
| 1 | GoblinHut | -24.99 | 19.00 | 19 |
| 2 | Goblinstein | -24.00 | 16.10 | 27 |
| 3 | Ghost | -18.31 | 4.35 | 205 |
| 4 | FireSpirits | -17.70 | 15.86 | 20 |
| 5 | FirespiritHut | -16.40 | 11.94 | 25 |
| 6 | Balloon | -15.08 | 5.03 | 438 |
| 7 | Rascals | -14.68 | 15.70 | 20 |
| 8 | Berserker | -13.49 | 8.32 | 102 |

These associations come from the pre-repair baseline, not a repair comparison. Goblin Hut, Goblinstein, Fire Spirit and Furnace have only 19-27 finite-event exposures and wide uncertainty. Royal Ghost and Balloon have larger samples. Co-occurring deck cards, forms and outcome selection prevent causal attribution. Null times remain separate in the primary fit; the second fit uses match-end truncation as a sensitivity analysis.

## Controller and native queue

Explicit `PublicScriptedOpponent(..., card_scope="c56")` accepts C56 action cards with public v4 or pinned v5 observations. The P16 default and admission roster remain unchanged. C56 adds enemy-side deployment, siege/spawner placement, pull/DoT/top-three spell scoring, static air awareness and nested-body metadata. Its declared champion rule masks abilities. The engine API and B4 scenarios exercise those separately.

Constructed scalar development coverage: 336/336 roots chose legal non-wait actions, 336/336 offered at least two card choices above wait, 266/336 gave the focal card a score above wait, and all 56 cards had useful focal coverage in at least one context. Both seats and idle, ground-cluster and air-threat contexts are represented. `../controller_coverage.json` contains all roots and source hashes. This is not sampled Tier A coverage or a playing-strength result.

`../scenarios/manifest.json` contains 51 written scenarios spanning B1-B4. `../scenarios/run_bundle.py` validates without connecting to a probe by default and requires `EMULATOR_OK`, `--run` and an explicit port to execute on an already provisioned emulator. No emulator was started and no scenario was run natively. Native trace acceptance remains for the coordinator's queue; shield-order, radius-edge, death-payload and Ghost-reveal probes are now included.

## Final validation and root declarations

The final combined suite passed 78 tests. `../identity-v3-final.log` checked 12 P16 episodes and 15,949 state boundaries with zero mismatches. `../PHASE2_SOURCE_SHA256` binds the final source files. These checks are scalar evidence, not native acceptance.

Root generator v3 produced four prospective 32-family banks using 2,925 training-role human decks from 69,380 perspectives. All 128 episode seeds and designs are distinct, and native card-ID configuration was checked in memory. See `../root-v3/README.md` for scope, archetype selection, failure retention, air-opponent handling and the remaining capture/admission integration. No episodes were captured from those declarations.
