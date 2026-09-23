from __future__ import annotations

import copy

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.card_types import CardStatsCompat
from clasher.data import CardDataLoader


def test_specialized_card_stats_deepcopy_matches_generic_and_isolates_mutables() -> None:
    stats = CardDataLoader().get_card("Knight")
    assert stats is not None
    specialized_method = CardStatsCompat.__deepcopy__
    try:
        del CardStatsCompat.__deepcopy__
        generic = copy.deepcopy(stats)
    finally:
        CardStatsCompat.__deepcopy__ = specialized_method
    specialized = copy.deepcopy(stats)

    assert specialized is not stats
    assert specialized.__dict__.keys() == generic.__dict__.keys()
    assert specialized._raw_entry == generic._raw_entry
    assert specialized.name == generic.name
    assert specialized.hitpoints == generic.hitpoints
    assert specialized.damage == generic.damage
    assert specialized.projectile_data == generic.projectile_data
    assert specialized._raw_entry is not stats._raw_entry
    assert specialized.card_definition is not stats.card_definition

    specialized._raw_entry["optimizer_probe"] = {"values": [1, 2, 3]}
    assert "optimizer_probe" not in stats._raw_entry


def test_battle_clone_shares_only_definition_but_isolates_active_wrapper() -> None:
    source = BattleState(fast_path=True)
    assert source.deploy_card(0, "Knight", Position(3.5, 10.5))
    cloned = source.clone()

    source_knight = max(source.entities.values(), key=lambda entity: entity.id)
    cloned_knight = cloned.entities[source_knight.id]
    assert cloned_knight.card_stats is not source_knight.card_stats
    assert (
        cloned_knight.card_stats.card_definition
        is source_knight.card_stats.card_definition
    )
    assert cloned_knight.card_stats._raw_entry is not source_knight.card_stats._raw_entry

    cloned_knight.card_stats.damage += 1
    cloned_knight.card_stats._raw_entry["optimizer_probe"] = True
    assert cloned_knight.card_stats.damage != source_knight.card_stats.damage
    assert "optimizer_probe" not in source_knight.card_stats._raw_entry
