from __future__ import annotations

import inspect
import math
from collections.abc import Sequence

import numpy as np
import pytest
import torch

from clasher.arena import TileGrid
from clasher.battle import BattleState
from clasher.rl.simple_tensor_collector import (
    SimpleTensorCollector,
    SimpleTensorPolicyBoundary,
    SimpleTensorPolicyDecision,
)
from clasher.torch_sim.actions import NO_OP_ACTION
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

TOKEN_KEYS = (
    "<pad>",
    "<unknown>",
    "card_action:Knight",
    "card_action:Cannon",
    "card_action:Fireball",
    "troop_body:Knight",
    "building_body:Cannon",
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
    ),
) -> SimplePublicMaskTypedTables:
    return SimplePublicMaskTypedTables.compile(
        token_keys=token_keys,
        hand_playable=hand_playable,
        elixir_cost=(0.0, 0.0, 3.0, 3.0, 4.0, 0.0, 0.0, 0.0),
        is_spell=(False, False, False, False, True, False, False, False),
        non_rolling_spell=(False, False, False, False, True, False, False, False),
        is_building=(False, False, False, True, False, False, True, True),
        can_deploy_enemy_side=(False,) * len(TOKEN_KEYS),
        deploy_margin_tiles=(0,) * len(TOKEN_KEYS),
        deploy_radius_tiles=(0.5,) * len(TOKEN_KEYS),
        blocker_radius_tiles=(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.75, 1.0),
        blocked_tiles=tuple(TileGrid.BLOCKED_TILES),
        authority="test-authoritative-public-action-mask-v2",
    )


def _tables(device_name: str = "cpu") -> SimplePublicMaskTypedTables:
    tables = _compile_tables()
    return tables.to(device_name)


def _runtime(device_name: str = "cpu") -> SimpleGymRuntime:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    device = torch.device(device_name)
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
        sight_range_units=torch.full(
            (2, 3), 9_500, dtype=torch.int32, device=device
        ),
        hit_cooldown_ticks=torch.full(
            (2, 3), 16, dtype=torch.int32, device=device
        ),
    )
    hand_lookup = torch.zeros(fast.size, dtype=torch.int64, device=device)
    hand_lookup[knight] = 2
    hand_lookup[cannon] = 3
    hand_lookup[fireball] = 4
    entity_lookup = torch.zeros((5, fast.size), dtype=torch.int64, device=device)
    entity_lookup[:, 0] = 7
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
    result = np.zeros((*hand_ids.shape[:2], SIMPLE_PUBLIC_MASK_NO_OP + 2), dtype=np.bool_)
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
            for slot in range(4):
                token = int(hand_ids[batch, seat, slot])
                if not 0 < token < token_count or not playable[token]:
                    continue
                if float(cost[token]) > elixir + 1.0e-6:
                    continue
                candidates = non_blocked if non_rolling[token] or enemy_side[token] else zone & non_blocked
                for tile in np.flatnonzero(candidates).tolist():
                    x = float(tile % 18) + 0.5
                    y = float(tile // 18) + 0.5
                    if margin[token] and not margin[token] <= x < 18 - margin[token]:
                        continue
                    occupied = False
                    if not is_spell[token]:
                        body = float(deploy_radius[token])
                        building_half = max(
                            1, math.ceil(max(0.0, body) * 2.0) + 1
                        ) / 2.0
                        for blocker_x, blocker_y, radius, half in blockers:
                            if is_building[token]:
                                occupied |= (
                                    abs(x - blocker_x) < building_half + half
                                    and abs(y - blocker_y) < building_half + half
                                )
                            else:
                                occupied |= (
                                    (x - blocker_x) ** 2 + (y - blocker_y) ** 2
                                    < (body + radius) ** 2
                                    or (
                                        abs(x - blocker_x) < half
                                        and abs(y - blocker_y) < half
                                    )
                                )
                            if occupied:
                                break
                    if not occupied:
                        result[batch, seat, slot * 18 * 32 + tile] = True
    return torch.as_tensor(result, dtype=torch.bool, device=actor.hand_ids.device)


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
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


def test_collector_accepts_semantics_digest_without_mask_domain_leak() -> None:
    runtime = _runtime()
    tables = _tables()
    provider = SimpleCollectorPublicMaskV2Provider(
        SimplePublicMaskV2Provider(tables)
    )
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
    playable_body = [False, False, True, True, True, False, False, False]
    playable_body[5] = True
    with pytest.raises(SimplePublicMaskContractError, match="card_action"):
        _compile_tables(hand_playable=playable_body)
    tables = _tables()
    moved = tables.to("cpu")
    assert moved.lookup_digest == tables.lookup_digest
    assert moved.semantics_digest == tables.semantics_digest


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
