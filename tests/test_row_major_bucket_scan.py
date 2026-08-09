from __future__ import annotations

import pytest

from clasher import battle as battle_module
from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop
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


@pytest.mark.parametrize(
    ("center", "radius"),
    [
        (Position(9.0, 15.0), 1.5),
        (Position(3.0, 7.0), 4.0),
        (Position(15.0, 25.0), 8.0),
    ],
)
def test_row_major_bucket_scan_preserves_exact_candidates(
    monkeypatch,
    center: Position,
    radius: float,
):
    battle = BattleState(fast_path=True)
    for index, position in enumerate(
        (
            Position(3.0, 8.0),
            Position(9.0, 14.0),
            Position(7.0, 16.0),
            Position(11.0, 16.0),
            Position(15.0, 24.0),
        )
    ):
        _spawn_troop(battle, "Knight", index % 2, position)
    battle._refresh_fast_path_caches()

    monkeypatch.setattr(battle_module, "_USE_ROW_MAJOR_BUCKET_SCAN", False)
    column_major = battle.iter_entities_in_radius(center, radius)
    monkeypatch.setattr(battle_module, "_USE_ROW_MAJOR_BUCKET_SCAN", True)
    row_major = battle.iter_entities_in_radius(center, radius)

    assert [entity.id for entity in row_major] == [entity.id for entity in column_major]


@pytest.mark.parametrize("engine_fast_path", ["off", "shadow", "on"])
def test_row_major_bucket_scan_preserves_fixed_seed_rollout(
    monkeypatch,
    engine_fast_path: str,
):
    common = {
        "seed": 8861,
        "decisions": 32,
        "decks_path": "decks.json",
        "decision_interval": 8,
        "max_ticks": 2048,
        "mirror_match": False,
        "quiet_engine": True,
        "engine_fast_path": engine_fast_path,
        "reward_profile": "defense-v2",
    }

    monkeypatch.setattr(battle_module, "_USE_ROW_MAJOR_BUCKET_SCAN", False)
    column_major = compute_rollout_digest(**common)
    monkeypatch.setattr(battle_module, "_USE_ROW_MAJOR_BUCKET_SCAN", True)
    row_major = compute_rollout_digest(**common)

    assert row_major.sha256 == column_major.sha256
    assert row_major.decisions == column_major.decisions
    assert row_major.episodes_finished == column_major.episodes_finished
    assert row_major.mask_shadow_checks == column_major.mask_shadow_checks
    assert row_major.mask_shadow_mismatches == column_major.mask_shadow_mismatches == 0
