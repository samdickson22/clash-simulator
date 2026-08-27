from __future__ import annotations

import copy
import inspect
from dataclasses import fields
from typing import Any

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.torch_sim.catalog import TensorCardCatalog
from clasher.torch_sim.simple_policy_mechanics import (
    FAST_VISIBILITY_FADE_WHEN_IDLE,
    FAST_VISIBILITY_HIDE_WHEN_IDLE,
    FAST_VISIBILITY_NONE,
    FAST_VISIBILITY_UNSUPPORTED,
    FastPolicyMechanicCatalog,
    FastPolicyMechanicState,
    fast_policy_visibility_view,
    step_fast_policy_visibility_,
)


def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    return torch.device(name)


def _catalog(
    device_name: str,
) -> tuple[FastPolicyMechanicCatalog, TensorCardCatalog, dict[str, int]]:
    device = _device(device_name)
    loader = CardDataLoader()
    core = TensorCardCatalog.compile(
        loader,
        ["Knight", "RoyalGhost", "Tesla"],
        device=device,
    )
    return FastPolicyMechanicCatalog.compile(core, loader), core, core.name_to_id


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_visibility_catalog_compiles_exact_serialized_profiles(
    device_name: str,
) -> None:
    catalog, _, ids = _catalog(device_name)
    ordinary = ids["Knight"]
    fade = ids["RoyalGhost"]
    hide = ids["Tesla"]

    assert int(catalog.visibility_kind[ordinary]) == FAST_VISIBILITY_NONE
    assert bool(catalog.profile_supported[ordinary])
    assert not bool(catalog.declares_visibility[ordinary])

    assert int(catalog.visibility_kind[fade]) == FAST_VISIBILITY_FADE_WHEN_IDLE
    assert bool(catalog.profile_supported[fade])
    assert int(catalog.fade_delay_ticks[fade]) == 40
    assert bool(catalog.fade_use_attack_range[fade])
    assert bool(catalog.area_receivable_while_invisible[fade])

    assert int(catalog.visibility_kind[hide]) == FAST_VISIBILITY_HIDE_WHEN_IDLE
    assert bool(catalog.profile_supported[hide])
    assert int(catalog.hide_delay_ticks[hide]) == 16
    assert int(catalog.rise_time_ticks[hide]) == 16
    assert not bool(catalog.area_receivable_while_invisible[hide])


def test_declared_visibility_with_missing_serialized_scalar_fails_closed() -> None:
    loader = CardDataLoader()
    core = TensorCardCatalog.compile(loader, ["Tesla"])
    original = loader.get_card("Tesla")
    assert original is not None
    malformed = copy.deepcopy(original)
    raw = copy.deepcopy(malformed._raw_entry)
    character = raw["summonCharacterData"]
    character.pop("hideTimeMS", None)
    character.pop("hideTimeMs", None)
    malformed._raw_entry = raw

    class Loader:
        def get_card(self, _name: str) -> Any:
            return malformed

    catalog = FastPolicyMechanicCatalog.compile(core, Loader())  # type: ignore[arg-type]
    card = core.name_to_id["Tesla"]

    assert bool(catalog.declares_visibility[card])
    assert not bool(catalog.profile_supported[card])
    assert int(catalog.visibility_kind[card]) == FAST_VISIBILITY_UNSUPPORTED
    assert int(catalog.hide_delay_ticks[card]) == 0
    assert int(catalog.rise_time_ticks[card]) == 0


def _planes(
    device_name: str,
) -> tuple[
    FastPolicyMechanicCatalog,
    FastPolicyMechanicState,
    dict[str, int],
    dict[str, torch.Tensor],
]:
    catalog, _, ids = _catalog(device_name)
    device = catalog.device
    state = FastPolicyMechanicState.empty(1, max_entities=3, device=device)
    planes = {
        "active": torch.ones((1, 3), dtype=torch.bool, device=device),
        "stable_id": torch.tensor([[11, 12, 13]], device=device),
        "card_id": torch.tensor(
            [[ids["RoyalGhost"], ids["Tesla"], ids["Knight"]]],
            device=device,
        ),
        "deployed": torch.ones((1, 3), dtype=torch.bool, device=device),
        "attack_started": torch.zeros((1, 3), dtype=torch.bool, device=device),
        "has_attack_range_target": torch.zeros((1, 3), dtype=torch.bool, device=device),
        "has_attack_target": torch.zeros((1, 3), dtype=torch.bool, device=device),
        "stunned": torch.zeros((1, 3), dtype=torch.bool, device=device),
    }
    initialized = state.initialize_spawned_(
        catalog,
        stable_id=planes["stable_id"],
        card_id=planes["card_id"],
        spawned=planes["active"],
    )
    assert initialized.initialized.all()
    assert not initialized.invalid_identity.any()
    assert not initialized.profile_rejected.any()
    return catalog, state, ids, planes


def _step(
    catalog: FastPolicyMechanicCatalog,
    state: FastPolicyMechanicState,
    planes: dict[str, torch.Tensor],
):
    return step_fast_policy_visibility_(catalog, state, **planes)


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_inactivity_visibility_reveal_hold_and_exact_fade_boundary(
    device_name: str,
) -> None:
    catalog, state, _, planes = _planes(device_name)
    initial = fast_policy_visibility_view(
        catalog,
        state,
        active=planes["active"],
        stable_id=planes["stable_id"],
        card_id=planes["card_id"],
    )
    assert bool(initial.invisible[0, 0])
    assert bool(initial.target_unavailable[0, 0])
    assert bool(initial.secondary_targetable[0, 0])
    assert bool(initial.direct_effect_receivable[0, 0])
    assert bool(initial.area_receivable[0, 0])
    assert not bool(initial.special_active[0, 0])

    planes["attack_started"][0, 0] = True
    revealed = _step(catalog, state, planes)
    assert bool(revealed.became_visible[0, 0])
    assert not bool(revealed.view.invisible[0, 0])
    assert int(state.fade_elapsed_ticks[0, 0]) == 0
    planes["attack_started"].zero_()

    planes["has_attack_range_target"][0, 0] = True
    for _ in range(50):
        held = _step(catalog, state, planes)
    assert not bool(held.view.invisible[0, 0])
    assert int(state.fade_elapsed_ticks[0, 0]) == 0

    planes["has_attack_range_target"].zero_()
    for _ in range(39):
        fading = _step(catalog, state, planes)
    assert not bool(fading.view.invisible[0, 0])
    assert int(state.fade_elapsed_ticks[0, 0]) == 39
    faded = _step(catalog, state, planes)
    assert bool(faded.became_invisible[0, 0])
    assert bool(faded.view.target_unavailable[0, 0])
    assert bool(faded.view.secondary_targetable[0, 0])
    assert bool(faded.view.area_receivable[0, 0])


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_idle_hide_boundary_freeze_pause_and_target_reveal(device_name: str) -> None:
    catalog, state, _, planes = _planes(device_name)
    hide_slot = 1

    for _ in range(7):
        visible = _step(catalog, state, planes)
    planes["stunned"][0, hide_slot] = True
    for _ in range(20):
        frozen = _step(catalog, state, planes)
    assert int(state.hide_phase_ticks[0, hide_slot]) == 7
    assert not bool(frozen.view.hidden[0, hide_slot])

    planes["stunned"].zero_()
    for _ in range(8):
        visible = _step(catalog, state, planes)
    assert int(state.hide_phase_ticks[0, hide_slot]) == 15
    assert not bool(visible.view.hidden[0, hide_slot])
    hidden = _step(catalog, state, planes)
    assert bool(hidden.became_hidden[0, hide_slot])
    assert bool(hidden.clear_source_target[0, hide_slot])
    assert bool(hidden.view.special_active[0, hide_slot])
    assert bool(hidden.view.target_unavailable[0, hide_slot])
    assert not bool(hidden.view.secondary_targetable[0, hide_slot])
    assert not bool(hidden.view.direct_effect_receivable[0, hide_slot])
    assert bool(hidden.view.effect_receivable_affects_hidden[0, hide_slot])

    planes["has_attack_target"][0, hide_slot] = True
    revealed = _step(catalog, state, planes)
    assert bool(revealed.became_revealed[0, hide_slot])
    assert not bool(revealed.view.hidden[0, hide_slot])
    assert not bool(revealed.view.target_unavailable[0, hide_slot])


@pytest.mark.parametrize("device_name", ("cpu", "cuda"))
def test_replay_death_slot_reuse_and_row_reset_are_identity_safe(
    device_name: str,
) -> None:
    catalog, state, ids, planes = _planes(device_name)
    replay = state.clone()
    replay_planes = {name: value.clone() for name, value in planes.items()}
    for _ in range(16):
        first = _step(catalog, state, planes)
        second = _step(catalog, replay, replay_planes)
    for descriptor in fields(state):
        if descriptor.name != "device":
            assert torch.equal(
                getattr(state, descriptor.name), getattr(replay, descriptor.name)
            )
    assert torch.equal(first.view.hidden, second.view.hidden)

    planes["active"][0, 1] = False
    death = _step(catalog, state, planes)
    assert bool(death.stale_cleared[0, 1])
    assert int(state.bound_stable_id[0, 1]) == 0
    assert not bool(state.hidden[0, 1])

    planes["active"][0, 1] = True
    planes["stable_id"][0, 1] = 99
    planes["card_id"][0, 1] = ids["RoyalGhost"]
    spawned = torch.zeros_like(planes["active"])
    spawned[0, 1] = True
    initialized = state.initialize_spawned_(
        catalog,
        stable_id=planes["stable_id"],
        card_id=planes["card_id"],
        spawned=spawned,
    )
    assert bool(initialized.initialized[0, 1])
    assert bool(state.invisible[0, 1])
    assert int(state.fade_elapsed_ticks[0, 1]) == 40

    state.reset_rows_(torch.ones(1, dtype=torch.bool, device=state.device))
    assert not bool(state.bound_stable_id.any())
    assert not bool(state.bound_card_id.any())
    assert not bool(state.invisible.any())
    assert not bool(state.hidden.any())


def test_unsupported_profile_is_runtime_fail_closed_if_injected() -> None:
    loader = CardDataLoader()
    core = TensorCardCatalog.compile(loader, ["Tesla"])
    original = loader.get_card("Tesla")
    assert original is not None
    malformed = copy.deepcopy(original)
    raw = copy.deepcopy(malformed._raw_entry)
    raw["summonCharacterData"].pop("upTimeMS", None)
    raw["summonCharacterData"].pop("upTimeMs", None)
    malformed._raw_entry = raw

    class Loader:
        def get_card(self, _name: str) -> Any:
            return malformed

    catalog = FastPolicyMechanicCatalog.compile(core, Loader())  # type: ignore[arg-type]
    card = core.name_to_id["Tesla"]
    state = FastPolicyMechanicState.empty(1, max_entities=1)
    stable_id = torch.ones((1, 1), dtype=torch.int64)
    card_id = torch.full((1, 1), card, dtype=torch.int64)
    active = torch.ones((1, 1), dtype=torch.bool)
    initialized = state.initialize_spawned_(
        catalog,
        stable_id=stable_id,
        card_id=card_id,
        spawned=active,
    )
    view = fast_policy_visibility_view(
        catalog,
        state,
        active=active,
        stable_id=stable_id,
        card_id=card_id,
    )

    assert bool(initialized.profile_rejected[0, 0])
    assert bool(view.profile_rejected[0, 0])
    assert bool(view.target_unavailable[0, 0])
    assert bool(view.combat_blocked[0, 0])
    assert bool(view.movement_blocked[0, 0])
    assert not bool(view.direct_effect_receivable[0, 0])


def test_visibility_hot_path_has_no_sync_compaction_or_card_dispatch() -> None:
    source = "\n".join(
        inspect.getsource(value)
        for value in (
            FastPolicyMechanicState.initialize_spawned_,
            FastPolicyMechanicState.refresh_identity_,
            fast_policy_visibility_view,
            step_fast_policy_visibility_,
        )
    )
    for forbidden in (
        ".item(",
        ".tolist(",
        ".cpu(",
        ".nonzero(",
        "argsort(",
        "topk(",
    ):
        assert forbidden not in source
    for card_name in ("RoyalGhost", "Tesla", "ArcherQueen"):
        assert card_name not in source
