import pytest

from clasher import battle as battle_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Building
from clasher.rl.determinism_check import compute_rollout_digest


class _CountingEntityDict(dict):
    values_calls = 0

    def values(self):
        self.values_calls += 1
        return super().values()


def _spawn_cannon(battle: BattleState, position: Position) -> Building:
    stats = battle.card_loader.get_card("Cannon")
    assert stats is not None
    entity = battle._spawn_entity(Building, position, 0, stats)
    assert isinstance(entity, Building)
    return entity


def test_movement_phase_reuses_one_exact_membership_scan(monkeypatch):
    battle = BattleState(fast_path=True)
    battle.entities = _CountingEntityDict(battle.entities)
    battle._coalesce_alive_building_refreshes = True
    battle._alive_building_cache_dirty = True

    monkeypatch.setattr(
        battle_module,
        "_COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH",
        True,
    )
    battle._refresh_alive_buildings_cache()
    battle._refresh_alive_buildings_cache()

    assert battle.entities.values_calls == 1


def test_building_death_invalidates_phase_local_membership():
    battle = BattleState(fast_path=True)
    position = Position(9.0, 10.0)
    cannon = _spawn_cannon(battle, position)
    battle._coalesce_alive_building_refreshes = True
    battle._alive_building_cache_dirty = True
    assert battle.is_position_occupied_by_building(position)
    assert not battle._alive_building_cache_dirty

    cannon.take_damage(cannon.hitpoints + 1.0)

    assert battle._alive_building_cache_dirty
    assert not battle.is_position_occupied_by_building(position)


def test_building_spawn_invalidates_phase_local_membership():
    battle = BattleState(fast_path=True)
    position = Position(9.0, 10.0)
    battle._coalesce_alive_building_refreshes = True
    battle._alive_building_cache_dirty = True
    battle._refresh_alive_buildings_cache()
    assert not battle.is_position_occupied_by_building(position)

    _spawn_cannon(battle, position)

    assert battle._alive_building_cache_dirty
    assert battle.is_position_occupied_by_building(position)


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_coalesced_building_refresh_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
):
    common = {
        "seed": 8857,
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
        battle_module,
        "_COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH",
        False,
    )
    repeated = compute_rollout_digest(**common)
    monkeypatch.setattr(
        battle_module,
        "_COALESCE_MOVEMENT_BUILDING_CACHE_REFRESH",
        True,
    )
    coalesced = compute_rollout_digest(**common)

    assert coalesced.sha256 == repeated.sha256
    assert coalesced.mask_shadow_checks == repeated.mask_shadow_checks
    assert coalesced.mask_shadow_mismatches == repeated.mask_shadow_mismatches == 0
