from __future__ import annotations

import json
import random
from collections import deque
from itertools import pairwise

import pytest

from clasher import rust_core, rust_publication
from clasher.battle import BattleState
from clasher.differential import canonical_battle_snapshot
from clasher.entities import Troop
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rust_core import (
    _PREPARED_PUBLICATION_DELTA_CONSUMER,
    _PREPARED_PUBLICATION_RAW_CONSUMER,
    ResidentRustBattle,
    RustBattleMode,
    rust_core_available,
)
from clasher.rust_differential import (
    python_resident_semantic_snapshot,
    rust_resident_semantic_snapshot,
)
from clasher.rust_publication import (
    ResidentPublicationError,
    _build_direct_delta_publication_plan,
    _build_direct_publication_plan,
    publish_complete_tick_state,
)
from clasher.rust_runtime import ResidentCompleteTickRuntime

pytestmark = pytest.mark.skipif(
    not rust_core_available(),
    reason="optional Rust extension is not installed",
)


def _prepare_hands(battle: BattleState, card_name: str) -> None:
    battle.players[0].hand = [card_name, "Knight", "Knight", "Knight"]
    battle.players[0].cycle_queue = deque(["Knight"] * 4)
    battle.players[0].elixir = battle.players[0].max_elixir
    battle.players[1].hand = ["Knight"] * 4
    battle.players[1].cycle_queue = deque(["Knight"] * 4)
    battle.players[1].elixir = battle.players[1].max_elixir


def _apply_python_joint_actions(
    battle: BattleState,
    action_space: DiscreteTileActionSpace,
    actions: tuple[int, int],
) -> tuple[dict[int, bool], tuple[int, int]]:
    order = [0, 1]
    battle.rng.shuffle(order)
    success = {
        player_id: action_space.apply_action(battle, player_id, actions[player_id])
        for player_id in order
    }
    return success, (order[0], order[1])


def _spawned_troops(battle: BattleState, first_id: int) -> list[Troop]:
    return [
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id >= first_id and type(entity) is Troop
    ]


def _assert_stats_aliases(
    card_name: str,
    spawned: list[Troop],
    *,
    fresh: bool = True,
) -> None:
    if card_name == "GoblinGang":
        assert [str(entity.card_stats.name) for entity in spawned] == [
            "Goblin_Stab",
            "Goblin_Stab",
            "Goblin_Stab",
            "SpearGoblin",
            "SpearGoblin",
            "SpearGoblin",
        ]
        assert spawned[0].card_stats is spawned[1].card_stats is spawned[2].card_stats
        assert spawned[3].card_stats is spawned[4].card_stats is spawned[5].card_stats
        assert spawned[0].card_stats is not spawned[3].card_stats
        if fresh:
            assert [
                entity.deploy_delay_remaining for entity in spawned
            ] == pytest.approx([1.0, 1.1, 1.2, 1.3, 1.4, 1.5])
    else:
        assert [str(entity.card_stats.name) for entity in spawned] == [
            "RascalBoy",
            "RascalGirl",
            "RascalGirl",
        ]
        assert spawned[0].card_stats is not spawned[1].card_stats
        assert spawned[1].card_stats is spawned[2].card_stats
        if fresh:
            assert [
                entity.deploy_delay_remaining for entity in spawned
            ] == pytest.approx([1.0, 1.0, 1.0])
    assert all(
        entity.mechanics is not other.mechanics
        for entity, other in pairwise(spawned)
    )


def test_catalog_structurally_qualifies_current_mixed_troop_formations() -> None:
    battle = BattleState()
    data_path = battle.card_loader.data_file
    stat = data_path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(data_path.resolve()), stat.st_mtime_ns, stat.st_size
    )
    payload = json.loads(bundle.payload)
    mixed = {
        card["lookup_name"]: card
        for card in payload["cards"]
        if card["mixed_formation_members"]
    }
    resident = ResidentRustBattle.from_battle(battle)

    assert payload["schema_version"] == 18
    assert set(mixed) == {"GoblinGang", "Rascals"}
    assert mixed["GoblinGang"]["summon_count"] == 6
    assert mixed["Rascals"]["summon_count"] == 3
    assert all(len(card["mixed_formation_members"]) == 4 for card in mixed.values())
    assert resident.resident_action_card_capability_reasons("GoblinGang") == ()
    assert resident.resident_action_card_capability_reasons("Rascals") == ()
    assert resident.resident_action_card_capability_reasons("Goblinstein")
    assert resident.resident_action_card_capability_reasons("GoblinBarrel") == ()


@pytest.mark.parametrize("card_name", ["GoblinGang", "Rascals"])
@pytest.mark.parametrize("player_id", [0, 1])
@pytest.mark.parametrize("world_x", [0, 14])
def test_mixed_formation_actions_match_both_players_lanes_and_edge_clamp(
    card_name: str,
    player_id: int,
    world_x: int,
) -> None:
    battle = BattleState(rng=random.Random(170_000 + player_id * 100 + world_x))
    _prepare_hands(battle, card_name)
    if player_id == 1:
        battle.players[1].hand[0] = card_name
        battle.players[0].hand[0] = "Knight"
    first_id = battle.next_entity_id
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    world_y = 10 if player_id == 0 else 21
    action = action_space.encode_action(0, world_x, world_y, player_id)
    actions = (
        action if player_id == 0 else action_space.no_op_action,
        action if player_id == 1 else action_space.no_op_action,
    )

    expected_success, expected_order = _apply_python_joint_actions(
        battle, action_space, actions
    )
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)

    assert actual_success == expected_success == {0: True, 1: True}
    assert actual_order == expected_order
    spawned = _spawned_troops(battle, first_id)
    _assert_stats_aliases(card_name, spawned)
    assert [entity.id for entity in spawned] == list(
        range(first_id, first_id + len(spawned))
    )
    assert rust_resident_semantic_snapshot(resident) == (
        python_resident_semantic_snapshot(battle)
    )
    for _ in range(32):
        assert resident.advance_complete_tick()
        battle._step_logic_tick(refresh_fast_path_end=False)
        assert rust_resident_semantic_snapshot(resident) == (
            python_resident_semantic_snapshot(battle)
        )


def test_simultaneous_goblin_gangs_preserve_shuffle_order_and_twelve_ids() -> None:
    battle = BattleState(rng=random.Random(170_100))
    for player in battle.players:
        player.hand = ["GoblinGang", "Knight", "Knight", "Knight"]
        player.cycle_queue = deque(["Knight"] * 4)
        player.elixir = player.max_elixir
    first_id = battle.next_entity_id
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    actions = (
        action_space.encode_action(0, 5, 10, 0),
        action_space.encode_action(0, 12, 21, 1),
    )

    expected_success, expected_order = _apply_python_joint_actions(
        battle, action_space, actions
    )
    actual_success, actual_order = resident.apply_resident_joint_actions(*actions)

    assert actual_success == expected_success == {0: True, 1: True}
    assert actual_order == expected_order
    spawned = _spawned_troops(battle, first_id)
    assert len(spawned) == 12
    assert [entity.player_id for entity in spawned[:6]] == [expected_order[0]] * 6
    assert [entity.player_id for entity in spawned[6:]] == [expected_order[1]] * 6
    assert [entity.id for entity in spawned] == list(range(first_id, first_id + 12))
    assert rust_resident_semantic_snapshot(resident) == (
        python_resident_semantic_snapshot(battle)
    )


def test_goblin_gang_joint_headroom_rejects_before_shuffle_or_player_mutation() -> None:
    battle = BattleState(rng=random.Random(170_110))
    for player in battle.players:
        player.hand = ["GoblinGang", "Knight", "Knight", "Knight"]
        player.cycle_queue = deque(["Knight"] * 4)
        player.elixir = player.max_elixir
    battle.next_entity_id = (1 << 63) - 11
    resident = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    actions = (
        action_space.encode_action(0, 5, 10, 0),
        action_space.encode_action(0, 12, 21, 1),
    )
    before = (
        resident.rng_state_bytes(),
        resident.player_states(),
        rust_resident_semantic_snapshot(resident),
    )

    with pytest.raises(RuntimeError, match="entity-ID allocation headroom"):
        resident.apply_resident_joint_actions(*actions)

    assert (
        resident.rng_state_bytes(),
        resident.player_states(),
        rust_resident_semantic_snapshot(resident),
    ) == before


@pytest.mark.parametrize(
    "mutation",
    ["offset", "delay", "stats_fingerprint", "stats_group", "effective_name"],
)
def test_mixed_catalog_member_tamper_fails_closed(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState(rng=random.Random(170_120))
    _prepare_hands(battle, "GoblinGang")
    path = battle.card_loader.data_file
    stat = path.stat()
    bundle = rust_core._resident_card_catalog_bundle(
        str(path.resolve()), stat.st_mtime_ns, stat.st_size
    )
    payload = json.loads(bundle.payload)
    card = next(card for card in payload["cards"] if card["lookup_name"] == "GoblinGang")
    member = card["mixed_formation_members"][0][0]
    if mutation == "offset":
        member["offset"][0] += 1
    elif mutation == "delay":
        member["deploy_delay"] += 0.05
    elif mutation == "stats_fingerprint":
        member["card_stats_fingerprint"] = "0" * 64
    elif mutation == "stats_group":
        member["card_stats_group"] = 7
    else:
        member["effective_name"] = "SpearGoblin"
    tampered = rust_core._ResidentCardCatalogBundle(
        payload=json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "ascii"
        ),
        action_recipes=bundle.action_recipes,
        death_spawn_recipes=bundle.death_spawn_recipes,
        action_member_recipes=bundle.action_member_recipes,
        rolling_spawn_recipes=bundle.rolling_spawn_recipes,
        rolling_projectile_recipes=bundle.rolling_projectile_recipes,
        pending_spell_action_kinds=bundle.pending_spell_action_kinds,
    )
    monkeypatch.setattr(rust_core, "_resident_card_catalog_bundle", lambda *_: tampered)
    resident = ResidentRustBattle.from_battle(battle)
    before = (
        resident.rng_state_bytes(),
        resident.player_states(),
        rust_resident_semantic_snapshot(resident),
    )
    action_space = DiscreteTileActionSpace()

    assert resident.resident_action_card_capability_reasons("GoblinGang")
    with pytest.raises(RuntimeError, match="unsupported hand card"):
        resident.apply_resident_joint_actions(
            action_space.encode_action(0, 9, 10, 0),
            action_space.no_op_action,
        )
    assert (
        resident.rng_state_bytes(),
        resident.player_states(),
        rust_resident_semantic_snapshot(resident),
    ) == before


@pytest.mark.parametrize("card_name", ["GoblinGang", "Rascals"])
def test_mixed_full_delta_publication_and_stats_aliases(card_name: str) -> None:
    battle = BattleState(rng=random.Random(170_130), fast_path=True)
    _prepare_hands(battle, card_name)
    prior = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 9, 10, 0)
    candidate, success, _order, advanced = prior.preview_resident_joint_action_interval(
        action,
        action_space.no_op_action,
        8,
    )
    assert success == {0: True, 1: True}
    assert advanced == 8
    registry: dict[int, object] = dict(battle.entities)
    full_raw = candidate.prepare_publication(prior)._consume_raw_parts(
        _PREPARED_PUBLICATION_RAW_CONSUMER
    )
    delta_raw = candidate.prepare_publication(prior)._consume_delta_parts(
        _PREPARED_PUBLICATION_DELTA_CONSUMER
    )

    full_plan = _build_direct_publication_plan(
        full_raw,
        battle=battle,
        resident=candidate,
        entity_registry=registry,
    )
    delta_plan = _build_direct_delta_publication_plan(
        delta_raw,
        battle=battle,
        resident=candidate,
        entity_registry=registry,
    )
    expected_count = 6 if card_name == "GoblinGang" else 3
    assert sum(
        entity.entity_id >= battle.next_entity_id for entity in full_plan.entities
    ) == expected_count
    assert sum(entity.full is not None for entity in delta_plan.entities) == expected_count

    publish_complete_tick_state(
        battle,
        candidate,
        prior_resident=prior,
        entity_registry=registry,
    )
    spawned = _spawned_troops(battle, battle.next_entity_id - expected_count)
    _assert_stats_aliases(card_name, spawned, fresh=False)
    assert python_resident_semantic_snapshot(battle) == (
        rust_resident_semantic_snapshot(candidate)
    )
    battle._step_logic_tick(refresh_fast_path_end=False)


@pytest.mark.parametrize("payload_kind", ["full", "delta"])
def test_mixed_publication_rejects_per_ordinal_provenance_tamper(
    payload_kind: str,
) -> None:
    battle = BattleState(rng=random.Random(170_135), fast_path=True)
    _prepare_hands(battle, "GoblinGang")
    prior = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    candidate, success, _order, advanced = prior.preview_resident_joint_action_interval(
        action_space.encode_action(0, 9, 10, 0),
        action_space.no_op_action,
        0,
    )
    assert success == {0: True, 1: True}
    assert advanced == 0
    registry: dict[int, object] = dict(battle.entities)
    before = canonical_battle_snapshot(battle)

    if payload_kind == "full":
        raw = candidate.prepare_publication(prior)._consume_raw_parts(
            _PREPARED_PUBLICATION_RAW_CONSUMER
        )
        births = [
            row["character_birth"]
            for row in raw["entities"]
            if row["id"] >= battle.next_entity_id
        ]
        builder = _build_direct_publication_plan
    else:
        raw = candidate.prepare_publication(prior)._consume_delta_parts(
            _PREPARED_PUBLICATION_DELTA_CONSUMER
        )
        births = [
            row["full"]["character_birth"]
            for row in raw["entities"]
            if row["full"] is not None
        ]
        builder = _build_direct_delta_publication_plan

    birth = births[0]
    current_recipe = candidate.character_action_birth_recipe(
        birth["lookup_name"],
        birth["template_fingerprint"],
        birth["ordinal"],
    )
    catalog = candidate._birth_catalog
    assert current_recipe is not None
    assert current_recipe.formation_variant is not None
    assert catalog is not None
    birth["template_fingerprint"] = next(
        fingerprint
        for (lookup_name, ordinal, fingerprint), recipe in (
            catalog.action_member_recipes.items()
        )
        if lookup_name == birth["lookup_name"]
        and ordinal == birth["ordinal"]
        and recipe.formation_variant != current_recipe.formation_variant
    )

    with pytest.raises(ResidentPublicationError, match="unknown catalog birth recipe"):
        builder(
            raw,
            battle=battle,
            resident=candidate,
            entity_registry=registry,
        )

    assert canonical_battle_snapshot(battle) == before
    assert tuple(registry.items()) == tuple(battle.entities.items())


def test_mixed_publication_commit_failure_rolls_back_exactly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    battle = BattleState(rng=random.Random(170_140), fast_path=True)
    _prepare_hands(battle, "GoblinGang")
    prior = ResidentRustBattle.from_battle(battle)
    action_space = DiscreteTileActionSpace()
    candidate, success, _order, advanced = prior.preview_resident_joint_action_interval(
        action_space.encode_action(0, 9, 10, 0),
        action_space.no_op_action,
        8,
    )
    assert success == {0: True, 1: True}
    assert advanced == 8
    registry: dict[int, object] = dict(battle.entities)
    canonical_before = canonical_battle_snapshot(battle)
    entities_before = tuple(battle.entities.items())
    registry_before = tuple(registry.items())

    def reject_commit(*_args: object, **_kwargs: object) -> None:
        raise ResidentPublicationError("injected mixed publication failure")

    monkeypatch.setattr(
        rust_publication,
        "_after_typed_publication_commit",
        reject_commit,
    )
    with pytest.raises(ResidentPublicationError, match="rolled back"):
        publish_complete_tick_state(
            battle,
            candidate,
            prior_resident=prior,
            entity_registry=registry,
        )

    assert canonical_battle_snapshot(battle) == canonical_before
    assert tuple(battle.entities.items()) == entities_before
    assert tuple(registry.items()) == registry_before


@pytest.mark.parametrize("card_name", ["GoblinGang", "Rascals"])
def test_mixed_action_off_shadow_on_continuation(card_name: str) -> None:
    base = BattleState(rng=random.Random(170_150), fast_path=True)
    _prepare_hands(base, card_name)
    off = base.clone()
    shadow_battle = base.clone()
    on_battle = base.clone()
    action_space = DiscreteTileActionSpace()
    action = action_space.encode_action(0, 9, 10, 0)
    actions = (action, action_space.no_op_action)
    _apply_python_joint_actions(off, action_space, actions)
    assert off.step_logic_ticks(32) == 32
    shadow = ResidentCompleteTickRuntime(
        shadow_battle,
        RustBattleMode.SHADOW,
        action_ingress=True,
        python_action_applier=action_space.apply_action,
    )
    on = ResidentCompleteTickRuntime(
        on_battle,
        RustBattleMode.ON,
        action_ingress=True,
        python_action_applier=action_space.apply_action,
    )

    shadow_result = shadow.apply_joint_actions_and_advance(*actions, 32)
    on_result = on.apply_joint_actions_and_advance(*actions, 32)

    assert shadow_result.action_success == on_result.action_success == {0: True, 1: True}
    assert python_resident_semantic_snapshot(shadow_battle) == (
        python_resident_semantic_snapshot(off)
    )
    assert python_resident_semantic_snapshot(on_battle) == (
        python_resident_semantic_snapshot(off)
    )
    assert shadow.status.shadow_mismatches == 0
    count = 6 if card_name == "GoblinGang" else 3
    _assert_stats_aliases(
        card_name,
        list(on_battle.entities.values())[-count:],
        fresh=False,
    )
