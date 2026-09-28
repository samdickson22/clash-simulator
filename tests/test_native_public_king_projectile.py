"""Rendered King shots expose public projectile identity, never private targeting."""

import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from clasher.rl.native_public_observation import (
    NativeProjectileCatalog,
    NativePublicLevelEvidence,
    NativePublicObservationAdapter,
    NativePublicScope,
)
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.structured_obs import StructuredObservationBuilder

ROOT = Path(__file__).parent / "fixtures"
REFERENCE = json.loads(
    (ROOT / "native_public_king_projectile_15_535_86.json").read_text()
)


def adapter(frame):
    cards = [
        "Knight",
        "Archers",
        "Skeletons",
        "Goblins",
        "Giant",
        "HogRider",
        "Prince",
        "DarkPrince",
        "Musketeer",
        "Cannon",
        "IceGolem",
        "IceSpirit",
        "Tesla",
        "Fireball",
        "Log",
        "Zap",
        "Mirror",
    ]
    b = StructuredObservationBuilder(
        card_vocab=cards, canonical_lane_globals=True, public_entity_levels=True
    )
    csv = ROOT / "native_projectiles_15_535_86.csv"
    catalog = NativeProjectileCatalog.from_csv(
        csv, expected_sha256=hashlib.sha256(csv.read_bytes()).hexdigest()
    )
    tokens = [
        "<pad>",
        "<unknown>",
        *sorted(set(b.token_names[2:]) | set(catalog.names)),
    ]
    b = StructuredObservationBuilder(
        card_vocab=cards,
        token_names=tokens,
        canonical_lane_globals=True,
        public_entity_levels=True,
    )
    source = NativePublicObservationAdapter(
        b,
        NativePublicScope(
            "15.535.86", hashlib.sha256(b.loader.data_file.read_bytes()).hexdigest()
        ),
        card_names=tuple(cards),
        projectile_catalog=catalog,
    )
    raw = frame["ordinary"]
    levels = {int(k): v for k, v in frame["levels"]["levels"].items()}
    evidence = NativePublicLevelEvidence(
        tick=raw["tick"],
        generation=raw["generation"],
        state_epoch=raw["stateEpoch"],
        source_sha256=hashlib.sha256(
            json.dumps(frame["levels"], sort_keys=True).encode()
        ).hexdigest(),
        levels=levels,
        confidence={k: 1.0 for k in levels},
    )
    return b, source, evidence


@pytest.mark.parametrize("owner", [0, 1])
@pytest.mark.parametrize("frame", REFERENCE["frames"])
def test_king_projectile_public_position_and_unknown_health(frame, owner):
    b, source, levels = adapter(frame)
    view = source.project(
        frame["ordinary"], owner, rich_snapshot=frame["rich"], level_evidence=levels
    )
    mask = view.observation.entity_mask & (
        view.observation.entity_ids
        == b.token_id("KingProjectile", namespace="projectile")
    )
    assert mask.sum() == 1
    obj = next(e for e in frame["rich"]["objects"] if e["dataGlobalId"] == 10000001)
    xy = np.array([obj["x"] / 18000, obj["y"] / 32000])
    np.testing.assert_allclose(
        view.observation.entity_features[mask, :2][0], 1 - xy if owner else xy
    )
    assert view.observation.entity_features[mask, 6].item() == 1
    assert not view.observation.entity_features[mask, 9:].any()
    assert not view.entity_feature_confidence[mask, 9:].any()
    changed = copy.deepcopy(frame["rich"])
    for e in changed["objects"]:
        if e.get("projectile"):
            e["projectile"]["sourceEntityKey"] = [99, 99, 99]
            e["projectile"]["targetEntityKey"] = [98, 98, 98]
    after = source.project(
        frame["ordinary"], owner, rich_snapshot=changed, level_evidence=levels
    )
    a = PublicPolicySequence.from_observations(b, [view])
    c = PublicPolicySequence.from_observations(b, [after])
    for key in a.arrays:
        np.testing.assert_array_equal(a.arrays[key], c.arrays[key])
