import sys
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.entities import Troop

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.audit_enabled_mirror import (
    _child_card_stats,
    _runtime_unit_specs,
    _spawn_runtime_unit,
    run_fast_parity,
)


def test_enabled_spawn_graph_includes_every_distinct_base_child():
    direct = _runtime_unit_specs(
        BattleState(),
        include_reachable_children=False,
    )
    reachable = _runtime_unit_specs(
        BattleState(),
        include_reachable_children=True,
    )

    assert len(direct) == 52
    assert {
        name for name, spec in reachable.items() if spec.is_child
    } == {
        "Barbarian",
        "DeliveryRecruit",
        "Goblin",
        "Golemite",
        "LavaPups",
    }
    assert len(reachable) == 57
    assert all(
        spec.source_path is not None
        for spec in reachable.values()
        if spec.is_child
    )


def test_reachable_children_use_current_nested_stats_and_mechanics():
    specs = _runtime_unit_specs(
        BattleState(),
        include_reachable_children=True,
    )
    expected = {
        # child: (level-11 hitpoints, level-11 damage, mechanics)
        "Barbarian": (691, 192, ()),
        "DeliveryRecruit": (547, 133, ("Shield",)),
        "Goblin": (202, 120, ()),
        "Golemite": (1039, 84, ("DeathDamage",)),
        "LavaPups": (215, 81, ()),
    }

    for name, (hitpoints, damage, mechanics) in expected.items():
        stats = _child_card_stats(specs[name])
        assert stats.scaled_hitpoints == hitpoints
        assert stats.scaled_damage == damage
        assert tuple(
            type(mechanic).__name__
            for mechanic in stats.card_definition.mechanics
        ) == mechanics


def test_reachable_child_audit_spawns_one_real_combat_entity():
    specs = _runtime_unit_specs(
        BattleState(),
        include_reachable_children=True,
    )

    for name in (
        "Barbarian",
        "DeliveryRecruit",
        "Goblin",
        "Golemite",
        "LavaPups",
    ):
        battle = BattleState()
        battle.entities.clear()
        battle.next_entity_id = 1
        _spawn_runtime_unit(
            battle,
            specs[name],
            0,
            Position(9.0, 10.0),
        )

        assert len(battle.entities) == 1
        child = battle.entities[1]
        assert isinstance(child, Troop)
        assert child.card_stats.name == name
        assert child.hitpoints == child.card_stats.scaled_hitpoints


def test_random_fast_parity_density_cap_resets_deterministically(capsys):
    run_fast_parity(
        start_seed=0,
        seeds=1,
        events=2,
        max_ticks=2,
        max_entities=6,
    )

    assert capsys.readouterr().out == "fast seed 0: ok (2 density resets)\n"


def test_random_fast_parity_rejects_nonpositive_density_cap():
    with pytest.raises(ValueError, match="--max-entities must be positive"):
        run_fast_parity(
            start_seed=0,
            seeds=1,
            events=1,
            max_ticks=2,
            max_entities=0,
        )
