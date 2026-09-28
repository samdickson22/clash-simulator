"""Private deck changes must not alter the public encoder or actor arrays."""

import copy
import gzip
import hashlib
import importlib
import json
from pathlib import Path

import numpy as np
import pytest

from clasher.data import CardDataLoader
from clasher.rl.native_match_registry import canonical_digest
from clasher.rl.native_public_observation import (
    PUBLIC_REFERENCE_CARDS,
    NativeProjectileCatalog,
    NativePublicObservationAdapter,
    NativePublicScope,
    public_reference_builder,
)
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from clasher.rl.public_policy_contract import PublicPolicySequence

CATALOG = NativeProjectileCatalog(("Archer", "IceSpirits", "Zap"), "a" * 64)


@pytest.mark.parametrize("perspective", [0, 1])
def test_hidden_deck_change_preserves_vocabulary_actor_and_mask(perspective):
    path = (
        Path(__file__).parent
        / "fixtures/native_late_fidelity_boundaries_15_535_86.json"
    )
    frame = json.loads(path.read_text())["cases"][0]["initial"]
    changed = copy.deepcopy(frame)
    enemy = next(
        player for player in changed["players"] if player["owner"] != perspective
    )
    old, new = (26000003, 26000010) if perspective == 0 else (26000000, 26000002)

    def replace_private_card(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in {"cardId", "commandCardId"} and value == old:
                    node[key] = new
                else:
                    replace_private_card(value)
        elif isinstance(node, list):
            for value in node:
                replace_private_card(value)

    replace_private_card(enemy)
    assert len({card["cardId"] for card in enemy["deck"]}) == 8
    assert enemy != next(
        player for player in frame["players"] if player["owner"] != perspective
    )
    loader = CardDataLoader()
    sequences, builders, masks = [], [], []
    for snapshot in (frame, changed):
        builder = public_reference_builder(loader, CATALOG)
        adapter = NativePublicObservationAdapter(
            builder,
            NativePublicScope(
                "15.535.86", hashlib.sha256(loader.data_file.read_bytes()).hexdigest()
            ),
            card_names=PUBLIC_REFERENCE_CARDS,
            projectile_catalog=CATALOG,
        )
        public = adapter.project(snapshot, perspective)
        builders.append(builder)
        sequences.append(PublicPolicySequence.from_observations(builder, [public]))
        masks.append(
            PublicActionMaskBuilder(builder).build(
                PublicActionMaskInput.from_confidence_observation(public)
            )
        )
        assert builder.card_vocab == PUBLIC_REFERENCE_CARDS
        assert all(builder.token_id(name) > 1 for name in PUBLIC_REFERENCE_CARDS)
    assert builders[0].token_names == builders[1].token_names
    np.testing.assert_array_equal(
        builders[0].card_stat_features, builders[1].card_stat_features
    )
    for key in sequences[0].arrays:
        np.testing.assert_array_equal(
            sequences[0].arrays[key], sequences[1].arrays[key]
        )
    np.testing.assert_array_equal(masks[0], masks[1])


@pytest.mark.parametrize("declaration", ["legacy", "fixed", "subset", "wrong-digest"])
def test_capture_audit_distinguishes_legacy_and_declared_vocabularies(
    declaration, tmp_path, monkeypatch
):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    audit = importlib.import_module("audit_native_public_boundary").audit_capture
    loader = CardDataLoader()
    plan = {"decks": [["Knight"], ["Archers"]]}
    if declaration != "legacy":
        plan["public_card_roster"] = list(PUBLIC_REFERENCE_CARDS)
        plan["token_vocabulary_sha256"] = canonical_digest(
            public_reference_builder(loader, CATALOG).token_names
        )
    if declaration == "subset":
        plan["public_card_roster"].pop()
    elif declaration == "wrong-digest":
        plan["token_vocabulary_sha256"] = "0" * 64
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    (tmp_path / "gamedata.json").write_bytes(loader.data_file.read_bytes())
    with gzip.open(tmp_path / "native-frames.jsonl.gz", "wt"):
        pass
    if declaration in {"subset", "wrong-digest"}:
        with pytest.raises(ValueError, match="public roster|token vocabulary"):
            audit(tmp_path, CATALOG)
    else:
        result = audit(tmp_path, CATALOG)
        assert result["hidden_deck_independent_vocabulary"] is (declaration == "fixed")
        assert result["paired_frames_passed"] == 0
