from dataclasses import dataclass

import clasher.mechanics.champion.ability as ability_module
from clasher.battle import BattleState
from clasher.mechanics.champion.ability import ActiveAbility


@dataclass
class _NoOpEffect:
    called: bool = False

    def apply(self, context) -> None:
        self.called = True


@dataclass
class _DummyPosition:
    x: float
    y: float


@dataclass
class _DummyEntity:
    player_id: int
    position: _DummyPosition
    stunned: bool = False

    def is_stunned(self) -> bool:
        return self.stunned


def test_active_ability_activation_builds_context_without_import_error():
    battle = BattleState()
    battle.players[0].elixir = 10.0

    effect = _NoOpEffect()
    ability = ActiveAbility(
        name="TestAbility",
        elixir_cost=1,
        cooldown_ms=0,
        duration_ms=1000,
        effects=[effect],
    )

    entity = _DummyEntity(player_id=0, position=_DummyPosition(x=9.0, y=10.0))

    assert ability.activate(entity, battle)
    assert effect.called


def test_active_ability_can_activate_while_champion_is_stunned():
    battle = BattleState()
    battle.players[0].elixir = 10.0
    ability = ActiveAbility(
        name="FrozenAbility",
        elixir_cost=1,
        cooldown_ms=0,
        duration_ms=1000,
        effects=[],
    )
    entity = _DummyEntity(
        player_id=0,
        position=_DummyPosition(x=9.0, y=10.0),
        stunned=True,
    )

    assert ability.can_activate(entity, battle)
    assert ability.activate(entity, battle)
    assert battle.players[0].elixir == 9.0


def test_frozen_champion_activation_is_controlled_by_shared_global(monkeypatch):
    battle = BattleState()
    battle.players[0].elixir = 10.0
    ability = ActiveAbility(
        name="FrozenAbility",
        elixir_cost=1,
        cooldown_ms=0,
        duration_ms=1000,
        effects=[],
    )
    entity = _DummyEntity(
        player_id=0,
        position=_DummyPosition(x=9.0, y=10.0),
        stunned=True,
    )
    monkeypatch.setattr(
        ability_module,
        "LOGIC_CHAMPION_CAN_EXECUTE_ABILITY_FROZEN",
        False,
    )

    assert not ability.can_activate(entity, battle)
    assert not ability.activate(entity, battle)
    assert battle.players[0].elixir == 10.0


def test_active_ability_cooldown_starts_after_active_duration():
    battle = BattleState()
    battle.players[0].elixir = 10.0
    ability = ActiveAbility(
        name="TimedAbility",
        elixir_cost=1,
        cooldown_ms=2000,
        duration_ms=1000,
        effects=[],
    )
    entity = _DummyEntity(player_id=0, position=_DummyPosition(x=9.0, y=10.0))

    assert ability.activate(entity, battle)
    assert ability.get_cooldown_remaining(battle) == 2000

    battle.time = 1.0
    ability.update(entity, 1000, battle)
    assert not ability.is_active
    assert ability.get_cooldown_remaining(battle) == 2000

    battle.time = 2.999
    assert not ability.can_activate(entity, battle)
    assert ability.get_cooldown_remaining(battle) == 1

    battle.time = 3.0
    assert ability.can_activate(entity, battle)
    assert ability.get_cooldown_remaining(battle) == 0
