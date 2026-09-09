import copy
import json
from pathlib import Path

import pytest
import torch

from clasher.data import CardDataLoader
from clasher.rl.simple_pytorch_backend import load_simple_supported_decks
from clasher.torch_sim.simple_effects import FastEffectState
from clasher.torch_sim.simple_standard import compile_standard_simple_setup
from scripts.hog26_ordinary_projectile_sidecar import (
    compile_ordinary_rules,
    project_primary_effect_pool,
)
from scripts.hog26_public_delivery_flight_rules import with_public_delivery_flights


@pytest.fixture(scope="module")
def setup():
    root = Path(__file__).resolve().parents[1]
    protocol = json.loads((root / "reports/hog26_procedural_outcome_protocol_reassessed_20260908.json").read_text())
    artifact = load_simple_supported_decks(root / protocol["procedural_decks"]["path"])
    loader = CardDataLoader()
    compiled = compile_standard_simple_setup(loader, artifact.public_cards, device="cpu",
                                              canonical_lane_globals=True)
    inventory = json.loads((root / "reports/hog26_public_effect_registry_audit_20260909.json").read_text())
    rules = compile_ordinary_rules(compiled.spawn_blueprints.fast_cards, compiled.cards.names, inventory)
    return compiled, loader, inventory, rules


def test_delivery_identity_without_payload_or_target_exposure(setup):
    compiled, loader, inventory, original = setup
    rules, names = with_public_delivery_flights(original, compiled.spawn_blueprints.fast_cards,
                                                loader, inventory)
    assert names == ["GoblinBarrel"]
    card = compiled.cards.name_to_id["GoblinBarrel"]
    assert original.appearance_token[card] == 0
    effects = FastEffectState.empty(1, max_effects=1)
    effects.active[:] = True
    effects.source_card_id[:] = card
    expected = project_primary_effect_pool(effects, rules)
    assert expected[0][0, 0, 0] == rules.appearance_token[card]
    effects.target_x_units[:] = 16000
    effects.target_id[:] = 99
    effects.damage[:] = 1234
    effects.lifetime_ticks[:] = 999
    for actual, reference in zip(project_primary_effect_pool(effects, rules), expected, strict=True):
        torch.testing.assert_close(actual, reference, rtol=0, atol=0)


def test_mismatched_delivery_appearance_is_rejected(setup):
    compiled, loader, inventory, rules = setup
    changed = copy.deepcopy(inventory)
    row = next(row for row in changed["entries"] if row["runtime_card_name"] == "GoblinBarrel")
    row["candidates"][0]["name"] = "UnrelatedProjectile"
    with pytest.raises(ValueError, match="mismatch"):
        with_public_delivery_flights(rules, compiled.spawn_blueprints.fast_cards, loader, changed)
