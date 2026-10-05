"""V3 declarations remain prospective, scoped and independent."""

from collections import Counter

import pytest
from pydantic import ValidationError

from clasher.battle import BattleState
from clasher.rl.contract_v5 import ContractV5ObservationBuilder
from clasher.rl.deck_pool import apply_ordered_deck_to_player
from clasher.rl.public_scripted_opponent import SUPPORTED_CARDS, PublicScriptedOpponent
from clasher.rl.readiness_root_bank import DECKS, RootBank
from clasher.rl.readiness_root_bank_v3 import (
    AIR_CARDS,
    BUNDLES,
    C56_SCOPE,
    HumanDeckCatalog,
    HumanDeckFrequency,
    RootBankV3,
    RootRequestV3,
    generate_root_bank_v3,
    select_root_v3,
)


@pytest.fixture(scope="module")
def catalog():
    # Synthetic frequency fixture only; production catalogs use pinned train roles.
    decks = {tuple(sorted(DECKS[0])): 100}
    for focal in C56_SCOPE:
        cards = tuple(sorted(([focal] + [c for c in DECKS[0] if c != focal])[:8]))
        decks[cards] = 50
    return HumanDeckCatalog(
        index_sha256="0" * 64,
        roles_sha256="1" * 64,
        decks=tuple(
            HumanDeckFrequency(cards=d, frequency=n) for d, n in sorted(decks.items())
        ),
    )


@pytest.mark.parametrize("bundle", tuple(BUNDLES))
def test_bundle_bank_is_human_deck_based_balanced_and_roundtrips(catalog, bundle):
    bank = generate_root_bank_v3(42, catalog, bundle)
    assert bank == generate_root_bank_v3(42, catalog, bundle)
    assert RootBankV3.model_validate_json(bank.model_dump_json()) == bank
    assert len({r.episode_design_sha256 for r in bank.requests}) == 32
    assert Counter(r.root_owner for r in bank.requests) == {0: 16, 1: 16}
    assert {r.focal_card for r in bank.requests} == set(BUNDLES[bundle])
    assert all(
        2 <= n <= 4 for n in Counter(r.focal_card for r in bank.requests).values()
    )
    human = {d.cards for d in catalog.decks}
    for r in bank.requests:
        assert all(tuple(sorted(d)) in human for d in r.decks)
        if r.context == "air_threat":
            assert set(r.decks[1 - r.root_owner]) & AIR_CARDS
        else:
            assert set(r.decks[1 - r.root_owner]) <= SUPPORTED_CARDS
    with pytest.raises(ValidationError):
        RootBank.model_validate_json(bank.model_dump_json())


def test_same_master_seed_cannot_reuse_episode_seeds_across_bundles(catalog):
    banks = [generate_root_bank_v3(42, catalog, b) for b in BUNDLES]
    assert len({r.episode_seed for b in banks for r in b.requests}) == 128


def test_scope_parameter_removes_only_unrequested_focal_card(catalog):
    scope = tuple(c for c in C56_SCOPE if c != "GoblinHut")
    bank = generate_root_bank_v3(1, catalog, "B4", card_scope=scope)
    assert "GoblinHut" not in {r.focal_card for r in bank.requests}
    assert all("GoblinHut" not in r.decks[r.root_owner] for r in bank.requests)


def test_missing_human_focal_deck_is_not_synthesized(catalog):
    rows = tuple(d for d in catalog.decks if "Miner" not in d.cards)
    missing = HumanDeckCatalog(index_sha256="0" * 64, roles_sha256="1" * 64, decks=rows)
    with pytest.raises(ValueError, match="no eligible human deck"):
        generate_root_bank_v3(1, missing, "B4")


def test_duplicate_episode_is_rejected_even_after_renaming(catalog):
    bank = generate_root_bank_v3(1, catalog, "B4")
    rows = list(bank.requests)
    duplicated = rows[0].model_dump()
    duplicated.update(
        family_id=rows[1].family_id, source_episode_id=rows[1].source_episode_id
    )
    rows[1] = RootRequestV3(**duplicated)
    with pytest.raises(ValidationError, match="duplicate"):
        RootBankV3(**{**bank.model_dump(), "requests": tuple(rows)})


def public_scene(catalog, focal):
    request = next(
        r
        for r in generate_root_bank_v3(1, catalog, "B4").requests
        if r.focal_card == focal
    )
    battle = BattleState()
    for owner in (0, 1):
        apply_ordered_deck_to_player(battle.players[owner], request.decks[owner])
    for _ in range(90):
        battle.step()
    battle.players[request.root_owner].elixir = 10
    hand = [focal] + [c for c in request.decks[request.root_owner] if c != focal]
    battle.players[request.root_owner].hand = hand[:4]
    builder = ContractV5ObservationBuilder()
    controller = PublicScriptedOpponent(builder, card_scope="c56")
    return request, controller, builder.build_public(battle, request.root_owner)


def test_v3_first_eligible_root_does_not_read_future(catalog):
    request, controller, packet = public_scene(catalog, "Miner")

    def packets():
        yield 90, packet
        raise AssertionError("selector read a future packet")

    result = select_root_v3(request, controller, packets())
    assert result.status == "selected" and result.root_tick == 90


def test_v3_missing_and_exhausted_windows_remain_failures(catalog):
    request, controller, packet = public_scene(catalog, "FirespiritHut")
    request = RootRequestV3(**{**request.model_dump(), "stop_tick": 100})
    assert (
        select_root_v3(request, controller, [(90, packet), (100, packet)]).status
        == "missing_packets"
    )
    result = select_root_v3(
        request, controller, [(90, packet), (95, packet), (100, packet)]
    )
    assert result.status == "no_eligible_root" and result.root_tick is None
