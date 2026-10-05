"""Prospective root selection must preserve missingness and episode ownership."""

from dataclasses import replace

import pytest
from pydantic import ValidationError

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.public_observation import exact_public_observation
from clasher.rl.public_scripted_opponent import SUPPORTED_CARDS, PublicScriptedOpponent
from clasher.rl.readiness_root_bank import (
    RootBank,
    RootRequest,
    generate_root_bank,
    context_matches,
    apply_prefix_owner_reserve,
    OFFENSIVE_FOCAL_CARDS,
    select_root,
)
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.training_readiness_v2 import ROLES


def fixture(owner=0):
    battle = BattleState()
    builder = StructuredObservationBuilder(
        card_vocab=sorted(SUPPORTED_CARDS),
        canonical_lane_globals=True,
        public_entity_levels=True,
        card_semantics_version=4,
    )
    controller = PublicScriptedOpponent(builder)
    battle.players[owner].hand = ["Cannon", "Skeletons", "HogRider", "Fireball"]
    battle.players[owner].elixir = 10
    own = (
        "Cannon",
        "Skeletons",
        "HogRider",
        "Fireball",
        "Log",
        "Musketeer",
        "IceGolem",
        "IceSpirit",
    )
    other = (
        "Giant",
        "Prince",
        "DarkPrince",
        "Musketeer",
        "Archers",
        "Goblins",
        "Fireball",
        "Zap",
    )
    request = RootRequest(
        family_id="test-episode",
        source_episode_id="test-episode",
        root_owner=owner,
        episode_seed=4,
        decks=(own, other) if owner == 0 else (other, own),
        prefix_styles=("balanced", "pressure"),
        focal_card="Cannon",
        context="own_half_threat",
        start_tick=90,
        stop_tick=100,
    )

    def packet():
        return exact_public_observation(builder.build_actor(battle, owner))

    return battle, controller, request, packet


def test_bank_declares_independent_episodes_balanced_seats_and_all_cards():
    bank = generate_root_bank(191301)
    assert bank == generate_root_bank(191301)
    assert bank != generate_root_bank(191302)
    assert len({r.episode_design_sha256 for r in bank.requests}) == 32
    assert sum(r.root_owner for r in bank.requests) == 16
    assert {r.focal_card for r in bank.requests} == SUPPORTED_CARDS
    assert {r.context for r in bank.requests} == {
        "own_half_threat",
        "bridge_contact",
        "enemy_cluster",
        "contested_board",
        "enemy_backline",
    }
    assert RootBank.model_validate_json(bank.model_dump_json()) == bank


@pytest.mark.parametrize("field", ["family_id", "source_episode_id", "episode_seed"])
def test_duplicate_episode_cannot_be_renamed_into_independent_family(field):
    bank = generate_root_bank(191301)
    rows = list(bank.requests)
    value = rows[0].model_dump()
    changed = rows[1].model_dump()
    changed[field] = value[field]
    rows[1] = RootRequest(**changed)
    with pytest.raises(ValidationError, match="duplicate"):
        RootBank(master_seed=191301, requests=tuple(rows))


@pytest.mark.parametrize("owner", [0, 1])
def test_first_public_eligible_root_stops_before_future_or_outcomes(owner):
    battle, controller, request, packet = fixture(owner)
    empty = packet()
    battle._spawn_unit_at_position(
        Position(3.5 if owner == 0 else 14.5, 11.5 if owner == 0 else 20.5),
        1 - owner,
        battle.card_loader.get_card("HogRider"),
        deploy_delay_override=0,
        snap_to_valid=False,
    )
    threatened = packet()

    def stream():
        yield 90, empty
        yield 95, threatened
        raise AssertionError("root selection read future data")

    chosen = select_root(request, controller, stream())
    assert chosen.status == "selected"
    assert chosen.root_tick == 95
    assert tuple(c.role for c in chosen.candidates) == ROLES
    assert len({c.action_id for c in chosen.candidates}) == 4
    assert chosen.original_recommendation == controller.decide(threatened).action_id


def test_missing_tick_is_not_silently_skipped():
    _, controller, request, packet = fixture()
    result = select_root(request, controller, [(90, packet()), (100, packet())])
    assert result.status == "missing_packets"
    assert "expected tick 95" in result.reason
    assert not result.candidates


def test_exhausted_root_window_is_failure_without_replacement():
    _, controller, request, packet = fixture()
    result = select_root(
        request, controller, [(90, packet()), (95, packet()), (100, packet())]
    )
    assert result.status == "no_eligible_root"
    assert result.observed_packets == 3
    assert result.root_tick is None


def test_terminal_state_cannot_produce_a_root():
    _, controller, request, packet = fixture()
    data = packet()
    terminal = replace(data, observation=replace(data.observation, terminal=True))
    result = select_root(request, controller, [(90, terminal)])
    assert result.status == "terminal_before_root"


def test_focal_card_in_hand_is_insufficient_without_candidate_exposure():
    battle, controller, request, packet = fixture()
    battle._spawn_unit_at_position(
        Position(3.5, 11.5),
        1,
        battle.card_loader.get_card("HogRider"),
        deploy_delay_override=0,
        snap_to_valid=False,
    )
    request = RootRequest(**{**request.model_dump(), "focal_card": "HogRider"})
    assert "HogRider" in battle.players[0].hand
    result = select_root(
        request, controller, [(90, packet()), (95, packet()), (100, packet())]
    )
    assert result.status == "no_eligible_root"
    assert not result.candidates


def test_revised_bank_declares_reserve_window_and_offensive_context():
    bank=generate_root_bank(260928903)
    assert bank.schema_version == "readiness-v2-root-bank-v2"
    assert all(request.prefix_owner_min_elixir == 8 for request in bank.requests)
    assert all(request.stop_tick == 3600 for request in bank.requests)
    offensive=[r for r in bank.requests if r.focal_card in OFFENSIVE_FOCAL_CARDS]
    assert len(offensive)==10
    assert all(r.context=="enemy_backline" for r in offensive)


@pytest.mark.parametrize('owner',[0,1])
def test_backline_needs_enemy_troops_and_excludes_every_incoming_enemy(owner):
    battle,controller,_,packet=fixture(owner)
    assert not context_matches('enemy_backline',controller,packet())
    def spawn(canonical_y):
        world_y=canonical_y if owner==0 else 32-canonical_y
        battle._spawn_unit_at_position(Position(3.5,world_y),1-owner,
            battle.card_loader.get_card('Knight'),deploy_delay_override=0,snap_to_valid=False)
    spawn(22)
    assert context_matches('enemy_backline',controller,packet())
    spawn(16.5)
    assert not context_matches('enemy_backline',controller,packet())


def test_prefix_reserve_applies_only_to_owner_without_changing_requested_action_at_threshold():
    battle,_,request,packet=fixture()
    request=RootRequest(**(request.model_dump()|{'prefix_owner_min_elixir':8.0}))
    battle.players[0].elixir=7.9
    assert apply_prefix_owner_reserve(request,0,packet(),14)==2304
    assert apply_prefix_owner_reserve(request,1,packet(),14)==14
    battle.players[0].elixir=8
    assert apply_prefix_owner_reserve(request,0,packet(),14)==14
    _,_,legacy,_=fixture()
    assert apply_prefix_owner_reserve(legacy,0,packet(),14)==14
    assert legacy.prefix_owner_min_elixir==0
    assert request.episode_design_sha256 != legacy.episode_design_sha256


def test_legacy_bank_remains_unrestricted_when_optional_reserve_is_absent():
    from clasher.rl.readiness_execution import canonical_sha
    bank=generate_root_bank(260928903).model_dump(mode='json')
    bank['schema_version']='readiness-v2-root-bank-v1'
    for request in bank['requests']:
        request.pop('prefix_owner_min_elixir')
        request['stop_tick']=1290
    parsed=RootBank.model_validate_json(__import__('json').dumps(bank))
    assert all(r.prefix_owner_min_elixir==0 and r.stop_tick==1290 for r in parsed.requests)
    r=parsed.requests[0]
    assert r.episode_design_sha256==canonical_sha({'seed':r.episode_seed,'decks':r.decks,'prefix_styles':r.prefix_styles,'level':r.level})
