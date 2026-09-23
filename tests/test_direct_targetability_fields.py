from __future__ import annotations

from dataclasses import dataclass

import pytest

from clasher import entities as entities_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
from clasher.mechanics.mechanic_base import BaseMechanic
from clasher.rl.determinism_check import compute_rollout_digest


def _spawn_troop(
    battle: BattleState,
    card_name: str,
    player_id: int,
    position: Position,
) -> Troop:
    stats = battle.card_loader.get_card(card_name)
    assert stats is not None
    before = set(battle.entities)
    battle._spawn_unit_at_position(position, player_id, stats)
    return next(
        entity
        for entity_id, entity in battle.entities.items()
        if entity_id not in before and isinstance(entity, Troop)
    )


@dataclass
class _TargetingBlocker(BaseMechanic):
    def blocks_targeting(self, entity: Troop) -> bool:
        del entity
        return True


def test_direct_targetability_skips_death_immunity_helper(monkeypatch):
    battle = BattleState()
    target = _spawn_troop(battle, "Knight", 1, Position(9.0, 16.0))

    def fail_if_called() -> bool:
        raise AssertionError("death-spawn helper called")

    monkeypatch.setattr(target, "_has_death_spawn_target_immunity", fail_if_called)
    assert target.is_targetable_by(0)


def test_direct_targetability_retains_death_immunity_and_mechanic_gates():
    battle = BattleState()
    target = _spawn_troop(battle, "Knight", 1, Position(9.0, 16.0))
    target._death_spawn_target_immunity_elapsed_ms = 0
    assert not target.is_targetable_by(0)

    target._death_spawn_target_immunity_elapsed_ms = -1
    target.mechanics.append(_TargetingBlocker())
    assert not target.is_targetable_by(0)


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_direct_targetability_fields_preserve_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
):
    common = {
        "seed": 8851,
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
        "_USE_DIRECT_TARGETABILITY_FIELDS",
        False,
    )
    defensive = compute_rollout_digest(**common)
    monkeypatch.setattr(
        entities_module,
        "_USE_DIRECT_TARGETABILITY_FIELDS",
        True,
    )
    direct = compute_rollout_digest(**common)

    assert direct.sha256 == defensive.sha256
    assert direct.decisions == defensive.decisions
    assert direct.episodes_finished == defensive.episodes_finished
    assert direct.mask_shadow_checks == defensive.mask_shadow_checks
    assert direct.mask_shadow_mismatches == defensive.mask_shadow_mismatches == 0
