from dataclasses import fields
from types import SimpleNamespace

import pytest
import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import TimedExplosive
from clasher.rl.simple_pytorch_backend import (
    _compile_public_mask_v2_tables,
    _typed_lookups,
    load_current_client_typed_vocabulary,
)
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.resident_outputs import TensorPublicStructuredObservation
from clasher.torch_sim.simple_public_mask import SimplePublicMaskV2Provider
from clasher.torch_sim.simple_standard import compile_standard_simple_setup
from scripts.hog26_scalar_public_payload_mask import (
    ScalarPublicPayloadMaskProvider,
    ScalarPublicPayloadMaskRules,
    policy_public_view,
    scalar_policy_inputs_with_payload_mask,
)


@pytest.fixture(scope="module")
def setup():
    vocabulary = load_current_client_typed_vocabulary()
    names = (*vocabulary.token_names, "projectile:TowerPrincessProjectile", "public_tower_shot:king",
             "public_effect:chain_bolt", "building_body:SkeletonContainerNew")
    builder = StructuredObservationBuilder(token_names=vocabulary.token_names, max_entities=8,
                                           card_semantics_version=3, canonical_lane_globals=True)
    compiled = compile_standard_simple_setup(builder.loader, ["Knight", "Cannon", "Fireball", "Log"],
                                             device="cpu", canonical_lane_globals=True)
    lookup, _ = _typed_lookups(compiled, builder.loader, vocabulary)
    base = SimplePublicMaskV2Provider(_compile_public_mask_v2_tables(builder, compiled, lookup))
    rules = ScalarPublicPayloadMaskRules.compile(builder.loader, policy_token_names=vocabulary.token_names,
                                                 outcome_token_names=names)
    return builder, ScalarPublicPayloadMaskProvider(base, rules)


def actor_fixture(builder, provider, token, *, viewer=0, owner=0, canonical_x=9.0, canonical_y=12.0):
    world_x, world_y = ((canonical_x, canonical_y) if viewer == 0
                        else (18 - canonical_x, 32 - canonical_y))
    ids = torch.full((1, 2, 1), token, dtype=torch.int64)
    features = torch.zeros((1, 2, 1, 32))
    for seat in (0, 1):
        x, y = ((world_x, world_y) if seat == 0 else (18 - world_x, 32 - world_y))
        features[0, seat, 0, :4] = torch.tensor([x / 18, y / 32, owner == seat, owner != seat])
        features[0, seat, 0, 7] = 1
    hand = torch.tensor([[builder.token_id(name, namespace="card_action") for name in
                          ("Knight", "Cannon", "Fireball", "Log")] + [0]]).expand(2, -1)[None].clone()
    globals_ = torch.ones((1, 2, 18))
    return TensorPublicStructuredObservation(ids, features, torch.ones((1, 2, 1), dtype=torch.bool),
                                             hand, globals_)


def test_static_authority_and_new_semantics(setup):
    builder, provider = setup
    rules = provider.rules
    assert [(rules.outcome_token_names[i], r) for i, r in enumerate(rules.radius_logic_units) if r] == [
        ("building_body:BalloonBomb", 450), ("building_body:BombTowerBomb", 450),
        ("building_body:SkeletonContainerNew", 500)]
    assert len(rules.payload_sha256) == 3 and all(len(d) == 64 for _, d in rules.payload_sha256)
    actor = actor_fixture(builder, provider, 60)
    result = provider.build(actor)
    assert result.semantics_digest != provider.tables.semantics_digest
    assert result.semantics["base_semantics_digest"] == provider.tables.semantics_digest
    assert result.semantics["scalar_public_payload_digest"] == rules.digest


@pytest.mark.parametrize("token", [60, 64, 497])
@pytest.mark.parametrize("viewer", [0, 1])
@pytest.mark.parametrize("owner", [0, 1])
def test_all_tiles_match_scalar_payload_occupancy_for_visible_own_and_enemy_bodies(setup, token, viewer, owner):
    builder, provider = setup
    actor = actor_fixture(builder, provider, token, viewer=viewer, owner=owner)
    actual = provider.build(actor).masks
    base = provider.base_provider.build(policy_public_view(actor, provider.rules)).masks
    assert not bool((actual & ~base).any())
    battle = BattleState()
    bomb = TimedExplosive(id=battle.next_entity_id, position=Position(9, 12 if viewer == 0 else 20),
                          player_id=owner, card_stats=None, hitpoints=1, max_hitpoints=1,
                          damage=0, range=0, sight_range=0,
                          deployment_collision_radius=provider.rules.radius_logic_units[token] / 1000)
    battle.entities[bomb.id] = bomb
    for slot, name in enumerate(("Knight", "Cannon", "Fireball", "Log")):
        stats = builder.loader.get_card(name)
        for tile in range(576):
            cx, cy = tile % 18 + 0.5, tile // 18 + 0.5
            position = Position(cx, cy) if viewer == 0 else Position(18 - cx, 32 - cy)
            occupied = False if name in {"Fireball", "Log"} else battle.is_deployment_payload_occupied(
                position, card_stats=stats if name == "Cannon" else None,
                mover_radius=stats.collision_radius or 0.5,
            )
            index = slot * 576 + tile
            assert bool(actual[0, viewer, index]) == (bool(base[0, viewer, index]) and not occupied), (
                viewer, owner, token, name, position
            )
    assert torch.equal(actual[..., 2304:], base[..., 2304:])


@pytest.mark.parametrize("name,slot", [("Knight", 0), ("Cannon", 1)])
@pytest.mark.parametrize("outside_units", [0, 1])
def test_tangent_is_blocked_and_one_logic_unit_outside_is_allowed(setup, name, slot, outside_units):
    builder, provider = setup
    stats = builder.loader.get_card(name)
    if name == "Knight":
        body_extent = stats.collision_radius
    else:
        body_extent = BattleState()._building_footprint_size_tiles(stats) / 2
    actor = actor_fixture(builder, provider, 60, canonical_x=9.5 + body_extent + .45 + outside_units / 1000,
                          canonical_y=12.5)
    index = slot * 576 + 12 * 18 + 9
    assert bool(provider.build(actor).masks[0, 0, index]) == bool(outside_units)


def test_hidden_or_nonbody_effect_does_not_block_and_inputs_are_unchanged(setup):
    builder, provider = setup
    actor = actor_fixture(builder, provider, 497)
    copies = [getattr(actor, f.name).clone() for f in fields(actor)]
    refined = provider.build(actor)
    assert all(torch.equal(getattr(actor, f.name), old) for f, old in zip(fields(actor), copies, strict=True))
    actor.entity_mask.zero_()
    hidden = provider.build(actor)
    assert torch.equal(hidden.masks, provider.base_provider.build(policy_public_view(actor, provider.rules)).masks)
    actor.entity_mask.fill_(True)
    actor.entity_ids.fill_(496)  # chain category has no deployment footprint.
    other = provider.build(actor)
    assert torch.equal(other.masks, hidden.masks)
    assert not torch.equal(refined.masks, hidden.masks)


def test_unknown_policy_mapping_preserves_497_geometry_only_in_public_refinement(setup):
    builder, provider = setup
    actor = actor_fixture(builder, provider, 497)
    actors = tuple(SimpleNamespace(**{f.name: getattr(actor, f.name)[0, seat].numpy()
                                     for f in fields(actor)}) for seat in (0, 1))
    inputs, result = scalar_policy_inputs_with_payload_mask(
        actors, provider, previous_actions=[2304, 2304], episode_starts=[True, True])
    assert (inputs.entity_ids == 1).all()
    assert not inputs.entity_id_confidence.any()
    assert (inputs.entity_features[..., 7] == 1).all()
    assert not inputs.entity_features[..., 4:6].any()
    index = 12 * 18 + 9
    assert not result.masks[0, 0, index]
    assert not inputs.action_mask[0, 0, index]
    premature_mapping = provider.build(policy_public_view(actor, provider.rules))
    assert premature_mapping.masks[0, 0, index]


def test_changed_vocabulary_and_hidden_runtime_geometry_are_not_inputs(setup):
    builder, provider = setup
    with pytest.raises(ValueError, match="uniquely extend"):
        ScalarPublicPayloadMaskRules.compile(builder.loader, policy_token_names=provider.rules.policy_token_names,
                                             outcome_token_names=provider.rules.outcome_token_names[:-1] + ("<pad>",))
    assert {f.name for f in fields(TensorPublicStructuredObservation)} == {
        "entity_ids", "entity_features", "entity_mask", "hand_ids", "global_features"}


def test_static_radius_change_changes_rule_authority(setup):
    builder, provider = setup

    def changed_card(name):
        stats = builder.loader.get_card(name)
        if name != "Balloon":
            return stats
        raw = stats._raw_entry
        body = raw["summonCharacterData"]
        payload = body["deathSpawnCharacterData"]
        return SimpleNamespace(_raw_entry={**raw, "summonCharacterData": {
            **body, "deathSpawnCharacterData": {**payload, "collisionRadius": 451}}})

    changed = ScalarPublicPayloadMaskRules.compile(SimpleNamespace(get_card=changed_card),
        policy_token_names=provider.rules.policy_token_names,
        outcome_token_names=provider.rules.outcome_token_names)
    assert changed.radius_logic_units[60] == 451
    assert changed.digest != provider.rules.digest
    assert changed.payload_sha256 != provider.rules.payload_sha256


def test_anchor_resolution_is_frozen_and_changes_semantic_authority(setup, monkeypatch):
    import scripts.hog26_scalar_public_payload_mask as module

    builder, provider = setup
    actor = actor_fixture(builder, provider, 60)
    original = provider.build(actor)
    original_anchor = module.building_anchor

    def shifted_anchor(position, size):
        resolved = original_anchor(position, size)
        return Position(resolved.x + 0.001, resolved.y)

    monkeypatch.setattr(module, "building_anchor", shifted_anchor)
    assert torch.equal(provider.build(actor).masks, original.masks)
    changed = ScalarPublicPayloadMaskProvider(provider.base_provider, provider.rules)
    assert changed.semantics_digest != provider.semantics_digest
    assert changed.semantics["scalar_public_building_anchor_sha256"] != provider.semantics[
        "scalar_public_building_anchor_sha256"
    ]


def test_irrelevant_effect_payload_columns_cannot_change_placement_mask(setup):
    builder, provider = setup
    actor = actor_fixture(builder, provider, 497)
    before = provider.build(actor).masks
    actor.entity_features[..., 9:] = 99999
    assert torch.equal(provider.build(actor).masks, before)


def test_resolved_anchor_masks_keep_batches_and_seats_independent(setup):
    builder, provider = setup
    actors = [
        actor_fixture(builder, provider, 60),
        actor_fixture(builder, provider, 497, viewer=1, owner=1,
                      canonical_x=7.0, canonical_y=12.0),
    ]
    combined = TensorPublicStructuredObservation(**{
        field.name: torch.cat([getattr(actor, field.name) for actor in actors], dim=0)
        for field in fields(TensorPublicStructuredObservation)
    })
    expected = torch.cat([provider.build(actor).masks for actor in actors], dim=0)
    assert torch.equal(provider.build(combined).masks, expected)
