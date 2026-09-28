import json
from pathlib import Path

import numpy as np
import pytest
from expanded_authority import (
    COHORTS,
    ScheduledGame,
    build_context,
    load_authority,
    metadata_for,
    read_game,
)

from scripts.hog26_scalar_opening_audit import audit_scalar_opening_metadata

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("present", [False, True])
def test_incomplete_expansion_refuses_before_setup_or_old_arrays(tmp_path, monkeypatch, present):
    import expanded_authority

    def forbidden(root):
        raise AssertionError("partial expansion proceeded to model setup")

    monkeypatch.setattr(expanded_authority, "build_context", forbidden)
    if present:
        directory = tmp_path / "datasets/derived" / COHORTS[2][1]
        directory.mkdir(parents=True)
        (directory / "complete.json").write_text(json.dumps({"status": "complete-audited", "game_count": 12}))
    with pytest.raises(ValueError, match="expanded collection incomplete"):
        load_authority(tmp_path)


def test_independent_context_and_original_game_metadata_match_existing_authorities():
    import torch

    torch.set_num_threads(1)
    vocabulary, tokens, mask_digest, authorities = build_context(ROOT)
    for kind, _, plan_name, _, _ in COHORTS:
        assert authorities[kind] == json.loads((ROOT / "reports" / plan_name).read_text())["source_authority"]
    for kind, directory_name, plan_name, _, _ in COHORTS[:2]:
        directory = ROOT / "datasets/derived" / directory_name
        plan = json.loads((ROOT / "reports" / plan_name).read_text())
        record = json.loads((directory / "complete.json").read_text())["games"][0]
        schedule = plan["schedules"][0]
        scenario = audit_scalar_opening_metadata(schedule["metadata"], expected_authority=schedule["external_authority"])[0]
        seat = schedule["learner_seats"][0]
        metadata = metadata_for(authorities[kind], plan, schedule, scenario, seat, tokens, vocabulary.token_names, mask_digest)
        hand = tuple(vocabulary.resolve(c, "card_action") for c in scenario.relative_decks[0][:5])
        game = ScheduledGame(directory / record["path"], record["sha256"], kind, metadata, hand, record)
        public, label, margin = read_game(game)
        assert public["hand_ids"].shape == (record["rows"], 4)
        assert len(public["global_features"]) == record["rows"]
        assert label == 2 - int(np.argmax(record["outcome_wdl"]))
        assert margin == record["terminal_tower_margin"]


def test_changed_archive_refuses_before_corpus_validation(tmp_path, monkeypatch):
    import expanded_authority

    path = tmp_path / "game.npz"
    path.write_bytes(b"changed")

    def forbidden(*args, **kwargs):
        raise AssertionError("bad archive reached array validation")

    monkeypatch.setattr(expanded_authority, "validate_scalar_corpus", forbidden)
    with pytest.raises(ValueError, match="bytes differ"):
        read_game(ScheduledGame(path, "0" * 64, "expanded", {}, (), {}))


def test_missing_prefix_parity_refuses_before_setup(tmp_path, monkeypatch):
    import expanded_authority

    directory = tmp_path / "datasets/derived" / COHORTS[2][1]
    directory.mkdir(parents=True)
    (directory / "complete.json").write_text(json.dumps({"status": "complete-audited", "game_count": 4608}))

    def forbidden(root):
        raise AssertionError("unreviewed parallel corpus reached setup")

    monkeypatch.setattr(expanded_authority, "build_context", forbidden)
    with pytest.raises(ValueError, match="prefix parity required"):
        load_authority(tmp_path)
