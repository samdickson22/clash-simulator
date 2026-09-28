"""Exercise registered ordinary projectiles through native allocation and motion."""

import hashlib
import json
from pathlib import Path

import torch

from clasher.data import CardDataLoader
from clasher.rl.simple_pytorch_backend import load_simple_supported_decks
from clasher.torch_sim.simple_attack_effects import (
    FastEffectCommands,
    allocate_fast_attack_effects_,
)
from clasher.torch_sim.simple_effects import FastEffectState, step_fast_effects
from clasher.torch_sim.simple_standard import compile_standard_simple_setup
from clasher.torch_sim.simple_state import FastGymState
from scripts.hog26_ordinary_projectile_sidecar import (
    compile_ordinary_rules,
    project_primary_effect_pool,
)
from scripts.probe_hog26_native_public_effects_20260909 import digest


def run(device, artifact, inventory):
    setup = compile_standard_simple_setup(CardDataLoader(), artifact.public_cards,
                                         device=device, canonical_lane_globals=True)
    catalog = setup.spawn_blueprints.fast_cards
    rules = compile_ordinary_rules(catalog, setup.cards.names, inventory)
    cards = torch.nonzero(rules.appearance_token > 0).flatten()
    batch = len(cards)
    state = FastGymState.empty(batch, max_entities=2, device=device)
    effects = FastEffectState.empty(batch, max_effects=2, device=device)
    body = (catalog.kind[cards] == 0) | (catalog.kind[cards] == 1)
    state.active[:, 0] = body
    state.active[:, 1] = True
    state.stable_id[:] = torch.tensor([7, 8], device=device)
    state.owner[:] = torch.tensor([0, 1], device=device)
    state.card_id[:, 0] = cards
    state.card_id[:, 1] = setup.cards.name_to_id["Knight"]
    state.hp[:] = state.max_hp[:] = 1000
    state.x_units[:] = torch.tensor([2000, 12000], device=device)
    state.y_units[:] = 8000
    shape = (batch, 1)
    commands = FastEffectCommands(
        ready=torch.ones(shape, dtype=torch.bool, device=device),
        source_id=torch.where(body, 7, 0)[:, None],
        owner=torch.zeros(shape, dtype=torch.int8, device=device), card_id=cards[:, None],
        source_x_units=torch.full(shape, 2000, dtype=torch.int32, device=device),
        source_y_units=torch.full(shape, 8000, dtype=torch.int32, device=device),
        target_id=torch.full(shape, 8, dtype=torch.int64, device=device),
        target_x_units=torch.full(shape, 12000, dtype=torch.int32, device=device),
        target_y_units=torch.full(shape, 8000, dtype=torch.int32, device=device),
        damage_multiplier=torch.ones(shape, device=device),
    )
    consumed = torch.zeros_like(effects.source_card_id)
    allocation = allocate_fast_attack_effects_(state, effects, consumed, catalog, commands)
    assert allocation.accepted.all() and allocation.projectile.all()
    assert not consumed.any()
    status = torch.zeros_like(state.owner, dtype=torch.int8)
    status_ticks = torch.zeros_like(state.owner, dtype=torch.int32)
    frames = []
    for tick in range(4):
        before = digest(state, effects)
        tokens, features, mask = project_primary_effect_pool(effects, rules)
        assert digest(state, effects) == before
        if tick == 0:
            assert mask[:, :, 0].all() and not mask[:, :, 1].any()
            assert torch.equal(tokens[:, 0, 0], rules.appearance_token[cards])
        frames.append({"tokens": tokens.cpu().tolist(), "features": features.cpu().tolist(),
                       "mask": mask.cpu().tolist()})
        if tick < 3:
            step_fast_effects(state, effects, status, status_ticks)
    return {"device": device, "cards": [setup.cards.names[i] for i in cards.cpu().tolist()],
            "frames": frames, "read_only_projection": True,
            "exclusions": dict(zip(setup.cards.names, rules.exclusions, strict=True))}


def main():
    root = Path(__file__).resolve().parents[1]
    protocol = json.loads((root / "reports/hog26_procedural_outcome_protocol_reassessed_20260908.json").read_text())
    artifact = load_simple_supported_decks(root / protocol["procedural_decks"]["path"])
    inventory = json.loads((root / "reports/hog26_public_effect_registry_audit_20260909.json").read_text())
    devices = ["cpu"] + (["mps:0"] if torch.backends.mps.is_available() else [])
    results = [run(device, artifact, inventory) for device in devices]
    if len(results) == 2:
        assert results[0]["frames"] == results[1]["frames"]
    output = root / "reports/hog26_ordinary_projectile_allocation_probe_20260909.json"
    with output.open("x") as stream:
        json.dump({"status": "native allocation probe passed; no production enrichment authorized",
                   "scope": "Primary-pool ordinary projectile allocation plus three motion steps. This is not a complete-game cast-route, rendered appearance, capacity, or all-effect coverage certificate.",
                   "manifest_sha256": artifact.sha256,
                   "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   "sidecar_sha256": hashlib.sha256((root / "scripts/hog26_ordinary_projectile_sidecar.py").read_bytes()).hexdigest(),
                   "cpu_mps_frames_identical": len(results) == 2, "results": results}, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"devices": devices, "ordinary_identities": len(results[0]["cards"]),
                      "status": "allocation probe passed"}))


if __name__ == "__main__":
    main()
