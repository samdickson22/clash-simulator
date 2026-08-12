from __future__ import annotations

import pytest

from clasher import entities as entities_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Entity, Troop
from clasher.rl.determinism_check import compute_rollout_digest


def _spawn_attacker(battle: BattleState, x: float) -> Troop:
    stats = battle.card_loader.get_card("Knight")
    assert stats is not None
    return battle._spawn_entity(Troop, Position(x, 8.0), 0, stats)


def _enemy_crowns(battle: BattleState) -> dict[str, Entity]:
    return {
        str(entity._crown_tower_slot): entity
        for entity in battle.entities.values()
        if entity.player_id == 1
        and getattr(entity, "_crown_tower_slot", None) is not None
    }


@pytest.mark.parametrize(
    ("hidden_slots", "expected_slot", "validated_slots"),
    [
        ((), "left", {"left"}),
        (("left",), "right", {"left", "right"}),
        (("left", "right"), "king", {"left", "right", "king"}),
    ],
)
def test_deferred_validation_checks_only_potential_winners(
    monkeypatch: pytest.MonkeyPatch,
    hidden_slots: tuple[str, ...],
    expected_slot: str,
    validated_slots: set[str],
) -> None:
    battle = BattleState(fast_path=True)
    attacker = _spawn_attacker(battle, 3.0)
    crowns = _enemy_crowns(battle)
    for slot in hidden_slots:
        crowns[slot]._hidden_building = True
    battle._refresh_fast_path_caches()

    original = Entity._is_valid_target
    validated: list[str] = []

    def recording_valid(self: Entity, entity: Entity, **kwargs) -> bool:
        if entity in crowns.values():
            validated.append(str(entity._crown_tower_slot))
        return original(self, entity, **kwargs)

    monkeypatch.setattr(Entity, "_is_valid_target", recording_valid)
    selected = attacker.get_nearest_target(battle.entities)

    assert selected is crowns[expected_slot]
    assert set(validated) == validated_slots


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_deferred_validation_preserves_fixed_seed_rollout(
    monkeypatch: pytest.MonkeyPatch,
    engine_fast_path: str,
) -> None:
    common = {
        "seed": 8981,
        "decisions": 32,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 2048,
        "mirror_match": False,
        "quiet_engine": True,
        "engine_fast_path": engine_fast_path,
        "reward_profile": "defense-v2",
    }

    monkeypatch.setattr(
        entities_module,
        "_USE_DEFERRED_CROWN_FALLBACK_VALIDATION",
        False,
    )
    eager = compute_rollout_digest(**common)
    monkeypatch.setattr(
        entities_module,
        "_USE_DEFERRED_CROWN_FALLBACK_VALIDATION",
        True,
    )
    deferred = compute_rollout_digest(**common)

    assert deferred.sha256 == eager.sha256
    assert deferred.mask_shadow_checks == eager.mask_shadow_checks
    assert deferred.mask_shadow_mismatches == eager.mask_shadow_mismatches == 0
