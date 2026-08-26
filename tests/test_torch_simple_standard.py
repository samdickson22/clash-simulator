from __future__ import annotations

import pytest
import torch

from clasher.data import CardDataLoader, load_princess_tower_character_data
from clasher.torch_sim.simple_standard import (
    STANDARD_DOUBLE_ELIXIR_TICK,
    STANDARD_REGULATION_TICK,
    STANDARD_TIEBREAK_TICK,
    STANDARD_TRIPLE_ELIXIR_TICK,
    SimpleStandardSetup,
    compile_standard_simple_setup,
)

PUBLIC_ROOTS = ("Knight", "Balloon", "Golem", "Lumberjack")


def _setup(device_name: str) -> SimpleStandardSetup:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return compile_standard_simple_setup(
        CardDataLoader(),
        PUBLIC_ROOTS,
        device=device_name,
        canonical_lane_globals=True,
    )


def _typed_lookups(setup: SimpleStandardSetup) -> tuple[torch.Tensor, torch.Tensor]:
    fast = setup.spawn_blueprints.fast_cards
    entity = torch.zeros((2, fast.size), dtype=torch.int64, device=setup.device)
    hand = torch.zeros(fast.size, dtype=torch.int64, device=setup.device)
    for card_id in range(1, fast.size):
        kind = int(fast.kind[card_id])
        if kind >= 0:
            entity[kind, card_id] = 1_000 + card_id
        if bool(setup.public_root_mask[card_id]):
            hand[card_id] = 2_000 + card_id
    return entity, hand


def _deck(name: str) -> list[list[list[str]]]:
    return [[[name] * 8, [name] * 8]]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_standard_setup_constructs_native_runtime_from_authoritative_data(
    device_name: str,
) -> None:
    setup = _setup(device_name)
    entity_lookup, hand_lookup = _typed_lookups(setup)

    assert (
        STANDARD_DOUBLE_ELIXIR_TICK,
        STANDARD_REGULATION_TICK,
        STANDARD_TRIPLE_ELIXIR_TICK,
        STANDARD_TIEBREAK_TICK,
    ) == (2_400, 3_600, 4_800, 6_000)
    assert setup.rules.regulation_ticks == STANDARD_REGULATION_TICK
    assert setup.rules.tiebreak_ticks == STANDARD_TIEBREAK_TICK
    assert setup.canonical_lane_globals is True
    assert setup.public_root_names == ("Balloon", "Golem", "Knight", "Lumberjack")
    assert setup.supported_public_root_names == (
        "Balloon",
        "Golem",
        "Knight",
        "Lumberjack",
    )
    balloon = setup.cards.name_to_id["Balloon"]
    golem = setup.cards.name_to_id["Golem"]
    knight = setup.cards.name_to_id["Knight"]
    lumberjack = setup.cards.name_to_id["Lumberjack"]
    assert bool(setup.public_root_mask[balloon])
    assert bool(setup.public_root_mask[knight])
    assert bool(setup.supported_public_root_mask[balloon])
    assert bool(setup.supported_public_root_mask[golem])
    assert bool(setup.supported_public_root_mask[knight])
    assert bool(setup.supported_public_root_mask[lumberjack])

    princess = load_princess_tower_character_data(CardDataLoader().data_file)
    assert setup.tower_spec.x_units.tolist() == [
        [3_500, 14_500, 9_000],
        [3_500, 14_500, 9_000],
    ]
    assert setup.tower_spec.y_units.tolist() == [
        [6_500, 6_500, 2_500],
        [25_500, 25_500, 29_500],
    ]
    assert setup.tower_spec.range_units[:, :2].unique().item() == int(princess["range"])

    runtime = setup.create_runtime(
        _deck("Knight"),
        entity_token_lookup=entity_lookup,
        hand_token_lookup=hand_lookup,
        canonical_lane_globals=True,
        max_entities=16,
        max_effects=16,
    )
    assert runtime.device == torch.device(device_name)
    assert runtime.double_elixir_tick == 2_400
    assert runtime.triple_elixir_tick == 4_800
    assert runtime.outcomes.rules.regulation_ticks == 3_600
    assert runtime.outcomes.rules.tiebreak_ticks == 6_000
    assert runtime.spawn_blueprints is setup.spawn_blueprints
    assert runtime.observe().actor.hand_ids.shape == (1, 2, 5)
    balloon_runtime = setup.create_runtime(
        _deck("Balloon"),
        entity_token_lookup=entity_lookup,
        hand_token_lookup=hand_lookup,
        canonical_lane_globals=True,
        max_entities=16,
        max_effects=16,
    )
    assert balloon_runtime.spawn_blueprints is setup.spawn_blueprints


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_standard_setup_admits_complete_roots_and_rejects_nonpublic_decks(
    device_name: str,
) -> None:
    setup = _setup(device_name)
    entity_lookup, hand_lookup = _typed_lookups(setup)

    lumberjack = setup.create_runtime(
        _deck("Lumberjack"),
        entity_token_lookup=entity_lookup,
        hand_token_lookup=hand_lookup,
        canonical_lane_globals=True,
    )
    assert bool(lumberjack.observe().legal_mask[:, :, :-1].any())
    with pytest.raises(ValueError, match="not compiled public roots.*Arrows"):
        setup.create_runtime(
            _deck("Arrows"),
            entity_token_lookup=entity_lookup,
            hand_token_lookup=hand_lookup,
            canonical_lane_globals=True,
        )
    with pytest.raises(ValueError, match="canonical_lane_globals=true"):
        setup.create_runtime(
            _deck("Knight"),
            entity_token_lookup=entity_lookup,
            hand_token_lookup=hand_lookup,
            canonical_lane_globals=False,
        )


def test_standard_setup_refuses_noncanonical_compilation() -> None:
    with pytest.raises(ValueError, match="canonical_lane_globals=true"):
        compile_standard_simple_setup(
            CardDataLoader(),
            ("Knight",),
            device="cpu",
            canonical_lane_globals=False,
        )


def test_standard_setup_uses_optional_runtime_path_for_zero_blueprints() -> None:
    setup = compile_standard_simple_setup(
        CardDataLoader(),
        ("Knight",),
        device="cpu",
        canonical_lane_globals=True,
    )
    entity_lookup, hand_lookup = _typed_lookups(setup)

    assert setup.spawn_blueprints.blueprint_count == 0
    runtime = setup.create_runtime(
        _deck("Knight"),
        entity_token_lookup=entity_lookup,
        hand_token_lookup=hand_lookup,
        canonical_lane_globals=True,
        max_entities=16,
        max_effects=16,
    )

    assert runtime.spawn_blueprints is None
    assert runtime.observe().actor.hand_ids.shape == (1, 2, 5)
