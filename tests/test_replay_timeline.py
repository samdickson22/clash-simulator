import copy

import pytest

from clasher.replay_timeline import ReplayTimeline, import_replay_payload


def payload():
    cards = [
        {"card_key": k, "level": 16}
        for k in (
            "cannon-ev1",
            "musketeer-hero",
            "hog-rider",
            "ice-golem",
            "skeletons",
            "fireball",
            "ice-spirit",
            "the-log",
        )
    ]
    return {
        "battle": {
            side: {"players": [{"deck": copy.deepcopy(cards)}]}
            for side in ("team", "opponent")
        },
        "events": [
            {
                "source_index": 0,
                "replay_tick_20hz": 20,
                "side": "team",
                "kind": "play_card",
                "card_key": "cannon",
                "deck_card_key_candidates": ["cannon-ev1"],
                "form_at_play": "unknown",
                "coordinates": {"native_world_units": {"x": 8500, "y": 10500}},
            }
        ],
    }


def test_import_preserves_forms_levels_and_unknown_active_form():
    source = payload()
    before = copy.deepcopy(source)
    result = import_replay_payload(source)
    assert result.team_deck[0].key == "cannon-ev1"
    assert result.team_deck[0].level == 16
    assert result.actions[0].deck_candidates == ("cannon-ev1",)
    assert result.actions[0].active_form is None
    assert "active_form_unresolved" in result.reconstruction_gaps()
    assert ReplayTimeline.model_validate_json(result.model_dump_json()) == result
    assert source == before


@pytest.mark.parametrize("change", ["bad_xy", "duplicate", "wrong_deck", "backward"])
def test_contradictory_records_are_rejected(change):
    source = payload()
    event = source["events"][0]
    if change == "bad_xy":
        event["coordinates"]["native_world_units"]["x"] = float("nan")
    elif change == "wrong_deck":
        event["deck_card_key_candidates"] = ["not-in-deck"]
    else:
        other = copy.deepcopy(event)
        if change == "backward":
            other["source_index"] = 1
            other["replay_tick_20hz"] = 19
        source["events"].append(other)
    with pytest.raises(ValueError):
        import_replay_payload(source)


def test_single_ability_candidate_is_not_silently_made_authoritative():
    source = payload()
    source["events"] = [
        {
            "source_index": 0,
            "replay_tick_20hz": 30,
            "side": "team",
            "kind": "activate_ability",
            "ability_source_candidates": ["musketeer-hero"],
            "ability_source_authoritative": False,
        }
    ]
    result = import_replay_payload(source)
    assert result.actions[0].ability_candidates == ("musketeer-hero",)
    assert result.actions[0].ability_source_authoritative is False
    assert "ability_source_unresolved" in result.reconstruction_gaps()
    source["events"][0]["ability_source_authoritative"] = True
    assert (
        "ability_source_unresolved"
        not in import_replay_payload(source).reconstruction_gaps()
    )
