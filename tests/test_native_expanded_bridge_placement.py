"""A destroyed lane's bridge becomes available for troop deployment."""
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from clasher.rl.public_observation import exact_public_observation
from clasher.rl.structured_obs import StructuredObservationBuilder


def destroy_lane(battle, owner, lane):
    tower = next(e for e in battle.entities.values() if e.player_id == 1 - owner and getattr(e, "_crown_tower_slot", None) == lane)
    tower.take_damage(tower.hitpoints)
    battle.step()


@pytest.mark.parametrize("owner", [0, 1])
@pytest.mark.parametrize("lane,x", [("left", 3), ("right", 14)])
def test_expanded_bridge_is_present_in_public_and_simulator_masks(owner, lane, x):
    battle = BattleState()
    destroy_lane(battle, owner, lane)
    battle.players[owner].hand = ["IceGolem"]
    builder = StructuredObservationBuilder(card_vocab=["IceGolem"], canonical_lane_globals=True)
    public = PublicActionMaskInput.from_confidence_observation(exact_public_observation(builder.build_actor(battle, owner)))
    mask = PublicActionMaskBuilder(builder).build(public)
    space = DiscreteTileActionSpace()
    for y in (15, 16):
        assert battle.arena.can_deploy_at(Position(x + .5, y + .5), owner, battle)
        assert mask[space.encode_action(0, x, y, owner)]
        assert not mask[space.encode_action(0, 10, y, owner)]
        assert not mask[space.encode_action(0, 17 - x, y, owner)]


@pytest.mark.parametrize("fast_path", [False, True])
def test_native_cannon_overlap_selects_newly_available_bridge(fast_path):
    # Native expanded seed1305001 prefix2850. Cannon occupies14.5,18.5;
    # Ice Golem requested at the same anchor resolves to14.5,16.499.
    battle = BattleState(fast_path=fast_path)
    destroy_lane(battle, 1, "right")
    battle._spawn_entity(Building, Position(14.5, 18.5), 1, battle.card_loader.get_card("Cannon"))
    battle.players[1].hand = ["IceGolem"]
    before = set(battle.entities)
    assert battle.deploy_card(1, "IceGolem", Position(14.5, 18.5))
    unit = battle.entities[(set(battle.entities) - before).pop()]
    battle.step()
    assert (round(unit.position.x * 1000), round(unit.position.y * 1000)) == (14500, 16499)


@pytest.mark.parametrize("owner", [0, 1])
@pytest.mark.parametrize("lane,x,accepted", [
    ("left", 2.5, True), ("left", 3.5, True), ("left", 4.5, False),
    ("right", 13.5, True), ("right", 14.5, True), ("right", 15.5, False),
])
@pytest.mark.parametrize("y", [15.5, 16.5])
def test_native_bridge_edges_survive_public_rotation(owner, lane, x, accepted, y):
    # Native controls: owner-zero-bridge-controls and failed-bridge-controls.
    # Acceptance follows arena coordinates, not the rotated action-grid edge.
    battle = BattleState()
    destroy_lane(battle, owner, lane)
    battle.players[owner].hand = ["Knight"]
    battle.players[owner].elixir = 10
    builder = StructuredObservationBuilder(card_vocab=["Knight"], canonical_lane_globals=True)
    actor = builder.build_actor(battle, owner)
    assert actor.board_rotated is bool(owner)
    public = PublicActionMaskInput.from_confidence_observation(exact_public_observation(actor))
    mask = PublicActionMaskBuilder(builder).build(public)
    action = DiscreteTileActionSpace().encode_action(0, int(x), int(y), owner)
    assert bool(mask[action]) is accepted
    assert battle.arena.can_deploy_at(Position(x, y), owner, battle) is accepted
    assert battle.deploy_card(owner, "Knight", Position(x, y)) is accepted


def test_unknown_orientation_cannot_guess_expanded_bridge_edge():
    from dataclasses import replace

    battle = BattleState()
    destroy_lane(battle, 1, "right")
    builder = StructuredObservationBuilder(card_vocab=["Knight"], canonical_lane_globals=True)
    actor = replace(builder.build_actor(battle, 1), board_rotated=None)
    public = PublicActionMaskInput.from_confidence_observation(exact_public_observation(actor))
    with pytest.raises(ValueError, match="requires public board orientation"):
        PublicActionMaskBuilder(builder).build(public)


def test_public_sequence_preserves_rotation_and_marks_legacy_unknown(tmp_path):
    import json

    import numpy as np

    from clasher.rl.public_policy_contract import PublicPolicySequence

    battle = BattleState()
    builder = StructuredObservationBuilder(card_vocab=["Knight"], canonical_lane_globals=True)
    sequence = PublicPolicySequence.from_observations(
        builder, [builder.build_actor(battle, owner) for owner in (0, 1)]
    )
    path = tmp_path / "current.npz"
    sequence.save(path)
    loaded = PublicPolicySequence.load(path, token_names=sequence.token_names)
    assert loaded.arrays["board_rotated"].tolist() == [0, 1]
    legacy = tmp_path / "legacy.npz"
    arrays = {k: v for k, v in sequence.arrays.items() if k != "board_rotated"}
    with legacy.open("xb") as stream:
        np.savez_compressed(stream, metadata=np.asarray(json.dumps({
            "schema": "clasher.public-policy.v3", "token_names": sequence.token_names,
        })), **arrays)
    loaded_legacy = PublicPolicySequence.load(legacy, token_names=sequence.token_names)
    assert loaded_legacy.arrays["board_rotated"].tolist() == [-1, -1]
