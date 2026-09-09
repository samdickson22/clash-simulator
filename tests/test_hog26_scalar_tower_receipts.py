from __future__ import annotations

import hashlib
import json
import random

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.entities import Projectile, Troop
from clasher.rl.simple_pytorch_backend import load_current_client_typed_vocabulary
from clasher.torch_sim.diagnostics import battle_snapshot
from scripts.hog26_scalar_public_effect_adapter import project_scalar_public_effects
from scripts.hog26_scalar_tower_receipts import ScalarTowerReceiptSetup


def _setup(visible=None):
    loader = CardDataLoader()
    vocabulary = load_current_client_typed_vocabulary()
    battle = BattleState(rng=random.Random(1279031))
    towers = tuple(battle.entities.values())
    setup = ScalarTowerReceiptSetup.compile(
        battle,
        towers,
        loader,
        vocabulary,
        source_visible_to=visible or (lambda source, seat: source.is_visible_to(seat)),
    )
    return battle, towers, setup, loader, vocabulary


def _hash(battle):
    snapshot = battle_snapshot(battle)
    snapshot["projectiles"] = [
        (
            p.id,
            p.target_position.x,
            p.target_position.y,
            p.travel_speed,
            p.splash_radius,
            p.launch_delay,
            p.tracks_target,
            p.source_entity.id if p.source_entity else None,
            p.primary_target.id if p.primary_target else None,
            p.source_name,
        )
        for p in battle.entities.values()
        if isinstance(p, Projectile)
    ]
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


def _populate_targets(battle, towers, loader):
    targets = []
    for tower in towers:
        target = battle._spawn_entity(
            Troop,
            Position(
                tower.position.x, tower.position.y + (1 if tower.player_id == 0 else -1)
            ),
            1 - tower.player_id,
            loader.get_card("Knight"),
        )
        target.deploy_delay_remaining = 0
        target.placement_pending = False
        targets.append(target)
        if tower.card_stats.name == "KingTower":
            tower.activate()
    return targets


def test_sidecar_extends_only_outcome_vocabulary_and_binds_all_six_sources():
    battle, towers, setup, loader, vocabulary = _setup()
    before_names, before_sha = vocabulary.token_names, vocabulary.sha256
    targets = _populate_targets(battle, towers, loader)
    with setup.recorder() as recorder:
        for tower, target in zip(towers, targets, strict=True):
            tower._create_projectile(target, battle)
        assert [r.source_id for r in recorder.receipts] == [t.id for t in towers]
        assert [r.appearance.token for r in recorder.receipts] == [
            494,
            494,
            495,
            494,
            494,
            495,
        ]
        ids, _, mask = project_scalar_public_effects(
            [r.appearance.entity for r in recorder.receipts],
            recorder.appearances,
            visible_to=lambda source, seat: source.is_visible_to(seat),
        )
        assert mask.all()
        assert ids[0, 0].tolist() == [494, 494, 495, 494, 494, 495]
        assert ids[0, 1].tolist() == ids[0, 0].tolist()
    assert setup.token_names[:494] == before_names
    assert setup.token_names[494:] == (
        "projectile:TowerPrincessProjectile",
        "public_tower_shot:king",
    )
    assert setup.extra_public_effect_ids == (494, 495)
    assert setup.extra_public_effect_tokens == setup.token_names[494:]
    assert vocabulary.token_names == before_names and vocabulary.sha256 == before_sha
    assert all("_create_projectile" not in t.__dict__ for t in towers)


def test_actual_tower_appearances_map_only_policy_identity_to_unknown():
    from clasher.rl.simple_pytorch_backend import (
        _compile_public_mask_v2_tables,
        _typed_lookups,
    )
    from clasher.rl.structured_obs import StructuredObservationBuilder
    from clasher.torch_sim.simple_public_mask import SimplePublicMaskV2Provider
    from clasher.torch_sim.simple_standard import compile_standard_simple_setup
    from scripts.hog26_scalar_actor_projection import build_scalar_reference_actors
    from scripts.hog26_scalar_policy_inputs import scalar_policy_inputs

    battle, towers, setup, loader, vocabulary = _setup()
    targets = _populate_targets(battle, towers, loader)
    builder = StructuredObservationBuilder(token_names=vocabulary.token_names,
                                           max_entities=128, card_semantics_version=3,
                                           canonical_lane_globals=True)
    static = compile_standard_simple_setup(loader, ["Knight"], device="cpu",
                                           canonical_lane_globals=True)
    lookup, _ = _typed_lookups(static, loader, vocabulary)
    provider = SimplePublicMaskV2Provider(_compile_public_mask_v2_tables(builder, static, lookup))
    with setup.recorder() as recorder:
        for tower, target in zip(towers, targets, strict=True):
            tower._create_projectile(target, battle)
        actors = build_scalar_reference_actors(
            battle, builder, appearances=recorder.appearances,
            visible_to=lambda entity, seat: entity.is_visible_to(seat),
        )
        inputs, _ = scalar_policy_inputs(
            actors, provider, previous_actions=[2304, 2304], episode_starts=[True, True],
            extra_public_effect_tokens=setup.extra_public_effect_tokens,
        )
    for seat, actor in enumerate(actors):
        extra = actor.entity_ids >= 494
        assert int(extra.sum()) == 6
        assert (inputs.entity_ids[seat, 0, extra] == 1).all()
        assert not inputs.entity_id_confidence[seat, 0, extra].any()
        assert inputs.entity_feature_confidence[seat, 0, extra, :9].all()
        assert set(actor.entity_ids[extra]) == {494, 495}


def test_real_full_step_tower_receipts_preserve_physics_and_rng():
    instrumented, towers, setup, loader, _ = _setup()
    control, control_towers, _, control_loader, _ = _setup()
    _populate_targets(instrumented, towers, loader)
    _populate_targets(control, control_towers, control_loader)
    with setup.recorder() as recorder:
        for _ in range(140):
            instrumented.step()
            control.step()
            assert _hash(instrumented) == _hash(control)
            assert instrumented.rng.getstate() == control.rng.getstate()
        assert {r.source_id for r in recorder.receipts} == {t.id for t in towers}
        assert [r.projectile_id for r in recorder.receipts] == sorted(
            r.projectile_id for r in recorder.receipts
        )
    assert all("_create_projectile" not in tower.__dict__ for tower in towers)


@pytest.mark.parametrize("slot", [0, 2, 3, 5])
def test_source_visibility_loss_rejects_before_birth_and_restores(slot):
    visible = [True]
    battle, towers, setup, loader, _ = _setup(
        lambda source, seat: visible[0] or seat == 0
    )
    targets = _populate_targets(battle, towers, loader)
    with setup.recorder() as recorder:
        visible[0] = False
        before = _hash(battle)
        with pytest.raises(ValueError, match="not observable"):
            towers[slot]._create_projectile(targets[slot], battle)
        assert _hash(battle) == before
        assert recorder.appearances == ()
    assert all("_create_projectile" not in tower.__dict__ for tower in towers)


def test_initial_receipt_and_source_position_changes_fail_closed():
    battle, towers, setup, loader, vocabulary = _setup()
    with pytest.raises(ValueError, match="exact six"):
        ScalarTowerReceiptSetup.compile(
            battle, towers[:-1], loader, vocabulary, source_visible_to=lambda *_: True
        )
    swapped = (towers[1], towers[0], *towers[2:])
    with pytest.raises(ValueError, match="exact six"):
        ScalarTowerReceiptSetup.compile(
            battle, swapped, loader, vocabulary, source_visible_to=lambda *_: True
        )
    targets = _populate_targets(battle, towers, loader)
    with setup.recorder() as recorder:
        towers[2].position.x += 1
        before = _hash(battle)
        with pytest.raises(ValueError, match="differs from its exact"):
            towers[2]._create_projectile(targets[2], battle)
        assert _hash(battle) == before
        assert recorder.appearances == ()


def test_missing_visibility_and_context_error_restore():
    with pytest.raises(ValueError, match="not observable"):
        _setup(lambda *_: False)
    _, towers, setup, _, _ = _setup()
    with pytest.raises(RuntimeError, match="fixture error"), setup.recorder():
        raise RuntimeError("fixture error")
    assert all("_create_projectile" not in tower.__dict__ for tower in towers)
