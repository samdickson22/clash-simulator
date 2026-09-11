import random
from collections import deque
from copy import deepcopy

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.simple_pytorch_backend import load_current_client_typed_vocabulary
from clasher.spells import SPELL_REGISTRY
from clasher.torch_sim.diagnostics import battle_snapshot
from scripts.hog26_scalar_royal_delivery_receipts import ScalarRoyalDeliveryRecorder


def fixture(owner):
    battle = BattleState(rng=random.Random(93211))
    p = battle.players[owner]
    p.hand = ["RoyalDelivery"]
    p.deck = ["RoyalDelivery"]
    p.cycle_queue = deque()
    p.elixir = 10
    return battle


@pytest.mark.parametrize("owner", [0, 1])
def test_actual_queued_delivery_has_no_visible_flight_and_matches_control(owner):
    battle, control = fixture(owner), fixture(owner)
    vocab = load_current_client_typed_vocabulary()
    position = Position(9, 12 if owner == 0 else 20)
    recorder = ScalarRoyalDeliveryRecorder(battle, battle.card_loader, vocab)
    with recorder:
        assert battle.deploy_card(owner, "RoyalDelivery", position)
        assert control.deploy_card(owner, "RoyalDelivery", position)
        assert not recorder.registered_internal_containers
        first_container = first_recruit = None
        for _ in range(100):
            battle.step()
            control.step()
            assert battle_snapshot(battle) == battle_snapshot(control)
            assert battle.rng.getstate() == control.rng.getstate()
            assert recorder.appearances == ()
            if recorder.registered_internal_containers:
                first_container = first_container or battle.tick
                entity = recorder.registered_internal_containers[0]
                assert entity.position == position and entity.target_position == position
                if entity.is_alive:
                    assert not recorder.recruits
                    assert recorder.current_recruit_rows(visible_to=lambda *_: True) == ((), ())
                else:
                    first_recruit = first_recruit or battle.tick
                    assert len(recorder.recruits) == 1
                    recruit = recorder.recruits[0]
                    assert vocab.token_names[recruit.token] == "troop_body:DeliveryRecruit"
                    assert recruit.entity.player_id == owner
        assert first_container == 20
        assert first_recruit == 61  # 1s acceptance plus serialized 2.05s impact delay.
        assert len(recorder.registered_internal_containers) == 1
        assert recorder.current_recruit_rows(visible_to=lambda *_: False) == ((), ())
    assert "cast" not in vars(SPELL_REGISTRY["RoyalDelivery"])
    assert "update" not in vars(recorder.registered_internal_containers[0])


def test_pending_scheduler_fields_never_produce_a_current_appearance():
    battle = fixture(0)
    with ScalarRoyalDeliveryRecorder(battle, battle.card_loader,
                                     load_current_client_typed_vocabulary()) as recorder:
        assert battle.deploy_card(0, "RoyalDelivery", Position(9, 12))
        for _ in range(20):
            battle.step()
        entity = recorder.registered_internal_containers[0]
        entity.target_position = Position(1, 1)
        entity.damage = 99999
        entity.activation_delay = 99999
        entity.spawn_character_data = {"secret": "future payload"}
        assert recorder.appearances == ()
        assert recorder.current_recruit_rows(visible_to=lambda *_: True) == ((), ())
        with pytest.raises(ValueError, match="scheduler authority changed"):
            battle.step()
        assert not recorder.recruits


def test_nested_scope_and_runtime_spell_mutation_rejected_restored():
    battle = fixture(0)
    vocab = load_current_client_typed_vocabulary()
    spell = SPELL_REGISTRY["RoyalDelivery"]
    original_payload = spell.spawn_character_data
    with ScalarRoyalDeliveryRecorder(battle, battle.card_loader, vocab):
        with pytest.raises(ValueError, match="already instrumented"), ScalarRoyalDeliveryRecorder(
            battle, battle.card_loader, vocab,
        ):
            pass
        spell.spawn_character_data = deepcopy(original_payload)
        spell.spawn_character_data["name"] = "WrongBody"
        try:
            assert battle.deploy_card(0, "RoyalDelivery", Position(9, 12))
            with pytest.raises(ValueError, match="spell authority changed"):
                for _ in range(25):
                    battle.step()
        finally:
            spell.spawn_character_data = original_payload
    assert "cast" not in vars(spell)
