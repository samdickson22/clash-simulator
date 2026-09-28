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
    ("GiantSnowball", 1), ("Rocket", 1), ("BarbLog", 1), ("GoblinBarrel", 1), ("Poison", 1),
    ("BarbarianBarrel", 1), ("Earthquake", 1), ("Freeze", 1), ("Tornado", 1),
    ("Graveyard", 1), ("Zap", 0)])
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


def test_unaudited_cast_override_rejected_and_restored():
    battle = _battle("Fireball", 0)
    spell = SPELL_REGISTRY["Fireball"]
    original = spell.cast
    def failing_cast(*args):
        raise RuntimeError("cast failure")
    spell.cast = failing_cast
    recorder = _recorder(battle, ["Fireball"])
    try:
        with (pytest.raises(ValueError, match="unaudited cast override"), recorder):
            assert battle.deploy_card(0, "Fireball", Position(9, 14))
            for _ in range(25):
                battle.step()
        assert spell.cast is failing_cast
        assert not recorder.receipts
    finally:
        del spell.cast
    assert spell.cast == original


@pytest.mark.parametrize("owner", [0, 1])
def test_zap_hits_visible_tower_but_emits_no_persistent_entity(owner):
    battle = _battle("Zap", owner)
    control = _battle("Zap", owner)
    target = next(e for e in battle.entities.values() if e.player_id != owner)
    control_target = control.entities[target.id]
    hp_before = target.hitpoints
    with _recorder(battle, ["Zap"]) as recorder:
        assert battle.deploy_card(owner, "Zap", target.position)
        assert control.deploy_card(owner, "Zap", control_target.position)
        for _ in range(25):
            battle.step()
            control.step()
            assert _physics(battle) == _physics(control)
        assert target.hitpoints < hp_before
        assert len(recorder.receipts) == 1
        assert recorder.receipts[0].appearances == ()
        assert recorder.appearances == ()


@pytest.mark.parametrize("card", ["IceGolem", "BombTower", "Lumberjack", "Golem"])
@pytest.mark.parametrize("owner", [0, 1])
def test_zap_lethal_callbacks_have_independent_birth_ownership(card, owner):
    from clasher.entities import Building, Troop
    from scripts.hog26_scalar_public_effect_adapter import project_scalar_public_effects

    battle = _battle("Zap", owner)
    control = _battle("Zap", owner)
    targets = []
    for current in (battle, control):
        target = current._spawn_entity(Building if card == "BombTower" else Troop,
                                       Position(9, 14), 1 - owner, CardDataLoader().get_card(card))
        target.deploy_delay_remaining = 0
        target.placement_pending = False
        target.hitpoints = 1
        targets.append(target)
    initial_ids = set(battle.entities)
    with _recorder(battle, ["Zap"]) as recorder:
        for current in (battle, control):
            assert current.deploy_card(owner, "Zap", Position(9, 14))
        unknown_effect_seen = False
        children_seen = False
        for _ in range(150):
            battle.step()
            control.step()
            assert _physics(battle) == _physics(control)
            children = [e for key, e in battle.entities.items() if key not in initial_ids]
            children_seen |= bool(children)
            for child in children:
                if child.is_alive and not isinstance(child, (Troop, Building)):
                    with pytest.raises(ValueError, match="no audited appearance"):
                        project_scalar_public_effects([child], recorder.appearances,
                                                      visible_to=lambda *_: True)
                    unknown_effect_seen = True
        assert not targets[0].is_alive
        assert children_seen
        assert len(recorder.receipts) == 1
        assert recorder.appearances == ()
        if card != "Golem":
            assert unknown_effect_seen


@pytest.mark.parametrize("spell_name,root_count", [("Fireball", 1), ("Arrows", 30)])
def test_real_projectile_impact_death_children_do_not_inherit_spell_appearance(spell_name, root_count):
    from clasher.entities import Troop
    from scripts.hog26_scalar_public_effect_adapter import project_scalar_public_effects

    battle = _battle(spell_name, 0)
    control = _battle(spell_name, 0)
    initial = []
    for current in (battle, control):
        target = current._spawn_entity(Troop, Position(9, 14), 1,
                                       CardDataLoader().get_card("IceGolem"))
        target.hitpoints = 1
        target.deploy_delay_remaining = 0
        target.placement_pending = False
        initial.append(target)
    with _recorder(battle, [spell_name]) as recorder:
        for current in (battle, control):
            assert current.deploy_card(0, spell_name, Position(9, 14))
        saw_unowned_death_effect = False
        for _ in range(120):
            battle.step()
            control.step()
            assert _physics(battle) == _physics(control)
            for entity in battle.entities.values():
                if (entity.is_alive and getattr(entity, "spell_name", None) == "FreezeIceGolemite"):
                    assert all(a.entity is not entity for a in recorder.appearances)
                    with pytest.raises(ValueError, match="no audited appearance"):
                        project_scalar_public_effects([entity], recorder.appearances,
                                                      visible_to=lambda *_: True)
                    saw_unowned_death_effect = True
        assert not initial[0].is_alive
        assert len(recorder.appearances) == root_count
        assert saw_unowned_death_effect


def test_exception_after_actual_creator_restores_spell_instance(monkeypatch):
    from scripts.hog26_scalar_public_effect_adapter import ScalarSpellAppearance

    battle = _battle("Fireball", 0)
    spell = SPELL_REGISTRY["Fireball"]
    original = spell.cast
    def reject(self, created):
        assert len(created) == 1
        raise RuntimeError("receipt failure")
    monkeypatch.setattr(ScalarSpellAppearance, "bind_cast", reject)
    with (pytest.raises(RuntimeError, match="receipt failure"),
          _recorder(battle, ["Fireball"]) as recorder):
        assert battle.deploy_card(0, "Fireball", Position(9, 14))
        for _ in range(25):
            battle.step()
    assert spell.cast == original
    assert not recorder.receipts
