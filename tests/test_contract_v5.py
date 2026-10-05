"""Public observation / model contract v5 (C56 scope expansion).

Covers the pinned vocabulary, the v5 card descriptors, the Princess-tower
placement footprint, the Champion ability action, hidden enemy units and the
v4 -> v5 checkpoint upgrade (bit-identical logits on P16 observations).
"""

import copy
import hashlib
import json
import random
from pathlib import Path

import numpy as np
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.contract_v5 import (
    CHAMPION_GLOBAL_INDICES,
    PINNED_TOKEN_COUNT,
    V5_DESCRIPTOR_NAMES,
    CachedContractV5ActionMask,
    ContractV5ActionMaskBuilder,
    ContractV5ObservationBuilder,
    hidden_from_enemy,
    load_pinned_tokens,
    remap_token_ids,
    validate_public_v5,
)
from clasher.rl.deck_pool import apply_ordered_deck_to_player
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from clasher.rl.public_observation import project_council_public_observation
from clasher.rl.structured_obs import StructuredObservationBuilder

REPO = next(parent for parent in Path(__file__).resolve().parents
            if (parent / "reports/strategy_council_20260928/human-prior-p16").exists() or parent == Path("/"))
P16_CARDS = ("Archers", "Cannon", "DarkPrince", "Fireball", "Giant", "Goblins", "HogRider", "IceGolem",
             "IceSpirit", "Knight", "Log", "Musketeer", "Prince", "Skeletons", "Tesla", "Zap")
HOG = ("HogRider", "Musketeer", "IceGolem", "IceSpirit", "Skeletons", "Cannon", "Fireball", "Log")
P16_CHECKPOINT = REPO / "reports/strategy_council_20260928/human-prior-p16/checkpoints/human-bc-natural-seed2903.pt"
P16_RECON = REPO / "reports/strategy_council_20260928/human-prior-p16/data/recon"
ABILITY = NUM_HAND_SLOTS * NUM_TILES + 1


@pytest.fixture(scope="module")
def v5():
    return ContractV5ObservationBuilder()


@pytest.fixture(scope="module")
def v4():
    return StructuredObservationBuilder(
        card_vocab=sorted(P16_CARDS), max_entities=128, canonical_perspective=True, canonical_lane_globals=True,
        public_history_slots=4, public_seen_card_slots=8, card_semantics_version=4,
        public_entity_levels=True, public_hand_levels=True)


def battle_with(deck0, deck1, seed=7):
    battle = BattleState(rng=random.Random(seed))
    apply_ordered_deck_to_player(battle.players[0], list(deck0))
    apply_ordered_deck_to_player(battle.players[1], list(deck1))
    return battle


# --------------------------------------------------------------------------
# Vocabulary and descriptors
# --------------------------------------------------------------------------

def test_pinned_vocabulary_is_fixed_and_contains_the_pilot_vocabulary(v5, v4):
    tokens = load_pinned_tokens()
    assert len(tokens.tokens) == PINNED_TOKEN_COUNT == 360
    assert tokens.tokens[:2] == ("<pad>", "<unknown>")
    assert len(tokens.cards) == 122
    assert v5.token_names == tokens.tokens
    assert set(v4.token_names) <= set(v5.token_names)
    # The 36 pilot rows keep their v4 stat and semantic columns exactly.
    rows = [v5.token_names.index(name) for name in v4.token_names]
    assert np.array_equal(v5.card_stat_features[rows, : v4.card_stat_features.shape[1]], v4.card_stat_features)


def test_pinned_vocabulary_rejects_reordering(tmp_path):
    payload = json.loads((REPO / "src/clasher/rl/contract_v5_tokens.json").read_text())
    payload["tokens"][2], payload["tokens"][3] = payload["tokens"][3], payload["tokens"][2]
    payload["tokens_sha256"] = hashlib.sha256(json.dumps(payload["tokens"], separators=(",", ":")).encode()).hexdigest()
    path = tmp_path / "tokens.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="reordered"):
        load_pinned_tokens(path)


def test_card_semantic_vectors_are_nonzero_and_distinct(v5):
    cards = [v5.token_id(name, namespace="card_action") for name in v5.pinned_tokens.cards]
    assert min(cards) > 1
    vectors = v5.card_stat_features[cards]
    assert np.all(np.abs(vectors).sum(axis=1) > 0), "every card, Mirror included, has a nonzero vector"
    assert len({vector.tobytes() for vector in vectors}) == len(cards)
    mirror = v5.token_names.index("Mirror")
    assert v5.v5_card_descriptors[mirror, V5_DESCRIPTOR_NAMES.index("mirror")] == 1.0


@pytest.mark.parametrize("card, descriptor", [
    ("Miner", "underground_travel"), ("Miner", "deploy_anywhere"), ("RoyalGhost", "invisibility"),
    ("ArcherQueen", "invisibility"), ("ArcherQueen", "is_champion"), ("MightyMiner", "ability_cost"),
    ("Goblinstein", "ability_cost"), ("InfernoTower", "ramp_damage"), ("Tornado", "pull"),
    ("Clone", "clone"), ("Wallbreakers", "kamikaze"), ("Tombstone", "spawn_interval"),
    ("Elixir Collector", "elixir_generation_per_minute"), ("ElectroDragon", "chain_target_count"),
    ("Golem", "death_damage"),
])
def test_v5_descriptors_name_the_mechanic(v5, card, descriptor):
    assert v5.v5_card_descriptors[v5.token_names.index(card), V5_DESCRIPTOR_NAMES.index(descriptor)] > 0


# --------------------------------------------------------------------------
# v4 is unchanged
# --------------------------------------------------------------------------

def test_v4_mask_footprint_rule_is_unchanged():
    for radius in (0.0, 0.3, 0.5, 0.6, 1.0, 1.0000000298, 1.5, 2.0):
        import math
        assert PublicActionMaskBuilder._footprint_size(radius) == max(1, math.ceil(max(0.0, radius) * 2.0) + 1)
    # The float32 Princess radius produced the 4-tile footprint in v4 and 3 in v5.
    assert PublicActionMaskBuilder._footprint_size(1.0000000298) == 4
    assert ContractV5ActionMaskBuilder._footprint_size(1.0000000298) == 3


def test_v4_builder_keeps_engine_visibility(v4):
    battle = battle_with(HOG, HOG)
    assert v4._actor_visible.__func__ is StructuredObservationBuilder._actor_visible


# --------------------------------------------------------------------------
# Placement mask: the real 3x3 Princess-tower rule
# --------------------------------------------------------------------------

def test_v5_mask_matches_engine_placement_near_own_princess_towers(v5):
    battle = battle_with(HOG, HOG)
    battle.players[0].elixir = 10.0
    mask_builder = ContractV5ActionMaskBuilder(v5)
    v4_mask_builder = PublicActionMaskBuilder(v5)
    packet = v5.build_public(battle, 0)
    mask = mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet))
    v4_mask = v4_mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet))
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    slot = list(battle.players[0].hand[:4]).index("Musketeer")
    mismatches, checked = [], 0
    for tower_x, tower_y in ((3.5, 6.5), (14.5, 6.5)):
        for tile_y in range(int(tower_y) - 3, int(tower_y) + 4):
            for tile_x in range(int(tower_x) - 3, int(tower_x) + 4):
                action = action_space.encode_action(slot, tile_x, tile_y, 0)
                trial = copy.deepcopy(battle)
                accepted = bool(action_space.apply_action(trial, 0, action))
                checked += 1
                if accepted != bool(mask[action]):
                    mismatches.append((tile_x, tile_y, accepted, bool(mask[action])))
    assert checked == 98
    assert not mismatches, mismatches
    # v4 blocked the one-tile ring the game allows.
    assert v4_mask[: NUM_HAND_SLOTS * NUM_TILES].sum() < mask[: NUM_HAND_SLOTS * NUM_TILES].sum()


# --------------------------------------------------------------------------
# Champion ability
# --------------------------------------------------------------------------

def test_ability_is_unmasked_exactly_when_the_engine_allows_it(v5):
    deck = ("ArcherQueen", "Knight", "Archers", "Log", "Fireball", "Skeletons", "Cannon", "IceSpirit")
    battle = battle_with(deck, HOG)
    mask_builder = ContractV5ActionMaskBuilder(v5)
    cached = CachedContractV5ActionMask(v5)
    v4_mask_builder = PublicActionMaskBuilder(v5)

    def check():
        packet = v5.build_public(battle, 0)
        request = PublicActionMaskInput.from_confidence_observation(packet)
        legal = bool(mask_builder.build(request)[ABILITY])
        assert legal == bool(battle.can_activate_champion_ability(0)), battle.tick
        assert bool(cached.build(packet)[ABILITY]) == legal
        assert not v4_mask_builder.build(request)[ABILITY]
        return legal, packet

    assert check()[0] is False
    battle.players[0].elixir = 10.0
    assert battle.deploy_card(0, "ArcherQueen", Position(9.5, 10.5))
    seen = {"legal": 0, "illegal_with_button": 0}
    activated = False
    for _ in range(1400):
        legal, packet = check()
        button = packet.global_feature_confidence[CHAMPION_GLOBAL_INDICES[0]] > 0
        if legal:
            seen["legal"] += 1
            if not activated:
                assert battle.activate_champion_ability(0)
                activated = True
        elif button:
            seen["illegal_with_button"] += 1
        battle.players[0].elixir = min(10.0, battle.players[0].elixir)
        battle.step()
    assert activated and seen["legal"] > 0 and seen["illegal_with_button"] > 0


def test_champion_globals_are_public_only_while_the_button_is_shown(v5):
    deck = ("ArcherQueen", "Knight", "Archers", "Log", "Fireball", "Skeletons", "Cannon", "IceSpirit")
    battle = battle_with(deck, HOG)
    packet = v5.build_public(battle, 0)
    assert not packet.global_feature_confidence[list(CHAMPION_GLOBAL_INDICES)].any()
    battle.players[0].elixir = 10.0
    assert battle.deploy_card(0, "ArcherQueen", Position(9.5, 10.5))
    for _ in range(40):
        battle.step()
    packet = v5.build_public(battle, 0)
    assert packet.global_feature_confidence[list(CHAMPION_GLOBAL_INDICES)].all()
    validate_public_v5(packet)
    # The opponent never sees the other side's ability clock.
    assert not v5.build_public(battle, 1).global_feature_confidence[list(CHAMPION_GLOBAL_INDICES)].any()


# --------------------------------------------------------------------------
# Hidden enemy units (hidden-state invariance)
# --------------------------------------------------------------------------

def _entity_view(packet):
    observation = packet.observation
    count = int(observation.entity_mask.sum())
    return (observation.entity_ids[:count].tobytes(), observation.entity_features[:count].tobytes(),
            observation.entity_levels[:count].tobytes())


def _remove_entity(battle, entity_id):
    clone = copy.deepcopy(battle)
    del clone.entities[entity_id]
    return clone


def _find(battle, player, predicate):
    return [entity for entity in battle.entities.values()
            if entity.player_id == player and entity.is_alive and predicate(entity)]


def test_enemy_underground_miner_is_hidden_and_invariant(v5):
    battle = battle_with(HOG, ("Miner", "Knight", "Archers", "Log", "Fireball", "Skeletons", "Cannon", "IceSpirit"))
    battle.players[1].elixir = 10.0
    assert battle.deploy_card(1, "Miner", Position(3.5, 8.5))
    tokens = load_pinned_tokens()
    v4_like = StructuredObservationBuilder(
        card_vocab=tokens.cards, token_names=tokens.tokens, max_entities=128, canonical_perspective=True,
        canonical_lane_globals=True, public_history_slots=4, public_seen_card_slots=8, card_semantics_version=4,
        public_entity_levels=True, public_hand_levels=True)
    checked = 0
    for _ in range(40):
        battle.step()
        hidden = _find(battle, 1, hidden_from_enemy)
        if not hidden:
            continue
        miner = hidden[0]
        without = _remove_entity(battle, miner.id)
        assert _entity_view(v5.build_public(battle, 0)) == _entity_view(v5.build_public(without, 0))
        # The owner still sees it, and so does v4.
        assert _entity_view(v5.build_public(battle, 1)) != _entity_view(v5.build_public(without, 1))
        v4_view = project_council_public_observation(v4_like.build_actor(battle, 0))
        assert int(v4_view.observation.entity_mask.sum()) > int(v5.build_public(battle, 0).observation.entity_mask.sum())
        checked += 1
    assert checked > 0
    for _ in range(200):
        battle.step()
    assert not _find(battle, 1, hidden_from_enemy), "the Miner surfaces and becomes visible"


@pytest.mark.parametrize("card", ["RoyalGhost", "ArcherQueen"])
def test_enemy_stealthed_unit_is_hidden_and_invariant(v5, card):
    battle = battle_with(HOG, (card, "Knight", "Archers", "Log", "Fireball", "Skeletons", "Cannon", "IceSpirit"))
    battle.players[1].elixir = 10.0
    assert battle.deploy_card(1, card, Position(9.5, 22.5))
    for _ in range(30):
        battle.step()
    from clasher.entities import Troop
    unit = max(_find(battle, 1, lambda entity: isinstance(entity, Troop)), key=lambda entity: entity.id)
    # Force the stealth window the engine opens (Royal Ghost idle / Queen cloak).
    from clasher.kinematics import logic_time_milliseconds
    unit._stealth_until = logic_time_milliseconds(battle.time) + 2000
    assert hidden_from_enemy(unit)
    without = _remove_entity(battle, unit.id)
    assert _entity_view(v5.build_public(battle, 0)) == _entity_view(v5.build_public(without, 0))
    assert _entity_view(v5.build_public(battle, 1)) != _entity_view(v5.build_public(without, 1))


# --------------------------------------------------------------------------
# Checkpoint upgrade: bit-identical logits on P16 observations
# --------------------------------------------------------------------------

def _gamedata_sha256():
    from clasher.paths import gamedata_path  # noqa: PLC0415
    return hashlib.sha256(Path(gamedata_path()).read_bytes()).hexdigest()


def test_upgraded_p16_checkpoint_gives_bit_identical_logits(v5):
    torch = pytest.importorskip("torch")
    if not P16_CHECKPOINT.exists() or not any(P16_RECON.glob("shard-014-part-00.npz")):
        pytest.skip("P16 checkpoint or reconstruction shards are not present")
    from clasher.rl.contract_v5 import upgrade_policy_payload_to_v5
    from clasher.rl.human_replay_bc import episode_arrays
    from clasher.rl.human_replay_demonstrations import load_human_replay_shard
    from clasher.rl.imitation import _sequence_batch_inputs
    from clasher.rl.model import ClasherPolicy, PolicyConfig

    payload = torch.load(P16_CHECKPOINT, map_location="cpu", weights_only=False)
    try:
        if _gamedata_sha256() != payload["gamedata_sha256"]:
            pytest.skip("run under the frozen runtime whose gamedata produced the P16 checkpoint")
    except ImportError:
        pass
    source_config = PolicyConfig.from_dict(payload["model_config"])
    state = payload["model_state_dict"]
    source = ClasherPolicy(source_config, torch.cat([state["actor_encoder.card_stat_features"],
                                                     state["actor_encoder.semantic_card_features"]], dim=1))
    source.load_state_dict(payload["model_state_dict"])
    upgraded = upgrade_policy_payload_to_v5(payload, v5)
    target = ClasherPolicy(PolicyConfig.from_dict(upgraded["model_config"]), torch.as_tensor(v5.card_stat_features))
    target.load_state_dict(upgraded["model_state_dict"])
    source.eval()
    target.eval()
    shard = load_human_replay_shard(P16_RECON / "shard-014-part-00.npz")
    source_tokens = tuple(shard.header["token_names"])
    compared = 0
    for summary in shard.header["perspectives"][:3]:
        arrays = episode_arrays(shard, summary)
        length = min(160, len(arrays["expert_actions"]))
        arrays = {name: values[:length] for name, values in arrays.items()}
        remapped = dict(arrays)
        for name in ("entity_ids", "hand_ids", "opponent_history_ids", "opponent_seen_card_ids", "own_last_play_ids"):
            remapped[name] = remap_token_ids(arrays[name], source_tokens, v5.token_names)
        rows = np.arange(length).reshape(1, length)
        with torch.no_grad():
            a = source(_sequence_batch_inputs(arrays, rows, torch.device("cpu"), trim_entity_padding=False,
                                              reset_memory=False), source.initial_state(1))
            b = target(_sequence_batch_inputs(remapped, rows, torch.device("cpu"), trim_entity_padding=False,
                                              reset_memory=False), target.initial_state(1))
        for name in ("joint_logits", "action_type_logits", "location_logits"):
            assert torch.equal(getattr(a, name), getattr(b, name)), name
        assert torch.equal(a.next_state[0], b.next_state[0]) and torch.equal(a.next_state[1], b.next_state[1])
        compared += length
    assert compared > 300
