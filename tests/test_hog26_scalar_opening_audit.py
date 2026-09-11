"""Pinned vectors and corruption checks; no producer helper imports."""

import copy
import hashlib
import json
import random

import pytest

from scripts.hog26_scalar_opening_audit import (
    ScalarOpeningAuditError,
    audit_scalar_opening_metadata,
)


def expected_authority():
    # Caller-owned fixture authority, deliberately separate from published data.
    templates = [
        ["HogRider", "Musketeer", "IceGolem", "Skeletons", "IceSpirits", "Cannon", "Fireball", "Log"],
        ["Goblins", "MiniPekka", "MegaMinion", "Princess", "Firecracker", "Poison", "Arrows", "BombTower"],
    ]
    return {"version": "clasher.scalar-canonical-opening.v1", "campaign_seed": "1279201",
            "role": "train", "deck_name": "Scalar opening audit fixture", "opponent_style": "balanced",
            "relative_templates": templates, "episodes": 2,
            "canonical_names": sorted(name for deck in templates for name in deck)}


def metadata():
    # Fixed independently generated JSON vectors, not values computed by the verifier.
    published = json.loads("""
    {"authority_sha256":"940252e7291d2c268748b389c007cd10a0375ae77b300342a4fac3eb0d407ac1",
     "scenarios":[
       {"scenario_id":"b4dfcd636f0e259c1359194dbc9a617da4a54f55d7bfb9c0197d8d6348a5dcdd",
        "cluster_id":"da212c60030aa62845deb6c07c5c25811bb690fe949ebf4fef97069a7ed17385",
        "ordinal":0,"attempts":1,
        "relative_decks":[
          ["Fireball","HogRider","IceGolem","Log","Musketeer","IceSpirits","Cannon","Skeletons"],
          ["MegaMinion","Arrows","Princess","Poison","Goblins","BombTower","MiniPekka","Firecracker"]],
        "stream_seeds":{
          "opening":"269415805009599073847276751851249997430327857103174390027614426386136593779",
          "battle":"8103925012797911013178793753272123764438416174096279221467904382186989040602",
          "action-order":"103576117130369001269111613054209365423812388798404144377026205948054655419217",
          "opponent":"87304465991442611990315221151011055081540737286810620084461841013143225732210"}},
       {"scenario_id":"a914d3b2fd5cec7af4edf179560562855d639ac5cfcdeb30e9d29cc1faabe76d",
        "cluster_id":"92cc2f90fdc666f53eb6528f243986c2e056b04dba4381a754d96d450ee410ef",
        "ordinal":1,"attempts":1,
        "relative_decks":[
          ["IceGolem","IceSpirits","Musketeer","Cannon","HogRider","Fireball","Log","Skeletons"],
          ["Princess","Goblins","MegaMinion","BombTower","Arrows","MiniPekka","Firecracker","Poison"]],
        "stream_seeds":{
          "opening":"20902050429764288182279708622999921152479227657939129906963002705625358359277",
          "battle":"60430591541747236426491497663771245808904940877335306861058754589388439265118",
          "action-order":"56655945604351846897503660460578816492191885611143679783014845077012668004854",
          "opponent":"73737817279295210707891609726638841180730493369451272911633521520131572702090"}}
     ]}
    """)
    published.update(authority=expected_authority(), pairing="same-relative-deal-and-streams-across-seats",
                     repeats="same-scenario-and-cluster; determinism-only",
                     rng_algorithm="CPython random.Random MT19937; shuffle/randbelow version pinned externally")
    return published


def test_pinned_vectors_manual_fisher_yates_and_no_global_rng_consumption(monkeypatch):
    def forbidden_shuffle(*args, **kwargs):
        raise AssertionError("verifier must use independent Fisher-Yates")

    monkeypatch.setattr(random.Random, "shuffle", forbidden_shuffle)
    before = random.getstate()
    rows = audit_scalar_opening_metadata(metadata(), expected_authority=expected_authority())
    assert random.getstate() == before
    assert len(rows) == 2 and len({r.cluster_id for r in rows}) == 2
    assert rows[0].scenario_id == "b4dfcd636f0e259c1359194dbc9a617da4a54f55d7bfb9c0197d8d6348a5dcdd"
    for row in rows:
        assert row.world_decks(0) == row.world_decks(1)[::-1]
        assert len(set(dict(row.stream_seeds).values())) == 4


@pytest.mark.parametrize("field", ["scenario_id", "cluster_id", "ordinal", "attempts", "relative_decks", "stream_seeds"])
def test_corrupted_record_is_rejected(field):
    data = metadata()
    row = data["scenarios"][0]
    if field.endswith("_id"):
        row[field] = "0" * 64
    elif field == "relative_decks":
        row[field][0].reverse()
    elif field == "stream_seeds":
        row[field]["battle"] = "0"
    else:
        row[field] += 1
    with pytest.raises(ScalarOpeningAuditError):
        audit_scalar_opening_metadata(data, expected_authority=expected_authority())


@pytest.mark.parametrize("field,value", [
    ("role", "selection"), ("deck_name", "different"), ("opponent_style", "reactive-defense"),
    ("campaign_seed", "1279202"), ("episodes", 3),
])
def test_self_consistent_authority_hash_does_not_replace_external_pin(field, value):
    data = metadata()
    data["authority"][field] = value
    data["authority_sha256"] = hashlib.sha256(json.dumps(data["authority"], sort_keys=True,
        separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()).hexdigest()
    with pytest.raises(ScalarOpeningAuditError, match="external pin"):
        audit_scalar_opening_metadata(data, expected_authority=expected_authority())


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(unexpected=True),
    lambda d: d["authority"].update(unexpected=True),
    lambda d: d["scenarios"][0].update(unexpected=True),
    lambda d: d.update(pairing="independent-seats"),
    lambda d: d.update(repeats="new-samples"),
    lambda d: d.update(rng_algorithm="different"),
    lambda d: d["authority"].update(version="clasher.scalar-canonical-opening.v1-proposal"),
    lambda d: d["authority"].update(campaign_seed=1279201),
    lambda d: d["authority"].update(campaign_seed="01279201"),
    lambda d: d["authority"].update(episodes=True),
    lambda d: d["authority"]["canonical_names"].reverse(),
    lambda d: d["authority"]["canonical_names"].append(d["authority"]["canonical_names"][0]),
    lambda d: d["scenarios"][0].update(ordinal=False),
    lambda d: d["scenarios"][0].update(attempts=True),
    lambda d: d["scenarios"][0]["stream_seeds"].update(battle="01"),
    lambda d: d["scenarios"][0]["stream_seeds"].update(battle=1),
    lambda d: d["scenarios"][0]["stream_seeds"].update(extra="1"),
    lambda d: d["scenarios"].pop(),
])
def test_schema_types_versions_and_inventory_fail_explicitly(mutate):
    data = metadata()
    mutate(data)
    with pytest.raises(ScalarOpeningAuditError):
        audit_scalar_opening_metadata(data, expected_authority=expected_authority())


def test_verified_rows_are_detached_from_caller_mutations():
    data, expected = metadata(), expected_authority()
    rows = audit_scalar_opening_metadata(data, expected_authority=expected)
    frozen = copy.deepcopy(rows)
    data["scenarios"][0]["relative_decks"][0].reverse()
    expected["canonical_names"].clear()
    assert rows == frozen
    with pytest.raises(ScalarOpeningAuditError):
        rows[0].world_decks(True)
    with pytest.raises(TypeError):
        audit_scalar_opening_metadata(metadata())


@pytest.mark.parametrize("learner_seat", [0, 1])
def test_real_scalar_episode_keeps_full_deal_and_public_hand_tokens(learner_seat):
    from clasher.rl.simple_pytorch_backend import load_current_client_typed_vocabulary
    from clasher.rl.structured_obs import StructuredObservationBuilder
    from scripts.hog26_scalar_actor_projection import build_scalar_reference_actors
    from scripts.hog26_scalar_reference_episode import ScalarReferenceEpisode

    rows = audit_scalar_opening_metadata(metadata(), expected_authority=expected_authority())
    vocab = load_current_client_typed_vocabulary()
    builder = StructuredObservationBuilder(token_names=vocab.token_names, max_entities=64,
        card_semantics_version=3, canonical_lane_globals=True)
    for row in rows:
        seeds = dict(row.stream_seeds)
        decks = row.world_decks(learner_seat)
        episode = ScalarReferenceEpisode.create(decks, seed=seeds["battle"],
            learner_seat=learner_seat, action_order_seed=seeds["action-order"])
        actors = build_scalar_reference_actors(episode.battle, builder, appearances=(),
            visible_to=lambda entity, viewer: entity.is_visible_to(viewer))
        for seat in (0, 1):
            player = episode.battle.players[seat]
            assert tuple(player.deck) == decks[seat]
            assert tuple(player.hand) == decks[seat][:4]
            assert tuple(player.cycle_queue) == decks[seat][4:]
            expected_ids = [builder.token_id(name, namespace="card_action") for name in decks[seat][:4]]
            assert actors[seat].hand_ids[:4].tolist() == expected_ids
        assert episode.battle.rng.getstate() == random.Random(seeds["battle"]).getstate()
        assert episode.action_order_rng.getstate() == random.Random(seeds["action-order"]).getstate()
