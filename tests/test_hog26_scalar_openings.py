import copy
import hashlib
import json
import random

import pytest

from scripts.hog26_scalar_openings import CanonicalOpeningSchedule

NAMES = tuple(f"Card{n:02}" for n in range(16))


def schedule(**overrides):
    args = {"campaign_seed": 1279201, "role": "train", "deck_name": "Procedural train 003-1",
                "opponent_style": "balanced", "learner_template": NAMES[:8],
                "opponent_template": NAMES[8:], "canonical_names": NAMES, "episodes": 32}
    args.update(overrides)
    return CanonicalOpeningSchedule(**args)


def independently_reconstruct(metadata):
    """Separate implementation using only published metadata, not producer helpers."""
    def sha(obj):
        raw = json.dumps(obj, ensure_ascii=True, allow_nan=False, separators=(",", ":"),
                         sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
    authority = metadata["authority"]
    assert metadata["authority_sha256"] == sha(authority)
    assert len(metadata["scenarios"]) == authority["episodes"]
    used = set()
    for ordinal, recorded in enumerate(metadata["scenarios"]):
        context = dict(authority)
        context.pop("episodes")
        context["ordinal"] = ordinal
        streams = {stream: str(int(sha({"domain": "stream-seed", "stream": stream,
                                       "scenario": context}), 16))
                   for stream in ["opening", "battle", "action-order", "opponent"]}
        for attempt in range(1000):
            seed = int(sha({"domain": "opening-attempt", "version": authority["version"],
                            "opening_seed": streams["opening"], "attempt": attempt}), 16)
            rng = random.Random(seed)
            rows = []
            for template in authority["relative_templates"]:
                # Independent Fisher-Yates expression of random.shuffle.
                ordered = list(template)
                for index in range(7, 0, -1):
                    selected = rng.randrange(index + 1)
                    ordered[index], ordered[selected] = ordered[selected], ordered[index]
                rows.append(ordered)
            cluster = sha({"domain": "relative-deal-cluster", "version": authority["version"],
                           "deck_name": authority["deck_name"],
                           "opponent_style": authority["opponent_style"], "relative_decks": rows})
            if cluster not in used:
                used.add(cluster)
                break
        assert recorded["ordinal"] == ordinal
        assert [list(d) for d in recorded["relative_decks"]] == rows
        assert recorded["stream_seeds"] == streams
        assert recorded["attempts"] == attempt + 1
        assert recorded["cluster_id"] == cluster
        assert recorded["scenario_id"] == sha({"domain": "scenario-identity", "scenario": context,
            "relative_decks": rows, "stream_seeds": list(streams.items()), "attempt": attempt})


def test_independent_reconstruction_and_json_roundtrip():
    proposed = schedule()
    independently_reconstruct(json.loads(json.dumps(proposed.metadata())))
    assert len({s.cluster_id for s in proposed.scenarios}) == 32
    for s in proposed.scenarios:
        assert set(s.relative_decks[0]) == set(NAMES[:8])
        assert set(s.relative_decks[1]) == set(NAMES[8:])
        assert len(set(dict(s.stream_seeds).values())) == 4


def test_paired_seats_and_repeats_do_not_create_independent_scenarios():
    a, b = schedule(), schedule()
    assert a.metadata() == b.metadata()
    for x, y in zip(a.scenarios, b.scenarios):
        assert x.scenario_id == y.scenario_id and x.cluster_id == y.cluster_id
        assert x.world_decks(0) == x.world_decks(1)[::-1]
        assert x.stream_seeds == y.stream_seeds
    # Larger budgets preserve prefixes, but publication freezes budget authority.
    assert schedule(episodes=64).scenarios[:32] == a.scenarios
    assert schedule(episodes=64).metadata()["authority_sha256"] != a.metadata()["authority_sha256"]


@pytest.mark.parametrize("override", [{"campaign_seed": 1279202}, {"role": "selection"},
    {"deck_name": "different-deck"}, {"opponent_style": "reactive-defense"}])
def test_context_changes_all_declared_streams(override):
    a, b = schedule(episodes=1).scenarios[0], schedule(episodes=1, **override).scenarios[0]
    assert a.scenario_id != b.scenario_id
    assert all(x != y for (_, x), (_, y) in zip(a.stream_seeds, b.stream_seeds))


def test_independent_audit_rejects_mutated_order_stream_or_identity():
    original = schedule(episodes=2).metadata()
    for field in ("relative_decks", "stream_seeds", "scenario_id", "ordinal", "attempts"):
        bad = copy.deepcopy(original)
        row = bad["scenarios"][0]
        if field == "relative_decks":
            row[field] = (row[field][0][::-1], row[field][1])
        elif field == "stream_seeds":
            row[field]["battle"] = "0"
        elif field == "scenario_id":
            row[field] = "0" * 64
        else:
            row[field] += 1
        with pytest.raises(AssertionError):
            independently_reconstruct(bad)


@pytest.mark.parametrize("kwargs", [{"campaign_seed": True}, {"episodes": 0},
    {"learner_template": NAMES[:7]}, {"opponent_template": NAMES[:7] + NAMES[:1]},
    {"learner_template": ("AliasName",) + NAMES[1:8]}, {"role": ""}])
def test_invalid_setup_rejected(kwargs):
    with pytest.raises(ValueError):
        schedule(**kwargs)


def test_no_global_random_state_consumption():
    before = random.getstate()
    schedule()
    assert random.getstate() == before


def test_pinned_reference_vector():
    s = schedule(episodes=1).scenarios[0]
    assert s.scenario_id == "4780a5980aaf970e6c4d6a7bb5c91ae24c6f146b184f400fbfe27a18139a9e2c"
    assert s.cluster_id == "cf96b7a325639bf23764b8beaaba4d86d9c2e41f398aa3e5f10697ed9e48a3b7"
    assert s.relative_decks[0] == ("Card00", "Card02", "Card07", "Card05", "Card03", "Card04", "Card01", "Card06")


def test_metadata_is_detached_and_inventory_is_part_of_authority():
    value = schedule(episodes=1)
    before = value.metadata()
    detached = value.metadata()
    detached["authority"]["role"] = "final"
    detached["authority"]["canonical_names"].append("UntrustedCard")
    value.authority["relative_templates"][0].reverse()
    assert value.metadata() == before
    assert schedule(episodes=1, canonical_names=(*NAMES, "Card99")).metadata() != before


def test_full_width_campaign_seed_is_losslessly_encoded():
    seed = 2**255 + 123
    value = schedule(episodes=1, campaign_seed=seed).metadata()
    assert value["authority"]["campaign_seed"] == str(seed)
    independently_reconstruct(json.loads(json.dumps(value)))
