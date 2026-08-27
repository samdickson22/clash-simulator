from __future__ import annotations

import copy
from typing import Any

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.rl.common import BOARD_WIDTH
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.simple_effects import FAST_STATUS_STUN
from clasher.torch_sim.simple_runtime import SimpleGymRuntime
from clasher.torch_sim.simple_standard import compile_standard_simple_setup

ROOTS = ("Knight", "RoyalGhost", "Tesla")


def _runtime(
    device_name: str,
    *,
    left_first: str,
) -> tuple[SimpleGymRuntime, dict[str, int]]:
    if device_name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    setup = compile_standard_simple_setup(
        CardDataLoader(),
        ROOTS,
        device=device_name,
        canonical_lane_globals=True,
    )
    fast = setup.spawn_blueprints.fast_cards
    entity = torch.zeros((2, fast.size), dtype=torch.int64, device=setup.device)
    hand = torch.zeros(fast.size, dtype=torch.int64, device=setup.device)
    for card_id in range(1, fast.size):
        kind = int(fast.kind[card_id])
        if kind >= 0:
            entity[kind, card_id] = 1_000 + card_id
        if bool(setup.public_root_mask[card_id]):
            hand[card_id] = 2_000 + card_id
    left = [left_first, "Knight", "Tesla", "RoyalGhost"] * 2
    right = ["Knight", "Tesla", "RoyalGhost", "Knight"] * 2
    runtime = setup.create_runtime(
        [[left, right]],
        entity_token_lookup=entity,
        hand_token_lookup=hand,
        canonical_lane_globals=True,
        max_entities=20,
        max_effects=32,
    )
    return runtime, setup.cards.name_to_id


def _deploy_first(runtime: SimpleGymRuntime) -> None:
    tile = 14 * BOARD_WIDTH + 9
    actions = torch.full((1, 2), tile, dtype=torch.int64, device=runtime.device)
    result = runtime.step_tick(actions)
    assert result.action_success.tolist() == [[True, True]]


def _slot(runtime: SimpleGymRuntime, card_id: int, owner: int) -> int:
    match = (
        runtime.state.active
        & (runtime.state.card_id == card_id)
        & (runtime.state.owner == owner)
    )
    assert int(match.sum()) == 1
    return int(match.to(torch.int64).argmax(dim=1)[0])


def _noop(runtime: SimpleGymRuntime) -> torch.Tensor:
    return torch.full((1, 2), NO_OP_ACTION, dtype=torch.int64, device=runtime.device)


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_ghost_runtime_reveal_melee_hold_fade_and_public_features(
    device_name: str,
) -> None:
    runtime, ids = _runtime(device_name, left_first="RoyalGhost")
    _deploy_first(runtime)
    ghost = _slot(runtime, ids["RoyalGhost"], 0)
    knight = _slot(runtime, ids["Knight"], 1)
    state = runtime.state
    state.deploy_ticks[0, ghost] = 0
    state.deploy_ticks[0, knight] = 0
    state.x_units[0, ghost] = state.x_units[0, knight] = 9_000
    state.y_units[0, ghost] = 15_000
    state.y_units[0, knight] = 16_500
    state.hp[0, ghost] = state.max_hp[0, ghost] = 1_000_000.0
    state.hp[0, knight] = state.max_hp[0, knight] = 1_000_000.0
    state.cooldown_ticks[0, ghost] = 0

    initial = runtime.observe()
    assert bool(runtime.combat._target_unavailable[0, ghost])
    assert initial.actor.entity_features[0, :, ghost, 18].tolist() == [1.0, 1.0]
    assert initial.actor.entity_mask[0, :, ghost].tolist() == [True, True]

    revealed = runtime.step_tick(_noop(runtime))
    assert bool(revealed.policy_visibility.became_visible[0, ghost])
    assert not bool(runtime.combat._target_unavailable[0, ghost])
    assert revealed.observation.actor.entity_features[0, :, ghost, 18].tolist() == [
        0.0,
        0.0,
    ]

    state.cooldown_ticks[0, ghost] = 10_000
    for _ in range(45):
        held = runtime.step_tick(_noop(runtime))
    assert not bool(held.policy_visibility.view.invisible[0, ghost])
    assert int(runtime.policy_mechanics.fade_elapsed_ticks[0, ghost]) == 0

    runtime.entity_status_kind[0, ghost] = FAST_STATUS_STUN
    runtime.entity_status_ticks[0, ghost] = 100
    state.y_units[0, knight] = 30_000
    for _ in range(39):
        fading = runtime.step_tick(_noop(runtime))
    assert not bool(fading.policy_visibility.view.invisible[0, ghost])
    assert int(runtime.policy_mechanics.fade_elapsed_ticks[0, ghost]) == 39
    faded = runtime.step_tick(_noop(runtime))
    assert bool(faded.policy_visibility.became_invisible[0, ghost])
    assert bool(faded.policy_visibility.view.secondary_targetable[0, ghost])
    assert bool(faded.policy_visibility.view.area_receivable[0, ghost])
    assert faded.observation.actor.entity_features[0, :, ghost, 18].tolist() == [
        1.0,
        1.0,
    ]
    assert faded.observation.actor.entity_mask[0, :, ghost].tolist() == [True, True]


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_tesla_runtime_freeze_hide_reveal_targeting_and_reset(device_name: str) -> None:
    runtime, ids = _runtime(device_name, left_first="Tesla")
    _deploy_first(runtime)
    tesla = _slot(runtime, ids["Tesla"], 0)
    knight = _slot(runtime, ids["Knight"], 1)
    state = runtime.state
    state.deploy_ticks[0, tesla] = 0
    state.deploy_ticks[0, knight] = 0
    state.x_units[0, tesla] = state.x_units[0, knight] = 9_000
    state.y_units[0, tesla] = 15_000
    state.y_units[0, knight] = 30_000
    state.hp[0, tesla] = state.max_hp[0, tesla] = 1_000_000.0
    state.hp[0, knight] = state.max_hp[0, knight] = 1_000_000.0

    runtime.entity_status_kind[0, tesla] = FAST_STATUS_STUN
    runtime.entity_status_ticks[0, tesla] = 100
    for _ in range(10):
        frozen = runtime.step_tick(_noop(runtime))
    assert int(runtime.policy_mechanics.hide_phase_ticks[0, tesla]) == 0
    assert not bool(frozen.policy_visibility.view.hidden[0, tesla])

    runtime.entity_status_kind[0, tesla] = 0
    runtime.entity_status_ticks[0, tesla] = 0
    for _ in range(15):
        visible = runtime.step_tick(_noop(runtime))
    assert int(runtime.policy_mechanics.hide_phase_ticks[0, tesla]) == 15
    assert not bool(visible.policy_visibility.view.hidden[0, tesla])
    hidden = runtime.step_tick(_noop(runtime))
    assert bool(hidden.policy_visibility.became_hidden[0, tesla])
    assert bool(runtime.combat._target_unavailable[0, tesla])
    assert int(state.target_id[0, tesla]) == 0
    assert hidden.observation.actor.entity_features[0, :, tesla, 17].tolist() == [
        1.0,
        1.0,
    ]
    assert hidden.observation.actor.entity_features[0, :, tesla, 19].tolist() == [
        1.0,
        1.0,
    ]
    assert hidden.observation.actor.entity_mask[0, :, tesla].tolist() == [True, True]

    state.y_units[0, knight] = 16_000
    revealed = runtime.step_tick(_noop(runtime))
    assert bool(revealed.policy_visibility.became_revealed[0, tesla])
    assert not bool(runtime.combat._target_unavailable[0, tesla])
    assert int(state.target_id[0, knight]) != int(state.stable_id[0, tesla])

    runtime.reset_rows(torch.ones(1, dtype=torch.bool, device=runtime.device))
    assert not bool(runtime.policy_mechanics.bound_stable_id.any())
    assert not bool(runtime._entity_special.any())
    assert not bool(runtime._entity_invisible.any())
    assert not bool(runtime._entity_hidden.any())
    assert not bool(runtime.combat._target_unavailable.any())


def test_standard_runtime_owns_visibility_catalog_and_admission_plane() -> None:
    setup = compile_standard_simple_setup(
        CardDataLoader(),
        ROOTS,
        device="cpu",
        canonical_lane_globals=True,
    )
    for name in ROOTS:
        card = setup.cards.name_to_id[name]
        assert bool(setup.policy_mechanics.profile_supported[card])
        assert bool(setup.supported_public_root_mask[card])


def test_standard_admission_rejects_declared_malformed_visibility_profile() -> None:
    base = CardDataLoader()
    original = base.get_card("Tesla")
    assert original is not None
    malformed = copy.deepcopy(original)
    raw = copy.deepcopy(malformed._raw_entry)
    raw["summonCharacterData"].pop("upTimeMS", None)
    raw["summonCharacterData"].pop("upTimeMs", None)
    malformed._raw_entry = raw

    class Loader:
        data_file = base.data_file

        def load_card_definitions(self) -> Any:
            return base.load_card_definitions()

        def get_card(self, name: str) -> Any:
            return malformed if name == "Tesla" else base.get_card(name)

    setup = compile_standard_simple_setup(
        Loader(),  # type: ignore[arg-type]
        ROOTS,
        device="cpu",
        canonical_lane_globals=True,
    )
    tesla = setup.cards.name_to_id["Tesla"]

    assert not bool(setup.policy_mechanics.profile_supported[tesla])
    assert not bool(setup.supported_public_root_mask[tesla])
