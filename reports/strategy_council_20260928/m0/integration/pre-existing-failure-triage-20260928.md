# Pre-existing test failure triage (September 28, 2026)

Scope: the 53 files in `/tmp/failfiles.txt`, all of which also fail at HEAD `95feeb0e`. Main (dirty tree) had 145 failures at the start of triage. Runs used `OMP_NUM_THREADS=4 .venv/bin/python -B -m pytest`. No simulator or source file was changed. Candidate source fixes were only tried in a throwaway copy at `/tmp/probe`.

Final state of the failing-file set on main: **138 failed, 1115 passed, 63 skipped** (was 145 / 1108 / 63).

## Pilot path, checked by import and call tracing

`council_pilot` launches `train_recurrent` with `public-contract-version 4`, `simulation-backend python`, `actor-observation-domain simulator-exact`, `opponent-mode strategy` and `elixir-leak-penalty-scale 0`. With contract v4, `SelfPlayBattleEnv.get_action_mask` always returns `PublicActionMaskBuilder.build(...)`. `StrategyBot` and `council_opponents` both call `env.get_action_mask`. `train_recurrent` passes `pre_action_masks` into `env.step`, so `DiscreteTileActionSpace.legal_action_mask` is not on the actor or opponent path. Actions still execute through `battle.deploy_card`.

After importing `council_pilot`, `train_recurrent`, `selfplay_env`, `public_action_mask`, `structured_obs`, `council_opponents`, `public_scripted_opponent`, `council_warmstart` and `council_evaluation`, none of these modules are loaded: `clasher.torch_sim.*`, `simple_pytorch_backend`, hog26 scripts, TV-Royale tooling, rage or inferno. `oracle_planner` is imported through `imitation.py`, but the pilot never builds it because the oracle arm is deferred.

## Counts

| Category | Count |
|---|---:|
| (a) Stale test, evidence-backed behavior change (fixed) | 7 |
| (b) Environment/tooling only | 59 |
| (c) Legacy or outside the pilot scope | 77 |
| (d) Real regression that can reach the pilot path | 2 |
| **Total** | **145** |

## (d) Real regression on the pilot path

### `tests/test_match_rules.py::test_short_stun_during_king_activation_does_not_change_first_shot_time` and `::test_freeze_does_not_add_a_new_windup_after_king_activation`

Root cause: `Entity.apply_stun` (`src/clasher/entities.py`, around line 1010) now sets `pause_crown = _crown_tower_slot is not None`, so every stun on a Crown Tower sets `_freeze_target_pause_remaining`. `Building._update_active_combat` returns early while that pause is positive, *before* the King's one-time activation clocks (`activation_delay_remaining` 3.3 s, then `activation_first_hit_delay_remaining` 0.7 s) are advanced. As a result, stunning a King Tower during wake-up delays its first shot by the full stun duration. The same function's own comment says native activation is not paused ("a King Tower completes its wake-up while Frozen"). This was introduced in `b86e434a`.

Evidence status: the pause itself is native-backed for an *in-progress Princess/Crown attack* (`tests/fixtures/native_late_fidelity_boundaries_15_535_86.json`, case `crown_zap_preserves_in_progress_attack`; disabling `pause_crown` breaks it at tick 1699). No native fixture covers the King activation window, so the two claims conflict only there.

Pilot repro (pilot cards only, full `battle.step()`): `/tmp/king_zap_repro.py`. A red Knight stands in King range, then red plays Fireball or Zap on the dormant blue King Tower.

```
main:          Fireball activation tick 44 -> first King attack 124 (80 ticks)
               Zap      activation tick 1  -> first King attack 91  (90 ticks, +0.5 s)
candidate fix: Zap      activation tick 1  -> first King attack 81  (80 ticks)
```

Proposed fix: in `Building._update_active_combat`, when `_freeze_target_pause_remaining > 0` and the tower is active with activation work remaining, advance `activation_delay_remaining` and `activation_first_hit_delay_remaining` exactly as in the unpaused branch. On completion, set `attack_cooldown = 0` and `_attack_preload_blocked = False`, then return without targeting or firing. Ordinary attacks keep the native Zap/Freeze pause.

This was checked in `/tmp/probe`: all `tests/test_native_*.py`, `test_match_rules.py`, `test_enabled_spell_interactions.py` and `test_enabled_troop_interactions.py` pass (exit 0), including the crown-zap native case and both King tests.

Pilot impact: reachable through Zap, and through Ice Spirit freeze, on a waking King Tower. The magnitude is small, at most the stun duration once per King activation. Confidence that it reaches the pilot: high. Confidence that it matters for strength: low. A native probe of Zap on a dormant King would settle it before any source change.

## (a) Stale tests updated (7), each with an evidence comment

- `test_building_footprint.py::test_tesla_uses_2x2_placement_footprint` and `::test_compact_building_footprint_is_data_driven_not_name_driven`: the tests spawned a 2x2 building directly at a tile centre. Even footprints anchor on integer coordinates (`native_building_anchors_15_535_86.json`: Tesla 7500/10500 -> 7000/10000). Both tests now spawn at `building_anchor(...)`. A separate check found fast and slow `is_building_placement_occupied` agree on 3,456 Tesla/Cannon queries.
- `test_rl_action_mask.py::test_fast_troop_occupancy_cache_matches_scalar_and_invalidates`: ground troops now use the native LogicSummoner ring search (`resolve_ground_troop_anchor`; `test_native_spawn_terrain_footprint.py` DarkPrince relocation), so only air cards use the radius cache. The test now uses Minions and BabyDragon. Legacy and fast masks still match.
- `test_rl_action_mask_gather.py::…[0]`, `[1]`: the building gather now resolves `building_anchor` first (native anchor and bank fixtures), and the expected mask does the same.
- `test_rl_typed_vocabulary.py::test_public_mask_accepts_typed_card_action_but_not_body_token`: `PublicActionMaskBuilder` now fails closed when `terminal` is None. Real observations set `terminal=bool(game_over)`, so the test now passes `terminal=False`.
- `test_gamedata_normalization.py::test_special_spell_loaders_follow_payload_shape_after_card_rename`: `SERVER_ACTION_DELAY_SECONDS` is 0.0. The first Graveyard deadline is 2.2 s, as `test_enabled_spell_interactions.py` pins, and `test_native_spell_command_timing.py` passes.

## (b) Environment/tooling only (59)

- **MPS "command buffer exited with error status" (52).** There were 99 such errors in the log. Every failing `[mps]` case whose `[cpu]` twin exists has that twin passing: `hog26_poison_target_local` 4, `torch_simple_cast_rng` 2, `grouped_geometry` 9, `grouped_projectiles` 14, `impulse` 5, `public_mask` 3, `river_jump` 6, `runtime_reset` 2, `targeting` 2, `rl_simple_pytorch_backend` 4, and `torch_simple_standard::test_standard_mps_runtime_matches_cpu_after_deployment` 1. The last two groups are MPS-only or have passing CPU twins; their secondary messages, such as "lacks exact typed body identity" and "not compiled public roots", appear only on MPS.
- **Missing optional artifacts (7):** `current_client_annotation_queue` 1 (dataset), `pretrain_public_cycle_belief` 1, `rl_public_history::test_zero_initialized_public_history_upgrade_preserves_checkpoint_outputs` 1, `set_policy_deterministic_hierarchy` 1, and `train_public_belief_counterfactual` 3. All of these are missing `checkpoints/...pt` files.

## (c) Legacy or outside the pilot scope (77)

- **hog26 legacy tooling (54).** Source-hash and authority pins: `flat_median_quarantine`, `heldout_gameplay_canary`, `phase_balanced` (3); "outcome inference source or runtime authority changed" (5). Scalar receipt suites drifted under the `b86e434a` fidelity changes: spell receipts now birth immediately because server delay is 0 (26); Lumberjack death lifecycle (8); rolling Log and BarbLog on CPU and MPS (4); Wallbreakers (2); RoyalDelivery (3); ArcherQueen (3). The ArcherQueen tests use the off-grid command `(9,5)`, which `is_tower_tile` now rejects. Pilot tile-centre commands such as `(9.5,5.5)` are unaffected.
- **TV-Royale and offline sidecar tooling (8).** The producer now writes public-observation schema 4 and mask contract 5, while TV-Royale readers still require v2. This is a real inconsistency inside that tooling, but no historical corpus is admitted to the pilot.
- **Tensor `torch_simple` CPU (6):** `representative_cards` Fireball (now applies level-11 damage, 688, against a pinned 269), `rolling_runtime` 3, `runtime` source-inspection 1, `standard` tower pin 1.
- **Rage 3 and Inferno 1:** these cards are not in the 16-card pilot set.
- **Oracle planner pins (4):** `rl_oracle_direct_path` 2 and `rl_oracle_planner_exactness` 2. The first decision already differs because the `DiscreteTileActionSpace` mask changed (seed 2301: 1409 -> 1411 legal actions for p0, 911 -> 923 for p1, from building anchors and ground search). The oracle arm is deferred. The pins were not re-pinned because I could not attribute the whole trace difference.
- **`rl_deployment_blocker_guard::test_deployment_blocker_guard_skips_empty_payload_queries` (1).** This is a genuine performance regression, not a correctness one: masks are identical, but with the guard on there are 888 payload queries instead of 0. The fast path now sends ground troops through the unguarded `_is_legal_deploy`, and `resolve_ground_troop_anchor` queries payload occupancy for each candidate. It is off the pilot path because v4 uses `PublicActionMaskBuilder`. Proposed fix: pass the guard's `deployment_blockers` snapshot into `_is_legal_deploy` and `resolve_ground_troop_anchor`, and skip payload queries when the snapshot is empty.

## Appendix: King activation repro (`/tmp/king_zap_repro.py`)

```python
# Pilot-card repro: red Zap on the dormant blue King Tower, with a red Knight in king range.
import sys
from collections import deque
from clasher.battle import BattleState
from clasher.arena import Position
from clasher.entities import Building, Troop, Projectile
def run(card):
    b = BattleState()
    king = next(e for e in b.entities.values() if isinstance(e, Building) and e.player_id == 0 and getattr(e, "_is_king_tower", False))
    ks = b.card_loader.get_card("Knight")
    b._spawn_troop(Position(9.0, 7.0), 1, ks)
    kn = max((e for e in b.entities.values() if isinstance(e, Troop)), key=lambda e: e.id)
    kn.deploy_delay_remaining = 0.0; kn.placement_pending = False; kn.on_spawn(); kn.speed = 0.0
    p = b.players[1]; p.hand = [card]; p.deck = [card]; p.cycle_queue = deque(); p.elixir = 10
    assert b.deploy_card(1, card, Position(king.position.x, king.position.y))
    act = None
    for _ in range(400):
        b.step()
        if act is None and getattr(king, "_tower_active", False): act = b.tick
        if any(isinstance(e, Projectile) and e.player_id == 0 and getattr(e, "source_id", None) == king.id for e in b.entities.values()) or getattr(king, "_has_attacked_once", False):
            return act, b.tick
    return act, None
for card in ("Fireball", "Zap"):
    print(card, "activation tick, first king attack tick =", run(card))
```
