# Merge test fixes for calibration batches 1+2 (`bot/calib-testfix`)

The coordinator approved merging `bot/calib-batch2` (c7be66486) into main if the full suite passes on the merged tree.
The 127x03 run (`bot-merge-test`, merge onto 3106c5ab) found 7 failures that the baseline doesn't have. This branch
resolves all 7. **No engine code changed**: `src/clasher`, `engine-rs/src`, `gamedata.json` and `engine-rs/differential.py`
are byte-identical to c7be66486. Only tests changed. The branch also adds `BATCH2.md` and `R2-AB.md`, which c7be66486
cites but did not contain; they are the versions committed on local `bot/lead`.

## Verdicts

| failure | class | change |
|---|---|---|
| `test_stat_scaling::test_current_balance_layer_updates_enabled_base_cards` | (a) refuted value | Wall Breakers damage 350 → 281 |
| `test_torch_simple_periodic_areas::test_poison_uses_serialized_periodic_cadence_and_tower_scale[cpu]` | (a) refuted value | Poison crown pulse 21 → 22 |
| `test_spell_levels::test_unreconciled_tournament_overrides_are_explicit[Poison]` | (a) consequence of the Poison fix | Poison moved to a new "reconciled" test |
| `test_stage4_b2::…test_pending_retarget_uses_prior_completed_attack_latch` | (a) clock class changed | two modes, see below |
| `test_stage4_b2::…test_special_weapon_retarget_in_reach_restores_retarget_delay` | (a) clock class changed | two modes |
| `test_stage4_b2::…test_depleted_target_competes_with_visible_alternatives` | (a) clock class changed | two modes |
| `test_stage4_b2::…test_finish_expiry_clears_special_weapon_target_memory` | (a) clock class changed | two modes |

None of the 7 is an unintended regression.

## Python tests

- **Wall Breakers 281** (BATCH2 §9a). Native blasts do 281 = 110 × 256% to towers (458 drops) and troops (83). Batch 2
  changed `WallbreakerProjectile` damage 137 → 110 in `gamedata.json`. The test still asserted the old 350.
- **Poison crown pulse 22** (BATCH2 §9c). Native crown towers drop 22 per pulse, i.e. 92 × 23% rounded up. Batch 2 changed
  `TOURNAMENT_SPELL_OVERRIDES["Poison"]` 21 → 22. The torch runtime reads the same override and gives 1978, which is what the
  test now expects.
- **Poison is now reconciled.** `create_spell_from_json(level≠11)` raises "needs a reconciled crown damage override" only
  when the level-11 override differs from `native_percent_damage(damage, multiplier)`. 21 differed and 22 matches. Poison
  therefore leaves the unreconciled list, which still holds Earthquake and Tornado. A new test,
  `test_poison_crown_override_is_reconciled_with_native_ceiling`, pins level 11 = (92, 22) and level 12 = (101, 24).

## The 4 Rust B2 reductions

**Cause.** All four use Firecracker as their special-weapon vehicle: windup, retarget delay, finish expiry and
completed-attack latch. BATCH2 §7B moved Firecracker onto the **ordinary** clock (`ordinary_combat_clock.supported`
accepts `AttackRecoil`), following native rich snapshots. The Rust branches these tests guard did not change, and they
still serve Princess, Valkyrie, ElectroSpirit, Ghost, Inferno, Mighty Miner and Wall Breakers.

**Evidence that this is not a regression** (127x03, merged engine):
1. **Special-weapon branches intact.** With Firecracker pinned to its pre-batch-2 classification (`supported` patched for
   `AttackRecoil` holders; `differential.entity` exports `ordinary` through the same function), all 4 original tests pass
   unchanged on the batch-2 Python and Rust. This includes the batch-2 recoil `push_reset` and the discarded-hit,
   building-retarget and Tesla-hide fixes.
2. **The ordinary path is in parity.** The tick-1 mismatches come from the tests writing legacy fields
   (`attack_cooldown`, `_attack_windup_active`, …) into an entity whose ordinary clock does not exist yet. Python seeds that
   clock lazily, at its first `get_clock` call, which here comes after the retarget code has already run on the legacy
   branch. Rust seeds it at import (`clock_initialized=False`).
   - Seeding the clock before export, as a live battle's first update would, makes every scenario match Python↔Rust on
     each tick.
   - This lazy-seed order affects any ordinary card injected this way (Musketeer, Archers, …), so it is not a batch-2
     effect. Live import (`live_snapshot.live_entity`) seeds Rust with the same formula as `seed_remaining`.
3. **Natural games.** `rs_parity` over all 577 native fixtures stays at 574/577 (below). The 3 mismatches are the ones
   batch 2 already listed as dating from HEAD.
4. **Finish expiry.** With no state injection at all, the digests match for all 45 ticks. Only the special-weapon
   expectation `_last_combat_target_id is None` fails, because the ordinary clock has no special finish expiry. Both
   engines keep the same lock memory.

**Change** (`engine-rs/test_stage4_b2.py`). Each of the 4 tests runs two subtests:
- `special`: Firecracker is pinned to the special-weapon clock (`special_weapon_firecracker()`) and the original
  assertions run unchanged.
- `ordinary`: the batch-2 clock, seeded before export. These subtests check the digest and RNG every tick, cooldown parity
  for the latch test, and Rust `last_target` equal to Python's for the finish-expiry test.

## Verification

Each run used an isolated copy (`git archive`) on 127x03 or 127x04, with its own native build.

- **Fidelity** (127x04 `bot-calibfix-fid`, branch 7f36df329, engine `clasher`, `--issue-offset -1`): 577/577 ok. Baseline is
  `bot-calib2-r1/runs/c12-spawn` (`compare_runs`).

  | split | view | no-tower ≤¼ | paired ≤¼ (better/worse) |
  |---|---|---|---|
  | train | standard | 72.26 → 72.26; HP exact 80.51 → 80.51 | +0.00 (0/0) |
  | train | live | 75.52 → 75.52 | +0.00 (0/0) |
  | validation | standard | 74.48 → 74.48 | +0.00 (0/0) |
  | validation | live | 77.93 → 77.93 | +0.00 (0/0) |
  | all | standard | 72.48 → 72.48 | +0.00 (0/0) |
  | all | live | 75.76 → 75.76 | +0.00 (0/0) |

  Crown-tower HP exact (train) is 81.97 → 81.97, and winner agreement 400 → 400.
- **Python↔Rust parity** (`bot.fidelity.rs_parity`, train + validation): **574/577**. The remaining mismatches are
  `…0795`, `…1157` and `…1226`, the same three as batch 2's `parity-c12r` (all from HEAD).
- **Targeted tests** (127x03): all 4 B2 tests pass, 24 subtests in both modes. The 2 B2 failures that remain
  (`air_knockback…`, `stun_resets…`) are in the baseline list too: they need `engine-speed/stage4` artifacts that are
  not in the tree.
- **Full suite on the merged tree** (127x03 `bot-calibfix-test`).
  - Setup: a scratch merge (not pushed) of this branch onto origin/main 3d2b8ec63; `git archive`; native rebuilt.
    It ran like `bot-merge-test/run2.sh`: tests/ and engine-rs/ with `--continue-on-collection-errors`.
  - **0 new failures vs `base-fails2.txt`**. The FAILED/ERROR list is identical: 369 = 369, with no line added or
    removed.
  - tests/: 241 failed, 100 errors, 5749 passed. The baseline has 241, 100 and 5696; the extra passes are batch 1/2's new
    tests and the new Poison test.
  - engine-rs/: 19 failed, 9 errors (same as the baseline), and 156 subtests passed against 144.
  - origin/main moved from 3106c5ab to 3d2b8ec63 between the two runs. That only changed `bot/value/players.py`, which
    neither suite collects.
