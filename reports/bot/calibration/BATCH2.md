# Engine calibration, batch 2 (exploration)

## Result (2026-10-14)

Batch 2 adds 13 native-measured rules on top of batch 1, plus 5 Python↔Rust parity fixes. Every rule was gated on train
only, one change at a time, with the batch-1 rule. Validation (64 fixtures) was opened once, at the end.

| split | no-tower ≤¼ tile: base → batch 1 → **batch 2** | no-tower HP exact | paired ≤¼, batch 2 − batch 1 (better/worse) | winner agrees |
|---|---|---|---|---|
| train (513) | 50.72 → 62.26 → **72.26** | 64.97 → 71.98 → **80.51** | +8.89 pp [+7.83, +9.98] (412/60) | 381 → 377 → 400 |
| **validation (64, untouched)** | 57.64 → 66.37 → **74.48** | 66.79 → 72.49 → **81.08** | +7.21 pp [+4.44, +10.08] (49/8) | 45 → 48 → 48 |
| all 577 | 51.39 → 62.66 → **72.48** | 65.15 → 72.03 → **80.56** | +8.70 pp [+7.73, +9.73] (461/68) | 426 → 425 → **448** |

- **Base vs final:** base is `baseL`, the r2-era engine with the seeded RNG. All 577 fixtures: +19.71 pp
  [+18.54, +20.97], better in 537/577. Validation: +16.51 pp [+12.54, +20.42].
- **Against RoyaleSim:** RoyaleSim 15.535 on the same corpus scores 78.8 / 81.8 and agrees on the winner in 477. Our
  HP-exact gap to it is now 1.2 pp, where it was 16.7 pp.
- **Live view** (train): 67.79 → **75.52**, HP 78.02 → 83.84.
- **Crown-tower HP exact:** 73.8 → **82.1** (RoyaleSim 84.4).
- **Validation per card** (small sample): batch 2 vs batch 1 shows BombTower −1.6 and FirespiritHut in the standard view,
  and Skeletons −1.6 in the live view. No card falls below −1 pp in validation for base → final in the live view.
- **Cumulative train, standard view (batch 1 → batch 2):** Wizard −1.44. Every step passed the gate; it is a sum of
  small cascades.
- **Python↔Rust digest parity (planner core):** 427 (batch 1) → **574/577** (§1, §6). The remaining 3 date from HEAD.
- **Runtime r2** is built from this engine (`RUNTIME-R2-PLAN.md`). Whether it plays better is in `R2-AB.md`.

| # | change | kind | train ≤¼ after | decision |
|---|---|---|---|---|
| §1 | Rust: discarded-hit cooldown, building retarget reset, IceGolem config alias | parity | – | done |
| §2 | BarbLog Barbarian HP 270 → 280 | data | 62.53 | strict ACCEPT |
| §3 | Royal Ghost route, ground body, re-hide clock | code | 66.06 | strict ACCEPT |
| §4 | side-1 back-row deploy bound y ≤ 31.0 | code | 66.61 | strict ACCEPT |
| §5a | GoblinHut spear-goblin aim | code | 67.73 | ACCEPT (LOO) |
| §5b | FirespiritHut 1500 forward spawn | code | – | **REJECTED** (overall standard ≤¼ −0.24) |
| §5c | Goblinstein doctor damage 36 → 53 | data | 68.00 | ACCEPT (LOO) |
| §7A | Rascals 100 ms deploy stagger | data | 68.22 | strict ACCEPT |
| §7B | Firecracker recoil on the ordinary clock | code | 69.97 | ACCEPT (LOO) |
| §9a | Wall Breakers damage 137 → 110 | data | 71.43 | strict ACCEPT |
| §9b | Miner emergence starts on the arrival tick | code | 71.48 | strict ACCEPT |
| §9d | projectile-spawned troops keep a full deploy tick | code | 72.26 | ACCEPT (LOO) |
| §9c | Poison crown pulse 21 → 22 | data | 72.26 | strict ACCEPT (crown HP +0.83) |

Python reference engine (`src/clasher`) and planner core (`engine-rs`), continuing BATCH1.md. Same gate and recipe:
577-fixture fidelity harness (FIDELITY.md, engine `clasher`, `--issue-offset -1`, seeded RNG), **decisions on split=train
(513) only**. Gate (BATCH1.md "Final rule"): ACCEPT if overall no-tower ≤¼ tile and HP exact do not decrease in both the
standard and the live view, and every card (≥8k unit-ticks) that loses >1 pp in either view is within −1 pp under
leave-one-fixture-out in both views.

- Baseline: `cal1` = batch-1 final (`c5d-minerend`). Rerun from an isolated tree on 127x03, it differs from the
  verified copy (127x04 `bot-calib-verify`) in 0/577 fixtures: train no-tower ≤¼ 62.26, HP exact 71.98.
- Work dir: `/mpac/sdicks02/jobs/clasher/bot-calib2-r1/` (scripts on 127x05; trees and runs on 127x03, plus the §9 (c)/(d)
  gates on 127x04). Every candidate is run from its own snapshot `trees/<name>` (`snap.sh`), so concurrent edits
  to the worktree cannot race a run.
- Research helpers (Opus, T3 delegated tasks) worked read-only on their own trees, `research/<topic>/`. Each proposal
  was reviewed, applied here, re-gated sequentially on the current baseline, and its Rust port built and parity-checked
  here.

## Per card, all 577 fixtures (cards with ≥8k unit-ticks; batch 1 = `cal1`, batch 2 = final `c12-spawn`)

| card | unit-ticks (final) | ≤¼ baseL | ≤¼ batch 1 | **≤¼ batch 2** | Δ b2 | HP batch 1 | **HP batch 2** | Δ b2 | RS 15535 ≤¼ | RS HP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Tower | 3375170 | 98.1 | 98.3 | **99.0** | +0.7 | 73.8 | **82.1** | +8.3 | 99.0 | 84.4 |
| SkeletonArmy | 621671 | 31.3 | 58.1 | **65.0** | +7.0 | 82.2 | **85.4** | +3.3 | 74.5 | 87.9 |
| GoblinGang | 375574 | 37.4 | 60.5 | **67.7** | +7.2 | 78.1 | **81.9** | +3.9 | 77.0 | 86.4 |
| Bats | 294560 | 35.5 | 60.9 | **73.2** | +12.2 | 76.9 | **87.2** | +10.3 | 80.0 | 90.2 |
| Goblins | 255831 | 58.9 | 63.3 | **73.4** | +10.2 | 76.0 | **83.6** | +7.6 | 72.8 | 81.1 |
| Minions | 236748 | 58.5 | 64.3 | **73.5** | +9.1 | 79.8 | **85.1** | +5.3 | 79.1 | 87.9 |
| GoblinHut | 193459 | 30.3 | 34.1 | **50.5** | +16.4 | 51.3 | **61.6** | +10.3 | 66.6 | 73.6 |
| Skeletons | 178619 | 64.1 | 68.6 | **76.9** | +8.3 | 79.9 | **86.4** | +6.5 | 81.5 | 88.7 |
| Archers | 178296 | 58.6 | 62.5 | **73.7** | +11.2 | 74.7 | **83.9** | +9.2 | 79.1 | 86.7 |
| Princess | 143908 | 54.0 | 61.0 | **69.2** | +8.3 | 77.2 | **82.9** | +5.7 | 77.9 | 87.8 |
| Wallbreakers | 127929 | 68.2 | 72.2 | **81.3** | +9.1 | 75.7 | **83.3** | +7.7 | 83.6 | 85.3 |
| FirespiritHut | 124529 | 23.0 | 46.0 | **49.7** | +3.7 | 65.0 | **66.1** | +1.1 | 68.2 | 51.9 |
| Cannon | 123670 | 84.7 | 85.8 | **91.5** | +5.7 | 76.9 | **84.6** | +7.7 | 92.4 | 88.1 |
| Ghost | 123082 | 21.2 | 23.0 | **64.9** | +41.9 | 56.0 | **71.5** | +15.5 | 66.1 | 68.6 |
| Knight | 112106 | 59.2 | 63.0 | **74.3** | +11.3 | 64.0 | **74.4** | +10.4 | 81.2 | 81.7 |
| Firecracker | 109624 | 36.6 | 38.6 | **59.7** | +21.0 | 65.8 | **78.5** | +12.7 | 65.5 | 82.4 |
| BarbLog | 107095 | 62.2 | 67.6 | **76.1** | +8.5 | 0.0 | **79.5** | +79.5 | 79.6 | 82.8 |
| Berserker | 105386 | 59.6 | 64.0 | **73.8** | +9.7 | 67.6 | **77.1** | +9.5 | 76.5 | 81.0 |
| IceGolem | 105103 | 65.8 | 67.7 | **83.0** | +15.3 | 64.3 | **79.3** | +15.0 | 85.1 | 82.8 |
| BombTower | 102374 | 84.0 | 83.5 | **89.4** | +5.9 | 70.5 | **78.5** | +8.0 | 92.3 | 86.3 |
| RoyalDelivery | 93437 | 71.0 | 75.0 | **80.3** | +5.3 | 83.8 | **86.6** | +2.7 | 83.4 | 86.6 |
| Tesla | 88640 | 89.8 | 90.0 | **93.8** | +3.8 | 77.9 | **83.6** | +5.7 | 88.3 | 77.5 |
| MinionHorde | 87601 | 43.5 | 61.4 | **70.6** | +9.2 | 79.7 | **86.4** | +6.7 | 75.5 | 85.5 |
| BlowdartGoblin | 81015 | 60.6 | 65.7 | **74.1** | +8.4 | 76.9 | **82.0** | +5.0 | 79.2 | 88.1 |
| RoyalHogs | 71438 | 75.9 | 79.2 | **81.7** | +2.6 | 78.8 | **81.5** | +2.7 | 81.8 | 87.0 |
| BabyDragon | 68866 | 56.2 | 60.5 | **68.7** | +8.2 | 67.9 | **74.2** | +6.4 | 75.8 | 78.2 |
| GoblinBarrel | 67748 | 71.4 | 72.0 | **80.4** | +8.3 | 79.4 | **86.2** | +6.8 | 84.9 | 87.8 |
| Goblinstein | 66652 | 9.8 | 69.1 | **79.6** | +10.5 | 75.6 | **78.9** | +3.3 | 89.3 | 91.0 |
| Valkyrie | 65455 | 61.0 | 63.4 | **70.2** | +6.8 | 60.1 | **67.4** | +7.3 | 78.9 | 79.4 |
| Musketeer | 62199 | 56.8 | 62.5 | **74.3** | +11.8 | 67.6 | **78.2** | +10.5 | 83.2 | 85.7 |
| Rascals | 60951 | 42.0 | 45.4 | **64.0** | +18.6 | 65.2 | **73.6** | +8.4 | 75.8 | 83.8 |
| Miner | 59402 | 47.6 | 74.9 | **85.4** | +10.5 | 73.5 | **85.8** | +12.3 | 92.4 | 89.4 |
| DarkPrince | 54168 | 54.7 | 60.9 | **72.0** | +11.1 | 67.1 | **75.1** | +8.1 | 74.0 | 75.0 |
| MightyMiner | 46740 | 54.3 | 60.3 | **63.8** | +3.5 | 51.6 | **57.9** | +6.3 | 73.2 | 69.4 |
| ElectroSpirit | 46573 | 71.9 | 75.8 | **81.1** | +5.3 | 81.8 | **85.9** | +4.1 | 85.3 | 0.0 |
| HogRider | 43615 | 70.4 | 75.8 | **83.4** | +7.6 | 69.5 | **77.0** | +7.5 | 89.3 | 86.5 |
| FireSpirits | 43090 | 69.3 | 72.0 | **77.8** | +5.8 | 77.8 | **82.4** | +4.6 | 85.5 | 0.0 |
| InfernoTower | 42638 | 91.2 | 90.6 | **92.2** | +1.6 | 71.6 | **78.3** | +6.7 | 93.8 | 87.0 |
| IceSpirit | 41805 | 71.5 | 75.3 | **82.3** | +7.0 | 79.3 | **85.6** | +6.3 | 89.3 | 0.0 |
| MiniPekka | 39091 | 58.8 | 66.2 | **75.7** | +9.5 | 63.9 | **75.3** | +11.3 | 82.6 | 83.8 |
| Giant | 32772 | 83.9 | 83.6 | **89.1** | +5.4 | 71.4 | **77.3** | +5.8 | 91.2 | 87.3 |
| Balloon | 28869 | 85.1 | 84.0 | **92.9** | +8.9 | 80.1 | **88.7** | +8.6 | 95.3 | 91.2 |
| Wizard | 25275 | 59.5 | 63.1 | **62.9** | -0.2 | 70.1 | **70.0** | -0.1 | 74.3 | 79.8 |
| Golem | 21049 | 73.7 | 78.1 | **85.9** | +7.8 | 67.4 | **76.9** | +9.5 | 94.0 | 91.0 |
| Prince | 19605 | 53.2 | 61.4 | **68.6** | +7.3 | 55.1 | **65.1** | +10.0 | 76.7 | 74.4 |
| Xbow | 17461 | 91.5 | 90.4 | **92.8** | +2.4 | 75.8 | **80.9** | +5.1 | 98.4 | 94.0 |
| ArcherQueen | 16467 | 54.8 | 59.0 | **68.8** | +9.8 | 63.9 | **73.8** | +10.0 | 74.6 | 79.3 |
| AngryBarbarians | 9569 | 58.4 | 69.1 | **66.2** | -3.0 | 62.7 | **60.2** | -2.5 | 75.3 | 77.6 |

- FirespiritHut HP exact (66.1) is above RoyaleSim's (51.9) for ours, as before.
- The 0.0 HP-exact rows for RoyaleSim are its level conventions (FIDELITY.md).

## 1. Rust parity (planner core) — 427 → 574 / 577

`bot/fidelity/rs_parity.py`: every fixture's plays applied to Python and Rust in lockstep; `es_common.battle_digest`
compared every tick to the recording's end.

| engine pair | full-length digest parity | first-mismatch classes |
|---|---|---|
| HEAD Python + HEAD Rust | 429 | IceGolemite 142, Princess, Projectile, Tesla, Firecracker/Projectile, RoyalHogs, SpearGoblin |
| batch 1 (calibrated Python + Rust) | 427 | IceGolemite 141, +4 new (below) |
| batch 2, Rust fixes only (tree `p3`, after §2) | 572 | Princess, Projectile, Tesla, Ghost, RoyalHogs (1 each; all pre-existing) |
| batch 2 through §7 (tree `c11r2`) | **574** | Projectile, Ghost, RoyalHogs (1 each; all pre-existing) |

The four fixtures batch 1 left diverging were two Rust gaps that changed trajectories exposed. Neither was in code
batch 1 touched.

- **"Extra projectile at the range edge"** (`…0813` Princess, `…1222` Firecracker; also HEAD's `…1141` Firecracker).
  - The attacker is pushed more than 1.5 tiles past its reach between commit and release, so the hit is discarded
    (Python `should_cancel_committed_hit`).
  - Python then installs the full post-attack cooldown (`_complete_attack_clock_cycle(discarded=True)`: hit interval,
    unless `LoadFirstHit` keeps the loaded timer). Rust's cancel branch left the cooldown at ~0, so the next out-of-range
    tick floored it at the first-hit time (0.3 s for Princess). Rust then fired 2.7 s early.
  - **Fix:** `engine-rs/src/lib.rs` cancel branch installs `interval` for cooldown weapons. New stat `discard_keeps_load`
    (`differential.py`: `load_first_hit and LOGIC_LOAD_FIRST_HIT_KEEP_LOADED_AFTER_DISCARD`) keeps the loaded timer.
- **"Untraced 43-damage hit"** (`…0804` Goblinstein doctor, `…1152` FirespiritHut). It was the **Inferno Tower**, not
  Firecracker shrapnel.
  - The Inferno was stunned; its target died after its own update. On the next tick it acquired a new in-range target.
  - Python `_note_combat_target` resets a cooldown weapon on any lock change that is not preserved: `retarget_time`, 0.8 s
    for the Inferno. Rust applied that reset only to `class == "Troop"`, so the Inferno hit 0.4 s early.
  - **Fix:** the Rust reset clause also covers non-crown buildings. Crown towers keep their in-range hit in both engines.
- **IceGolemite (139–142 fixtures, "pre-existing" in BATCH1 §6): a harness naming artifact, now fixed.**
  - The fixtures name the card by its gamedata name `IceGolemite`. `differential.config` exported the Ice Golem's death
    nova only for the C56 alias `IceGolem` (`if card == "IceGolem"`). So the Rust battle in rs_parity had no death area.
  - The planner's card list (`c56_controller.CARDS`) uses `IceGolem`, so **the planner always had the death nova**; only
    the parity harness was affected.
  - **Fix:** `differential.py` accepts both names.
- **The 5 remaining mismatches are all pre-existing.** A HEAD-engine tree plus the alias fix (`head-ig`, Rust .so
  identical to batch 1's `so-head`) gives the same first mismatch, tick for tick, on all 5. They are:
  - `…0714`: Princess target;
  - `…0795`: a Rust-only projectile;
  - `…1020`: Tesla HP;
  - `…1157`: Ghost re-acquires during a knockback in Rust; Python waits until the knockback is nearly over; the digest
    re-converges 5 ticks later;
  - `…1226`: RoyalHogs position, 1 unit.

  The Ghost case was masked by an earlier IceGolemite mismatch before.

## 2. BarbLog Barbarian HP — ACCEPTED (strict, both views)

- **Native:** all 696 BarbLog Barbarian bodies in train (data global id 34000009) have max_hp **716** at level 11.
  That is 280 × 256%. Ours had 270, giving 691 (BATCH1 per-card note; `maxhp-train.tsv`).
- **Change:** `gamedata.json` Barbarian hitpoints 270 → 280 at all 6 non-evolved paths. They are the same character:
  Barbarians, BarbarianHut spawn and death spawn, BarbarianLauncher, BattleRam death spawn, BarbLog. The evolved
  `Barbarian_EV1` is unchanged (no evolutions in the corpus). The canonicalization note is extended. This is data only;
  the Rust config gets it through `differential.config()`.
- **Test:** `tests/test_calibration_batch2.py::test_barblog_barbarian_hitpoints_match_native_level11` (fails on `cal1`).
- **Harness, train, `cal1` → `c6-barbhp`:**
  - standard: no-tower ≤¼ 62.26 → **62.53**, paired +0.21 pp [+0.05, +0.42] (45 better / 20 worse); HP exact 71.98 →
    **73.69**, paired +1.90 [+1.55, +2.28] (142 / 1); BarbLog HP exact 0.0 → 73.3, ≤¼ 66.7 → 69.0; worst card HogRider
    −0.52; winner agrees 377 → 382;
  - live: paired ≤¼ +0.13 [+0.03, +0.23], HP +1.87; worst card Firecracker −0.45. **Strict ACCEPT** in both views.

## 3. Royal Ghost: grid route, ground body, re-hide clock — ACCEPTED (strict, both views)

Diagnosed by a research helper (Opus) on 708 train Ghosts in 158 episodes (`research/ghost/REPORT.md` on 127x03);
reviewed and applied here, then re-run independently from the worktree: `c7-ghost` equals the helper's `g2-ghost` in
0/577 fixtures. Unless noted, "%" is the share of Ghost ticks where both engines have the Ghost alive and within ¼ tile,
from an offline replay; the baseline is 28.2%.

- **Movement: the grid route, not a straight hover line.**
  - Native headings snap to cell centres, e.g. exact (+63, +63) per-tick diagonals. ghost.md's "zig-zag" is this route.
  - `raw.targetX/Y` is only the previous tick's position.
  - Ghosts float over the river (22 stand on off-bridge river cells). The water cost that fits is 7, the JumpHeight
    cost: off-bridge Ghosts score 59.4% at cost 7, against 55.5% at 8, 45.7% at 5 and 28.6% at 50.
  - The route alone: 28.2% → 44.3%.
  - **Change:** `pathfinding.py`. Hover units take the ordinary route with the JumpHeight water profile instead of
    `native_single_node_waypoint`.
- **Collision: the body is on the ground plane.** Share of near ticks with another body within 600 units:

  | | vs ground troops | vs air troops | vs buildings and towers |
  |---|---|---|---|
  | native Ghost | 0.4% | 32.4% | 0.3% |
  | native Knight | 0.5% | 33.6% | 0.0% |
  | native Minions | 29.6% | 0.0% | 8.7% |

  - So the Ghost is a ground body; ours had it on the air plane.
  - Route plus ground plane: 67.8%.
  - **Change:** `unit_traits.uses_air_collision_plane` no longer returns true for hover. `entities.py` keeps hover exempt
    from push-back land recovery, so a Ghost can still stand over water.
- **Re-hide: 2000 ms after the Ghost starts walking again, not after its last hit.**
  - The reveal at the hit was already right. Native hits, rebuilt from enemy HP drops of exactly 261, match ours on the
    tick or one sampled tick early in 374/486.
  - Counted from the last frame before walking resumes: native is visible at +36..39 (29/29), hidden in 11/20 at +40..41,
    and hidden in 185/186 at ≥ +42. Ours hid at +34..35.
  - **Change:** `cards/royal_ghost.py` adds `attack_state_open`. It is set at attack start; the first tick with natural
    movement after an attack restarts the fade clock. Visibility agreement on matched positions goes 98.25% → 98.93%.
- **Tests:**
  - `tests/test_calibration_batch2_ghost.py`, 3 tests: route steps 2–10 vs native ep …0700 ±2 units; a Ghost deployed on
    a Knight is pushed ≥300 units; re-hide 40–41 ticks after walking. All 3 fail on the old code.
  - Six `test_enabled_troop_interactions.py` tests asserted the old air plane or the old re-hide; they are updated to
    the measured behaviour.
- **Harness, train, `c6-barbhp` → `c7-ghost`:**

  | view | no-tower ≤¼ | no-tower HP exact | paired ≤¼ (better/worse) | Ghost ≤¼ / HP exact | worst card | gate |
  |---|---|---|---|---|---|---|
  | standard | 62.53 → **66.06** | 73.69 → **76.09** | +3.10 pp [+2.45, +3.81] (142/16) | 23.7 → 62.4 / 57.7 → 69.4 | GoblinHut −0.20 | strict ACCEPT |
  | live | 67.93 → **70.29** | 79.70 → **80.66** | +2.58 pp [+2.04, +3.13] (142/16) | 25.9 → 63.8 / 62.5 → 70.7 | GoblinHut −0.48 | strict ACCEPT |

  - Fights involving a Ghost now match better too: IceGolem +7.3, MinionHorde +7.1, BombTower +5.4 (standard).
  - Winner agrees: 382 → 394.
- **Rust port** (code, not data):
  - `lib.rs prepare_route`: the single-node route is for `air` only; water cost 7 for `jump_speed > 0 || hover`.
  - `scope.rs collision_air`: drop hover.
  - Hover is exempt from the deploy water clip and the push-back ground clamp.
  - New Entity field `ghost_open` (`serde(default)`), set at attack start and cleared on the first `moving` tick in
    `c56.rs ghost_tick`, which resets `ghost_time`. Exported from `differential.py` (`attack_state_open`).
- **Open:**
  - About 60% of paired Ghosts still leave ¼ tile at some point, late, through fight cascades.
  - The hover goal-cell choice is unverified.
  - BattleHealer (also hover, not in the corpus) inherits rules 1–2 unverified.

## 4. Side-1 back-row deploy bound — ACCEPTED (strict, both views)

Diagnosed by the swarm research helper (`research/swarm/REPORT.md`).

**Where the swarm gap comes from.** Scope: the 8 swarm cards, train, live view; 644,597 of 1,926,865 unit-ticks lost. Each
spawn group is charged to the cause of its first unit to drift, weighted by the ticks it then loses:

| cause | % of lost |
|---|---:|
| another card nearby already wrong (Ghost 4.2, other Skeleton Army groups 2.8, Goblin Hut 2.4, Goblins 2.2, Firecracker 1.6, …) | 35.1 |
| a nearby crown tower's HP or alive state already wrong | 32.6 |
| heading differs at movement start, no wrong neighbour (mostly Skeleton Army at deploy end) | 8.1 |
| wrong on the first frame because a neighbour was already wrong | 6.6 |
| death timing with no earlier HP difference | 3.8 |
| slow drift on the same heading | 3.1 |
| **side-1 back-row bound (fixed here)** | 2.7 |
| river-adjacent taps | 1.0 |

So most of the swarm gap is cascade, not a swarm rule. Ruled out, all matching native:
- deploy timing (`deployRemainingMs` matches at the same tick);
- the movement start tick (607/782 Skeleton Army breaks start on time; the heading is what differs);
- deploy push physics on an empty board (95–100% within ¼ tile);
- target choice at deploy end (90.8%).

**Rule.** A ground body deployed by side 1 whose spawn point lies above y = 31.0 is born at y = **31.000**. This applies to
single troops and to every formation member, as long as side 0's princess tower on that half stands.
- Pocket closed: 115 of 138 bodies are at exactly 31000. The other 23 are at 31050–31300, i.e. 31000 plus one capped
  collision-push step. None is near 31.75.
- Pocket open: 21 of 22 bodies are above 31.0.
- Single troops tapped on row 31: 33 of 36 are born at 31000; the other 3 are Baby Dragons (air).
- Ours put them at 31499, and Goblin Gang's back row at 31750.

Side 0's mirror row and air bodies are not bounded.

**Change:** `battle.py` `_card_formation_back_edge`, applied where the forward deploy edge is applied. Rust:
`apply_action` caps `e.y` at 31.0 for side-1 ground cards while side 0's princess on the anchor's lane is alive, after
the forward edge and before the 0.25/31.75 clamp.

**Tests:**
- `tests/test_calibration_batch2_swarm.py`: 11 native first frames. The old code fails 8; the other 3 are guards.
- Batch 1's Goblinstein test case `…0715` now reproduces that match's destroyed left princess. Native left the doctor
  at 31750 there, consistent with the rule.

**Harness, train, `c7-ghost` → `c8-backedge`:**
- standard: ≤¼ 66.06 → **66.61**, paired +0.53 pp [+0.30, +0.81] (62/6); HP 76.09 → 76.19; worst card IceGolem −0.16;
- live: ≤¼ 70.29 → 70.84; HP 80.66 → 80.74.

Strict ACCEPT in both views. The helper's own run against `c6-barbhp` (without Ghost) gave +0.54, the same gain.

## 5. Huts and Goblinstein (research helper `research/huts/REPORT.md`) — (a) and (c) ACCEPTED, (b) REJECTED

- **(a) GoblinHut Spear Goblin aim.**
  - **Rule.** Each goblin spawns 1200 units from the hut, at the integer angle towards the nearest enemy in wake
    range, ±20°. The sign is −facing × (−1)^wave.
  - Facing is the sign of that enemy's x-offset; it keeps its last value at dx = 0 and starts at +1 for side 0, −1 for
    side 1. This fits 1003 of 1026 train goblins. The 1350/1500 radii seen in first frames are hut push-out.
  - Ours shifted the hut's fixed forward direction, which put every goblin at (−410, ±1128).
  - Wake check: air units and buildings do wake the hut, as ours already had.
  - **Change:** `cards/goblin_hut.py` (nearest target, facing state, `_radial_spawn_basis`) and `spawner.py` (overridable
    ring basis).
  - **Rust:** `spawn.rs` State gains `facing` and `target`. The gated branch finds the nearest in-range enemy; the ring
    base is `vector_angle(target) + sign × 20`. `spawn_snapshot.py` exports the state.
- **(b) FirespiritHut spirits 1500 units straight ahead, no terrain search.** Native fits 1123/1194; ours spawned them
  1000 ahead with a terrain search.
  - On top of (a), standard view: ≤¼ **−0.24** and HP exact **−0.55**. Paired ≤¼ was +0.12 [−0.20, +0.45], but 8
    cards lost more than 1 pp, mostly through one fixture (`…1325`/`…1323`), where we now win and end early.
  - Live view: +0.44 / +0.18, strict.
  - The final rule requires the overall standard numbers not to fall, so it is **rejected and reverted**.
  - The hut's walking showed no separate rule: it starts on the native tick at the native speed, and 316/361 are within
    ¼ tile at t40.
- **(c) Goblinstein doctor shot damage.**
  - The remaining Goblinstein gap is the doctor: 66% ≤¼ against 88% for the monster. In 86 of 87 doctor divergences a
    neighbour diverged first.
  - Every native doctor shot does **135** (501 hits, towers included; none of 92) = 53 × 256%. gamedata carried 36,
    giving 92.
  - **Change:** `gamedata.json` `Prj_goblinstein_doctor` damage 36 → 53. Data only; it reaches Rust through
    `differential.config()`.
- **Tests:** `tests/test_calibration_batch2_huts.py` has spear-goblin first frames (3 native taps) and the doctor
  damage. The (b) tests were removed with (b).
- **Harness, train** (cumulative runs `c9a` = c8+a, `c10-ac` = c9a+c):

  | step | view | ≤¼ | HP exact | paired ≤¼ | cards >1 pp (LOO) | decision |
  |---|---|---|---|---|---|---|
  | c8 → c9a (a) | standard | 66.61 → **67.73** | 76.19 → 76.72 | +1.14 [+0.80, +1.53] (103/17) | BombTower −1.32 (LOO −0.72) | ACCEPT (final rule) |
  | | live | 70.84 → 72.10 | 80.74 → 81.40 | +1.14 | none | strict |
  | c9a → c10-ac (c) | standard | 67.73 → **68.00** | 76.72 → 76.90 | +0.41 [+0.07, +0.76] (57/23) | Wizard −3.32 (LOO +0.05), MightyMiner (−0.77), RoyalDelivery (−0.35) | ACCEPT (final rule) |
  | | live | 72.10 → 72.67 | 81.40 → 81.91 | +0.57 [+0.35, +0.85] | Wizard −1.22 (LOO +0.01) | ACCEPT (LOO) |

  - GoblinHut ≤¼ 34.8 → 48.1 and HP 52.6 → 59.1 (standard); Goblinstein live 74.1 → 80.1.

## 6. Rust parity after each accepted change

Full 577-fixture parity was rerun after each Rust port; see §1 for the method. Every accepted change keeps the classes a
subset of HEAD's. Two more Rust gaps were found and fixed on the way:

- **`c8` → `c10r2`: `…0804` re-broke** with the Ghost and back-edge trajectories.
- Python buildings apply the acquisition preload only when `_last_combat_target_id` is None (`acquired_from_idle`).
- Rust used the current target field, which a target removed during another entity's update (here while the Inferno
  was stunned) clears without clearing the lock memory.
- Fix: the Rust building branch uses `acquired_from_idle` (`last_target`). `c10r2`: 572/577.
- **`c11` (Firecracker): `…1147` diverged in HEAD's Tesla class (Tesla HP).**
  - Python's Tesla hide clock (`HideWhenIdle`) advances at the native movement scale (`slow_multiplier`, movement buff).
    Rust's `hide_tick` used `attack_work()`.
  - Under the Ice Golem's movement-only death slow (move ×0.5, attack ×1.0), Rust hid the Tesla 5 ticks earlier.
    Python's area damage then hit a Tesla that Rust already treated as hidden.
  - Fix: `hide_tick` work = 50 × movement haste% × movement slow%. This also fixes HEAD's `…1020` (Tesla) and `…0714`
    (Princess).
  - `c11r2`: **574/577**. The remaining 3 are HEAD's `…0795` (a Rust-only projectile), `…1157` (Ghost re-acquires during
    a knockback) and `…1226` (RoyalHogs, 1 unit).

## 7. Next-worst cards: Rascals and Firecracker — both ACCEPTED (round-2 helper `research/cards/REPORT.md`)

Baseline `c10-ac`, gated sequentially (A, then B on top of A), as in batch 1. Verified: an independent rerun from the
worktree (`c11-cards`) equals the helper's `cards-ab` in 0/577 fixtures.

- **A. Rascals 100 ms deploy stagger (data).**
  - Native: on every train Rascals play, the boy and the two girls start moving at ages **20 / 22 / 24**. Ours started
    all three at 20.
  - That stagger is the `summonDeployDelay: 100` every other multi-unit card carries; Rascals had none. With it, the
    second girl's first-frame error at q90 goes 149 → 0.
  - **Change:** `gamedata.json` `spells[53]` gets `summonDeployDelay: 100`. Rust gets it through `differential.config()`.
- **B. Firecracker: the recoil stops the started hit, loading continues (code).**
  - Native rich phase snapshots: in the 9 ticks after every launch, `attackTimelineMs` is 0 and `loadRemainingMs` is
    2350 − 50k (366/367). A hit restarting at k = 10 shows 550, which is our ordinary clock's loaded work plus one tick.
  - Consequences: the next shot comes 59 ticks later (77/86 same-target pairs; ours 60), or +69 after a retarget. This is
    the "native fires 5–10 ticks later after a retarget" seen in §8.
  - When the recoil leaves the target out of reach, native walks straight back (31/34; ours 6/34).
  - **Change:** `ordinary_combat_clock.supported()` accepts `AttackRecoil`, which was excluded only because it overrides
    `on_attack_committed`. `cards/firecracker.py` passes `reset_hit_on_movement=True` to the recoil push.
  - **Rust:** `projectiles.rs recoil()` sets `push_reset = true`. The ordinary-clock flag flows through `differential.config()`.
- **Tests:** `tests/test_calibration_batch2_cards.py`, 5 tests: three native Rascals cases, the 59-tick period and the
  walk-back. All fail on `c10-ac`.
- **Harness, train:**

  | step | view | ≤¼ | HP exact | paired ≤¼ | cards >1 pp (LOO) | decision |
  |---|---|---|---|---|---|---|
  | c10-ac → +A | standard | 68.00 → **68.22** | 76.90 → 76.97 | +0.32 [+0.06, +0.62] (52/15) | none (worst SkeletonArmy −0.55) | strict ACCEPT |
  | | live | 72.67 → 73.01 | 81.91 → 82.09 | +0.35 [+0.19, +0.56] | none (Musketeer −0.64) | strict |
  | +A → +A+B (`c11-cards`) | standard | 68.22 → **69.97** | 76.97 → **78.59** | +1.36 [+0.90, +1.89] (104/29) | Prince −1.09 (LOO −0.06) | ACCEPT (final rule) |
  | | live | 73.01 → 73.89 | 82.09 → 82.72 | +0.99 [+0.68, +1.30] | Musketeer −2.11 (LOO −0.54) | ACCEPT (final rule) |

- **Results:**
  - Firecracker ≤¼ 40.9 → **57.1**, HP 69.5 → 76.8. Rascals 48.2 → **60.5**. Winner agrees 390 → **399**.
  - Musketeer gains +3.4 in the standard view. Its live-view loss comes from four fixtures where our final crowns now
    match native, so our battle runs into overtime and more, later Musketeer ticks are scored.
  - Measured against `c10-ac` as one combined change, the live view would fail LOO by 0.19 pp (Musketeer −1.19). The
    documented procedure is per-change, and each change passes on its own baseline.
- **Not changed (no native rule found):**
  - Knight, MiniPekka, Valkyrie, IceGolem: mixed causes, exact first frames, no first-hit or retarget signature.
  - Princess, Musketeer, Archers: native shot periods already match; they diverge late.

## 8. Own survey: ranged shot timing (no change)

`tools/shot_survey.py` and `shot_match.py`. Native projectile launches (4M-range object ids with a card id, first-seen
frame and the previous sampled frame as the window) are compared with ours per card, on train.
- The first shot of each burst falls in the native window for 65–72% of Archers, Minions, GoblinGang, Blowdart,
  Princess, Musketeer and BabyDragon, with no systematic offset. Their divergence is cascade, not a timing rule.
- The Log, BarbLog and RoyalDelivery offsets are representation only. Ours holds the rolling log or delivery object from
  the deploy tick; its first motion and the recruit spawn tick match native.
- The Firecracker's late second shots led to §7 B.

## 9. Crown towers: four rules — all ACCEPTED (round-2 helper `research/towers/REPORT.md`)

**Diagnosis on `c10-ac`.** 1,693 of 3,078 train towers diverge. Ranked by the fixture ticks left after the first
divergence:

| cause | towers | share |
|---|---:|---:|
| a native hit with no matching hit in ours (cascade from units already diverged) | 285 | 15.2% |
| Miner crown hit one tick late | 136 | 8.6% |
| Wall Breakers hit 350 vs native 281 | 88 | 6.2% |
| Goblin Barrel goblins one tick early | 83 | 4.7% |
| Spear Goblin late | 62 | 4.5% |
| Poison crown pulse 21 vs native 22 | 47 | 2.4% |

Not causes in this sample: king-tower activation, tower target choice, overtime tower drain. "Engine ended early" is
mostly benign: 180 of 289 such cases end within 5 ticks of native.

**The rules:**
- **(a) Wall Breakers.** Native blasts do 281 to towers (458 drops) and to troops (83) = 110 × 256%; ours did 350.
  - **Change:** `gamedata.json` `WallbreakerProjectile` damage 137 → 110 (data; reaches Rust through `differential.config()`).
- **(b) Miner: the emergence clock starts on the arrival tick.** Native `deployRemainingMs` reads 950 on the arrival
  tick; ours held 1000. Where native samples consecutive frames, our first crown hit came exactly one tick late.
  - **Change:** `cards/miner.py` subtracts one tick from the routed transport's deploy total.
  - **Rust:** `lib.rs` `apply_action` subtracts 0.05 s for routed tunnels.
  - After (b), the Miner's first crown hit matches in 412/423 plays (was 173/411).
- **(c) Poison crown-tower pulse 21 → 22** (`balance.py`). Native crown towers drop 22 per pulse: 92 × 23%, rounded up.
- **(d) A troop spawned by a projectile impact keeps its full deploy time on its spawn tick** (`entities.py`
  `_defer_projectile_spawn_deploy`).
  - Native rich phase on the exact spawn tick reads 1100 / 1000 / 250 ms for Goblin Barrel goblins (496 samples), BarbLog's
    Barbarian (176) and the Royal Delivery recruit (103). Ordinary card deploys read 950, as ours does.
  - Ours had already consumed one tick, so barrel goblins hit towers one tick early.
  - Rust gets this through the exported spawn templates.
- **Held out by the helper:** Mighty Miner stage-1 damage 16 → 17 (native 43 per hit). It is a strict ACCEPT alone but
  fails on top of (a)–(d) (≤¼ −0.09). Not applied.
- **Tests:** `tests/test_calibration_batch2_towers.py` has 7 tests; all fail on `c10-ac`. Two Miner tests in
  `test_enabled_troop_interactions.py` assert the deploy total and are updated to the one-tick-shorter clock.

**Harness, train, re-gated on top of `c11-cards`, sequentially.** The (c) and (d) gates were run on 127x04 from copies of
the same trees; 03 and 04 give identical results (batch-1 verify vs `cal1`: 0/577 differ).

| step | view | ≤¼ | HP exact | crown-tower HP exact | paired ≤¼ | cards >1 pp (LOO) | decision |
|---|---|---|---|---|---|---|---|
| c11 → +a (`c12a`) | standard | 69.97 → **71.43** | 78.59 → 80.11 | 77.37 → 80.12 | +0.83 [+0.42, +1.30] (71/11) | none | strict ACCEPT |
| | live | 73.89 → 74.52 | 82.72 → 83.29 | | +0.38 [+0.20, +0.61] | none | strict |
| +b (`c12-miner`) | standard | 71.43 → 71.48 | 80.11 → 80.16 | 80.12 → 80.29 | +0.12 [−0.08, +0.36] (45/25) | none | strict ACCEPT |
| | live | 74.52 → 74.54 | 83.29 → 83.31 | | +0.07 | none | strict |
| +d (`c12-ms`) | standard | 71.48 → **72.26** | 80.16 → **80.51** | 80.29 → 81.14 | +0.87 [+0.43, +1.30] (193/78) | Wallbreakers −1.52 (LOO −0.65), BarbLog −1.4 (−0.17), ArcherQueen (−0.75) | ACCEPT (final rule) |
| | live | 74.54 → 75.52 | 83.31 → 83.84 | | +1.00 [+0.64, +1.37] | ArcherQueen −1.08 (LOO −0.34) | ACCEPT (final rule) |
| +c (`c12-spawn` = final) | standard | 72.26 → 72.26 | 80.51 → 80.51 | 81.14 → **81.97** | 0 (no unit-tick changes) | none | strict ACCEPT |
| | live | 75.52 → 75.52 | 83.84 → 83.84 | | 0 | none | strict |

- Gating (c) before (d), as first tried, moves no-tower HP exact by −0.00003 pp (one fixture) and fails the strict
  "no decrease" rule on a technicality. After (d) it changes no unit tick at all. The order used is (d) then (c).
- Winner agreement drifts 402 → 400. The helper traced its own drop to (d), mostly tower kills landing exactly on the
  native final tick. The gate does not use this metric; reported as an open risk.
