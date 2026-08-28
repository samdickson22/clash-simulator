from __future__ import annotations

import inspect
import math
from collections.abc import Sequence
from dataclasses import fields, replace

import numpy as np
import pytest
import torch

from clasher.arena import TileGrid
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.rl.simple_tensor_collector import (
    SimpleTensorCollector,
    SimpleTensorPolicyBoundary,
    SimpleTensorPolicyDecision,
)
from clasher.torch_sim.actions import ABILITY_ACTION, NO_OP_ACTION
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.resident_outputs import TensorPublicStructuredObservation
from clasher.torch_sim.simple_catalog import FastCardCatalog
from clasher.torch_sim.simple_outcomes import FastMatchRules, FastTowerSpec
from clasher.torch_sim.simple_public_mask import (
    SIMPLE_PUBLIC_MASK_NO_OP,
    SimpleCollectorPublicMaskV2Provider,
    SimplePublicMaskContractError,
    SimplePublicMaskTypedTables,
    SimplePublicMaskV2Provider,
)
from clasher.torch_sim.simple_reward_v2 import SimpleRewardV2Config
from clasher.torch_sim.simple_rollout import SimpleGymRolloutBridge
from clasher.torch_sim.simple_runtime import SimpleGymRuntime
from clasher.torch_sim.simple_standard import compile_standard_simple_setup

TOKEN_KEYS = (
    "<pad>",
    "<unknown>",
    "card_action:Knight",
    "card_action:Cannon",
    "card_action:Fireball",
    "troop_body:Knight",
    "building_body:Cannon",
    "troop_body:ArcherQueen",
    "tower:KingTower",
)


def _compile_tables(
    *,
    token_keys: Sequence[str] = TOKEN_KEYS,
    hand_playable: Sequence[bool] = (
        False,
        False,
        True,
        True,
        True,
        False,
        False,
        False,
        False,
    ),
) -> SimplePublicMaskTypedTables:
    return SimplePublicMaskTypedTables.compile(
        token_keys=token_keys,
        hand_playable=hand_playable,
        elixir_cost=(0.0, 0.0, 3.0, 3.0, 4.0, 0.0, 0.0, 0.0, 0.0),
        is_spell=(False, False, False, False, True, False, False, False, False),
        non_rolling_spell=(
            False,
            False,
            False,
            False,
            True,
            False,
            False,
            False,
            False,
        ),
        is_building=(False, False, False, True, False, False, True, False, True),
        can_deploy_enemy_side=(False,) * len(TOKEN_KEYS),
        deploy_margin_tiles=(0,) * len(TOKEN_KEYS),
        deploy_radius_tiles=(0.5,) * len(TOKEN_KEYS),
        blocker_radius_tiles=(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.75, 0.5, 1.0),
        ability_supported=(
            False,
            False,
            False,
            False,
            False,
            False,
            False,
            True,
            False,
        ),
        ability_elixir_cost=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
        blocked_tiles=tuple(TileGrid.BLOCKED_TILES),
        authority="test-authoritative-public-action-mask-v2",
    )


def _tables(device_name: str = "cpu") -> SimplePublicMaskTypedTables:
    tables = _compile_tables()
    return tables.to(device_name)


def _runtime(device_name: str = "cpu") -> SimpleGymRuntime:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    if device_name == "mps" and not torch.backends.mps.is_available():
        pytest.skip("MPS unavailable")
    device = torch.device(device_name)
    if device.type == "mps":
        setup = compile_standard_simple_setup(
            CardDataLoader(),
            ("Knight", "Cannon", "Fireball"),
            device=device,
            canonical_lane_globals=True,
        )
        fast = setup.spawn_blueprints.fast_cards
        knight = setup.cards.name_to_id["Knight"]
        cannon = setup.cards.name_to_id["Cannon"]
        fireball = setup.cards.name_to_id["Fireball"]
        hand_lookup = torch.zeros(fast.size, dtype=torch.int64, device=setup.device)
        hand_lookup[knight] = 2
        hand_lookup[cannon] = 3
        hand_lookup[fireball] = 4
        entity_lookup = torch.zeros(
            (5, fast.size), dtype=torch.int64, device=setup.device
        )
        entity_lookup[:, 0] = 8
        entity_lookup[0, knight] = 5
        entity_lookup[1, cannon] = 6
        first_names = ("Knight", "Cannon", "Fireball", "Knight") * 2
        second_names = ("Cannon", "Knight", "Fireball", "Cannon") * 2
        return setup.create_runtime(
            [[first_names, second_names], [second_names, first_names]],
            entity_token_lookup=entity_lookup,
            hand_token_lookup=hand_lookup,
            canonical_lane_globals=True,
            max_entities=24,
            max_effects=16,
            include_privileged_critic=True,
        )
    full = TensorCardCatalog.compile(
        BattleState().card_loader,
        ("Knight", "Cannon", "Fireball"),
        device=device,
    )
    fast = FastCardCatalog.from_tensor_catalog(full)
    knight = full.name_to_id["Knight"]
    cannon = full.name_to_id["Cannon"]
    fireball = full.name_to_id["Fireball"]
    first = (knight, cannon, fireball, knight, cannon, fireball, knight, cannon)
    second = (cannon, knight, fireball, cannon, knight, fireball, cannon, knight)
    decks = torch.tensor(
        ((first, second), (second, first)), dtype=torch.int64, device=device
    )
    towers = FastTowerSpec(
        card_id=torch.zeros((2, 3), dtype=torch.int64, device=device),
        x_units=torch.tensor(
            ((3_500, 14_500, 9_000), (3_500, 14_500, 9_000)),
            dtype=torch.int32,
            device=device,
        ),
        y_units=torch.tensor(
            ((6_500, 6_500, 2_500), (25_500, 25_500, 29_500)),
            dtype=torch.int32,
            device=device,
        ),
        hitpoints=torch.tensor(
            ((2_000.0, 2_000.0, 3_000.0),) * 2,
            dtype=torch.float32,
            device=device,
        ),
        damage=torch.zeros((2, 3), dtype=torch.float32, device=device),
        range_units=torch.full((2, 3), 7_500, dtype=torch.int32, device=device),
        sight_range_units=torch.full((2, 3), 9_500, dtype=torch.int32, device=device),
        hit_cooldown_ticks=torch.full((2, 3), 16, dtype=torch.int32, device=device),
    )
    hand_lookup = torch.zeros(fast.size, dtype=torch.int64, device=device)
    hand_lookup[knight] = 2
    hand_lookup[cannon] = 3
    hand_lookup[fireball] = 4
    entity_lookup = torch.zeros((5, fast.size), dtype=torch.int64, device=device)
    entity_lookup[:, 0] = 8
    entity_lookup[0, knight] = 5
    entity_lookup[1, cannon] = 6
    return SimpleGymRuntime(
        decks,
        fast,
        towers,
        FastMatchRules(regulation_ticks=40, tiebreak_ticks=120),
        entity_token_lookup=entity_lookup,
        hand_token_lookup=hand_lookup,
        max_entities=24,
        max_effects=16,
        include_privileged_critic=True,
    )


def _reference_mask(
    actor: TensorPublicStructuredObservation,
    tables: SimplePublicMaskTypedTables,
) -> torch.Tensor:
    """Literal NumPy form of the authoritative public-mask-v2 algorithm."""

    entity_ids = actor.entity_ids.detach().cpu().numpy()
    entity_features = actor.entity_features.detach().cpu().numpy()
    entity_mask = actor.entity_mask.detach().cpu().numpy()
    hand_ids = actor.hand_ids.detach().cpu().numpy()
    global_features = actor.global_features.detach().cpu().numpy()
    playable = tables.hand_playable.detach().cpu().numpy()
    cost = tables.elixir_cost.detach().cpu().numpy()
    is_spell = tables.is_spell.detach().cpu().numpy()
    non_rolling = tables.non_rolling_spell.detach().cpu().numpy()
    is_building = tables.is_building.detach().cpu().numpy()
    enemy_side = tables.can_deploy_enemy_side.detach().cpu().numpy()
    margin = tables.deploy_margin_tiles.detach().cpu().numpy()
    deploy_radius = tables.deploy_radius_tiles.detach().cpu().numpy()
    blocker_radius = tables.blocker_radius_tiles.detach().cpu().numpy()
    non_blocked = tables.non_blocked_tiles.detach().cpu().numpy()
    base_zone = tables.base_deploy_zone.detach().cpu().numpy()
    left_extension = tables.left_tower_extension.detach().cpu().numpy()
    right_extension = tables.right_tower_extension.detach().cpu().numpy()
    ability_supported = tables.ability_supported.detach().cpu().numpy()
    ability_cost = tables.ability_elixir_cost.detach().cpu().numpy()
    result = np.zeros(
        (*hand_ids.shape[:2], SIMPLE_PUBLIC_MASK_NO_OP + 2), dtype=np.bool_
    )
    result[..., SIMPLE_PUBLIC_MASK_NO_OP] = True
    token_count = len(tables.token_keys)
    for batch in range(hand_ids.shape[0]):
        for seat in range(2):
            zone = base_zone.copy()
            if global_features[batch, seat, 11] <= 1.0e-4:
                zone |= left_extension
            if global_features[batch, seat, 12] <= 1.0e-4:
                zone |= right_extension
            blockers: list[tuple[float, float, float, float]] = []
            for entity in np.flatnonzero(entity_mask[batch, seat]).tolist():
                if entity_features[batch, seat, entity, 5] <= 0.5:
                    continue
                token = int(entity_ids[batch, seat, entity])
                if not 0 <= token < token_count:
                    continue
                radius = float(blocker_radius[token])
                half = max(1, math.ceil(max(0.0, radius) * 2.0) + 1) / 2.0 + 0.5
                blockers.append(
                    (
                        float(entity_features[batch, seat, entity, 0]) * 18.0,
                        float(entity_features[batch, seat, entity, 1]) * 32.0,
                        max(0.5, radius),
                        half,
                    )
                )
            elixir = float(global_features[batch, seat, 5]) * 10.0
            ability_candidates: list[int] = []
            for entity in np.flatnonzero(entity_mask[batch, seat]).tolist():
                token = int(entity_ids[batch, seat, entity])
                if (
                    0 < token < token_count
                    and ability_supported[token]
                    and entity_features[batch, seat, entity, 2] > 0.5
                    and entity_features[batch, seat, entity, 9] > 0.0
                    and entity_features[batch, seat, entity, 12] <= 0.5
                ):
                    ability_candidates.append(token)
            if (
                len(ability_candidates) == 1
                and global_features[batch, seat, 14] <= 1.0e-4
                and global_features[batch, seat, 15] <= 1.0e-4
                and ability_cost[ability_candidates[0]] <= elixir + 1.0e-6
            ):
                result[batch, seat, ABILITY_ACTION] = True
            for slot in range(4):
                token = int(hand_ids[batch, seat, slot])
                if not 0 < token < token_count or not playable[token]:
                    continue
                if float(cost[token]) > elixir + 1.0e-6:
                    continue
                candidates = (
                    non_blocked
                    if non_rolling[token] or enemy_side[token]
                    else zone & non_blocked
                )
                for tile in np.flatnonzero(candidates).tolist():
                    x = float(tile % 18) + 0.5
                    y = float(tile // 18) + 0.5
                    if margin[token] and not margin[token] <= x < 18 - margin[token]:
                        continue
                    occupied = False
                    if not is_spell[token]:
                        body = float(deploy_radius[token])
                        building_half = (
                            max(1, math.ceil(max(0.0, body) * 2.0) + 1) / 2.0
                        )
                        for blocker_x, blocker_y, radius, half in blockers:
                            if is_building[token]:
                                occupied |= (
                                    abs(x - blocker_x) < building_half + half
                                    and abs(y - blocker_y) < building_half + half
                                )
                            else:
                                occupied |= (x - blocker_x) ** 2 + (
                                    y - blocker_y
                                ) ** 2 < (body + radius) ** 2 or (
                                    abs(x - blocker_x) < half
                                    and abs(y - blocker_y) < half
                                )
                            if occupied:
                                break
                    if not occupied:
                        result[batch, seat, slot * 18 * 32 + tile] = True
    return torch.as_tensor(result, dtype=torch.bool, device=actor.hand_ids.device)


@pytest.mark.parametrize("device_name", ("cpu", "cuda", "mps"))
def test_tensor_mask_matches_free_running_numpy_trace(device_name: str) -> None:
    runtime = _runtime(device_name)
    tables = _tables(device_name)
    provider = SimplePublicMaskV2Provider(tables)
    unique_masks: set[bytes] = set()

    for _ in range(8):
        observation = runtime.observe()
        actual = provider.build(observation.actor)
        expected = _reference_mask(observation.actor, tables)
        assert torch.equal(actual.masks, expected)
        unique_masks.add(actual.masks.detach().cpu().numpy().tobytes())
        placement = actual.masks[..., :NO_OP_ACTION]
        first = placement.to(torch.int64).argmax(dim=-1)
        actions = torch.where(
            placement.any(dim=-1), first, torch.full_like(first, NO_OP_ACTION)
        )
        runtime.step_tick(actions)

    assert len(unique_masks) >= 3
    assert actual.contract_version == 2
    assert actual.semantics_digest == tables.semantics_digest
    assert actual.semantics["uses_simulator_legal_mask"] is False
    assert actual.semantics["uses_critic"] is False
    assert actual.semantics["uses_labels"] is False


class _NoopPolicy:
    def __call__(
        self, boundary: SimpleTensorPolicyBoundary
    ) -> SimpleTensorPolicyDecision:
        return SimpleTensorPolicyDecision(
            actions=torch.full(
                boundary.previous_actions.shape,
                NO_OP_ACTION,
                dtype=torch.int64,
                device=boundary.previous_actions.device,
            )
        )


@pytest.mark.parametrize("device_name", ("cpu", "mps"))
def test_collector_accepts_semantics_digest_without_mask_domain_leak(
    device_name: str,
) -> None:
    runtime = _runtime(device_name)
    tables = _tables(device_name)
    provider = SimpleCollectorPublicMaskV2Provider(SimplePublicMaskV2Provider(tables))
    collector = SimpleTensorCollector(
        SimpleGymRolloutBridge(
            runtime,
            decision_interval=2,
            reward_v2_config=SimpleRewardV2Config(gamma=0.995),
            strict_reset_check=False,
        ),
        public_mask_provider=provider,
        policy=_NoopPolicy(),
    )

    batch = collector.collect(2)

    assert batch.metadata.public_action_mask_contract_version == 2
    assert batch.metadata.public_action_mask_semantics_digest == (
        tables.semantics_digest
    )
    assert not torch.equal(batch.public_action_masks, batch.legal_masks)
    assert batch.all_rows_admitted.all()
    assert not batch.fallback_rows.any()


def test_typed_lookup_is_explicit_and_fail_closed() -> None:
    with pytest.raises(SimplePublicMaskContractError, match="explicitly typed"):
        _compile_tables(token_keys=(*TOKEN_KEYS[:-1], "KingTower"))
    playable_body = [False, False, True, True, True, False, False, False, False]
    playable_body[5] = True
    with pytest.raises(SimplePublicMaskContractError, match="card_action"):
        _compile_tables(hand_playable=playable_body)
    tables = _tables()
    moved = tables.to("cpu")
    assert moved.lookup_digest == tables.lookup_digest
    assert moved.semantics_digest == tables.semantics_digest

    unsupported_cost = list(tables.ability_elixir_cost.tolist())
    unsupported_cost[5] = 1.0
    with pytest.raises(SimplePublicMaskContractError, match="zero cost"):
        replace(
            tables,
            ability_elixir_cost=torch.tensor(unsupported_cost, dtype=torch.float64),
        )
    supported_hand = list(tables.ability_supported.tolist())
    supported_hand[2] = True
    with pytest.raises(SimplePublicMaskContractError, match="not a hand action"):
        replace(
            tables,
            ability_supported=torch.tensor(supported_hand, dtype=torch.bool),
            ability_elixir_cost=torch.tensor(
                (0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0),
                dtype=torch.float64,
            ),
        )


def _actor_with_ready_queen(
    device_name: str,
) -> tuple[TensorPublicStructuredObservation, SimplePublicMaskV2Provider]:
    runtime = _runtime(device_name)
    original = runtime.observe().actor
    ids = original.entity_ids.clone()
    features = original.entity_features.clone()
    mask = original.entity_mask.clone()
    globals_ = original.global_features.clone()
    ids[..., 0] = 7
    mask[..., 0] = True
    features[..., 0, :] = 0.0
    features[:, 0, 0, 2] = 1.0
    features[:, 1, 0, 3] = 1.0
    features[..., 0, 9] = 1.0
    globals_[..., 5] = 0.6
    globals_[..., 14:16] = 0.0
    return (
        TensorPublicStructuredObservation(
            entity_ids=ids,
            entity_features=features,
            entity_mask=mask,
            hand_ids=original.hand_ids,
            global_features=globals_,
        ),
        SimplePublicMaskV2Provider(_tables(device_name)),
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_ability_uses_only_actor_visible_typed_state_and_fails_closed(
    device_name: str,
) -> None:
    actor, provider = _actor_with_ready_queen(device_name)
    expected = torch.tensor(
        ((True, False), (True, False)),
        dtype=torch.bool,
        device=actor.hand_ids.device,
    )
    assert torch.equal(provider.build(actor).masks[..., ABILITY_ACTION], expected)

    stunned_entities = actor.entity_features.clone()
    stunned_entities[:, 0, 0, 14] = 1.0
    stunned = replace(actor, entity_features=stunned_entities)
    assert provider.build(stunned).masks[:, 0, ABILITY_ACTION].all()

    for feature, index in (("global", 14), ("global", 15), ("entity", 12)):
        globals_ = actor.global_features.clone()
        entities = actor.entity_features.clone()
        if feature == "global":
            globals_[:, 0, index] = 0.25
        else:
            entities[:, 0, 0, index] = 1.0
        gated = replace(actor, global_features=globals_, entity_features=entities)
        assert not provider.build(gated).masks[:, 0, ABILITY_ACTION].any()

    poor_globals = actor.global_features.clone()
    poor_globals[:, 0, 5] = 0.05
    assert (
        not provider.build(replace(actor, global_features=poor_globals))
        .masks[:, 0, ABILITY_ACTION]
        .any()
    )

    dead_features = actor.entity_features.clone()
    dead_features[:, 0, 0, 9] = 0.0
    assert (
        not provider.build(replace(actor, entity_features=dead_features))
        .masks[:, 0, ABILITY_ACTION]
        .any()
    )

    duplicate_ids = actor.entity_ids.clone()
    duplicate_features = actor.entity_features.clone()
    duplicate_mask = actor.entity_mask.clone()
    duplicate_ids[:, 0, 1] = 7
    duplicate_features[:, 0, 1] = duplicate_features[:, 0, 0]
    duplicate_mask[:, 0, 1] = True
    duplicate = replace(
        actor,
        entity_ids=duplicate_ids,
        entity_features=duplicate_features,
        entity_mask=duplicate_mask,
    )
    assert not provider.build(duplicate).masks[:, 0, ABILITY_ACTION].any()
    assert provider.tables.semantics["ability_multiple_owner_policy"] == (
        "fail-closed-without-public-stable-owner-id"
    )


def _authority_ability_tables() -> SimplePublicMaskTypedTables:
    token_keys = (
        "<pad>",
        "<unknown>",
        "card_action:ArcherQueen",
        "card_action:Knight",
        "troop_body:ArcherQueen",
        "troop_body:Knight",
        "tower:KingTower",
    )
    return SimplePublicMaskTypedTables.compile(
        token_keys=token_keys,
        hand_playable=(False, False, True, True, False, False, False),
        elixir_cost=(0.0, 0.0, 5.0, 3.0, 0.0, 0.0, 0.0),
        is_spell=(False,) * len(token_keys),
        non_rolling_spell=(False,) * len(token_keys),
        is_building=(False, False, False, False, False, False, True),
        can_deploy_enemy_side=(False,) * len(token_keys),
        deploy_margin_tiles=(0,) * len(token_keys),
        deploy_radius_tiles=(0.5,) * len(token_keys),
        blocker_radius_tiles=(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 1.0),
        ability_supported=(False, False, False, False, True, False, False),
        ability_elixir_cost=(0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        blocked_tiles=tuple(TileGrid.BLOCKED_TILES),
        authority="serialized-archer-queen-abilityData",
    )


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_ability_bit_matches_authoritative_runtime_trace(device_name: str) -> None:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    setup = compile_standard_simple_setup(
        CardDataLoader(),
        ("ArcherQueen", "Knight"),
        device=device_name,
        canonical_lane_globals=True,
    )
    queen = setup.cards.name_to_id["ArcherQueen"]
    knight = setup.cards.name_to_id["Knight"]
    assert int(setup.ability_catalog.elixir_cost[queen]) == 1
    entity_lookup = torch.zeros(
        (5, setup.spawn_blueprints.fast_cards.size),
        dtype=torch.int64,
        device=setup.device,
    )
    entity_lookup[:, 0] = 6
    entity_lookup[0, queen] = 4
    entity_lookup[0, knight] = 5
    hand_lookup = torch.zeros(
        setup.spawn_blueprints.fast_cards.size,
        dtype=torch.int64,
        device=setup.device,
    )
    hand_lookup[queen] = 2
    hand_lookup[knight] = 3
    runtime = setup.create_runtime(
        [[["ArcherQueen", "Knight"] * 4, ["Knight"] * 8]],
        entity_token_lookup=entity_lookup,
        hand_token_lookup=hand_lookup,
        canonical_lane_globals=True,
        starting_elixir=10.0,
        max_entities=24,
        max_effects=32,
    )
    provider = SimplePublicMaskV2Provider(_authority_ability_tables().to(setup.device))
    noop = torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=setup.device)
    deploy = torch.tensor(
        [[14 * 18 + 9, NO_OP_ACTION]], dtype=torch.int64, device=setup.device
    )
    runtime.step_tick(deploy)

    became_legal = False
    for _ in range(32):
        observation = runtime.observe()
        actual = provider.build(observation.actor).masks[..., ABILITY_ACTION]
        expected = observation.legal_mask[..., ABILITY_ACTION]
        assert torch.equal(actual, expected)
        if bool(expected[0, 0]):
            became_legal = True
            break
        runtime.step_tick(noop)
    assert became_legal

    activated = runtime.step_tick(
        torch.tensor(
            [[ABILITY_ACTION, NO_OP_ACTION]],
            dtype=torch.int64,
            device=setup.device,
        )
    )
    assert activated.action_success[0, 0]
    for _ in range(12):
        observation = runtime.observe()
        actual = provider.build(observation.actor).masks[..., ABILITY_ACTION]
        expected = observation.legal_mask[..., ABILITY_ACTION]
        assert torch.equal(actual, expected)
        runtime.step_tick(noop)


def test_hot_path_has_no_host_sync_or_privileged_inputs() -> None:
    source = inspect.getsource(SimplePublicMaskV2Provider.build)
    for forbidden in (
        ".cpu(",
        ".numpy(",
        ".item(",
        ".tolist(",
        "legal_mask",
        "critic",
        "label",
    ):
        assert forbidden not in source


@pytest.mark.skipif(
    not torch.backends.mps.is_available(),
    reason="MPS unavailable",
)
def test_provider_mps_fallback_matches_float64_cpu_authority() -> None:
    actor = _runtime("cpu").observe().actor
    cpu_tables = _tables("cpu")
    expected = SimplePublicMaskV2Provider(cpu_tables).build(actor)
    mps_actor = TensorPublicStructuredObservation(
        **{
            descriptor.name: getattr(actor, descriptor.name).to("mps")
            for descriptor in fields(TensorPublicStructuredObservation)
        }
    )
    mps_tables = cpu_tables.to("mps")

    actual = SimplePublicMaskV2Provider(mps_tables).build(mps_actor)
    torch.mps.synchronize()

    assert mps_tables.device.type == "cpu"
    assert actual.masks.device.type == "mps"
    assert torch.equal(actual.masks.cpu(), expected.masks)
    assert actual.semantics_digest == expected.semantics_digest


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_provider_is_cuda_graph_capturable_after_table_move() -> None:
    runtime = _runtime("cuda")
    provider = SimplePublicMaskV2Provider(_tables("cuda"))
    actor = runtime.observe().actor
    torch.cuda.synchronize()
    provider.build(actor)
    graph = torch.cuda.CUDAGraph()

    with torch.cuda.graph(graph):
        captured = provider.build(actor).masks
    graph.replay()
    torch.cuda.synchronize()

    eager = provider.build(actor).masks
    assert torch.equal(captured, eager)
