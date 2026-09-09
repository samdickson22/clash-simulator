import random
from collections import deque

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.rl.simple_pytorch_backend import load_current_client_typed_vocabulary
from clasher.spells import SPELL_REGISTRY
from clasher.torch_sim.diagnostics import battle_snapshot
from scripts.hog26_scalar_spell_receipts import ScalarSpellReceiptRecorder


def _battle(card, owner):
    battle = BattleState(rng=random.Random(99172))
    player = battle.players[owner]
    player.elixir = 10
    player.hand = [card]
    player.deck = [card]
    player.cycle_queue = deque()
    return battle


def _recorder(battle, cards):
    return ScalarSpellReceiptRecorder(battle, cards, CardDataLoader(),
                                      load_current_client_typed_vocabulary())


def _physics(battle):
    return (battle_snapshot(battle), battle.rng.getstate(),
            [(p.execute_at, p.sequence, p.spell_name, p.player_id,
              p.position.x, p.position.y) for p in battle._pending_spell_casts],
            [(e.id, e.position.x, e.position.y, e.is_alive,
              getattr(e, "launch_delay", None), getattr(e, "spawn_delay", None),
              getattr(e, "time_alive", None), getattr(e, "damage", None),
              getattr(getattr(e, "target_position", None), "x", None),
              getattr(getattr(e, "target_position", None), "y", None))
             for e in battle.entities.values()])


@pytest.mark.parametrize("card,count", [("Fireball", 1), ("Log", 1), ("Arrows", 30),
    ("GiantSnowball", 1), ("Rocket", 1), ("BarbLog", 1), ("GoblinBarrel", 1), ("Poison", 1)])
@pytest.mark.parametrize("owner", [0, 1])
def test_actual_queued_execution_preserves_physics_rng_and_unrelated_battle(card, count, owner):
    instrumented = _battle(card, owner)
    control = _battle(card, owner)
    target = Position(9, 14 if owner == 0 else 18)
    with _recorder(instrumented, [card]) as recorder:
        assert instrumented.deploy_card(owner, card, target)
        assert control.deploy_card(owner, card, target)
        assert not recorder.receipts
        assert len(instrumented._pending_spell_casts) == 1
        deadline = instrumented._pending_spell_casts[0].execute_at
        for _ in range(90):
            instrumented.step()
            control.step()
            assert _physics(instrumented) == _physics(control)
            if instrumented.time + 1e-9 < deadline:
                assert not recorder.receipts
            else:
                assert len(recorder.receipts) == 1
                assert len(recorder.appearances) == count
                assert not instrumented._pending_spell_casts
        # The control battle shared the same registry instances throughout,
        # but did not create additional receipts.
        assert len(recorder.receipts) == 1
    for spell, _ in recorder._registrations:
        assert "cast" not in spell.__dict__


def test_nested_and_exceptional_contexts_restore_instance_methods():
    battle = _battle("Fireball", 0)
    spell = SPELL_REGISTRY["Fireball"]
    original = spell.cast
    with _recorder(battle, ["Fireball"]) as outer:
        with pytest.raises(ValueError, match="already has"), _recorder(battle, ["Log", "Fireball"]):
            pass
        assert "cast" not in SPELL_REGISTRY["Log"].__dict__
        assert getattr(spell.cast, "_hog26_spell_receipt_wrapper", False)
        with pytest.raises(RuntimeError, match="twice"):
            outer.__enter__()
    assert spell.cast == original
    with pytest.raises(RuntimeError, match="sentinel"), _recorder(battle, ["Fireball"]):
        raise RuntimeError("sentinel")
    assert spell.cast == original


def test_exception_during_actual_cast_restores_wrapper():
    battle = _battle("Fireball", 0)
    spell = SPELL_REGISTRY["Fireball"]
    original = spell.cast
    def failing_cast(*args):
        raise RuntimeError("cast failure")
    spell.cast = failing_cast
    try:
        with (pytest.raises(RuntimeError, match="cast failure"),
              _recorder(battle, ["Fireball"]) as recorder):
            assert battle.deploy_card(0, "Fireball", Position(9, 14))
            for _ in range(25):
                battle.step()
        assert spell.cast is failing_cast
        assert not recorder.receipts
    finally:
        del spell.cast
    assert spell.cast == original
