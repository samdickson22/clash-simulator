"""Audit real runtime cast routes with a read-only experimental effect sidecar."""

import argparse
import hashlib
import json
from dataclasses import fields, replace
from pathlib import Path

import torch

from clasher.data import CardDataLoader, load_princess_tower_character_data
from clasher.rl.simple_pytorch_backend import (
    DEFAULT_SIMPLE_TOKEN_VOCABULARY,
    _typed_lookups,
    load_current_client_typed_vocabulary,
    load_simple_supported_decks,
)
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.simple_standard import compile_standard_simple_setup
from scripts.hog26_ordinary_projectile_sidecar import (
    compile_ordinary_rules,
    project_primary_effect_pool,
)
from scripts.hog26_primary_effect_transition_guard import (
    require_supported_primary_births,
)
from scripts.hog26_public_tower_shot_rules import with_public_tower_shots


def tensor_hash(tensors):
    digest = hashlib.sha256()
    for name, tensor in sorted(tensors.items()):
        digest.update(name.encode())
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def runtime_hash(runtime):
    tensors = dict(runtime._mutable_runtime_tensors())
    for name, owner in runtime._mutable_owners().items():
        tensors.update({name + "." + key: value for key, value in vars(owner).items()
                        if isinstance(value, torch.Tensor)})
    return tensor_hash(tensors)


def actor_tensors(result):
    return {"legal_mask": result.observation.legal_mask,
            **{field.name: getattr(result.observation.actor, field.name)
               for field in fields(result.observation.actor)}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", choices=["cpu", "mps:0"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tower-shots", action="store_true")
    parser.add_argument("--transition-guard", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite runtime probe")
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[1]
    protocol = json.loads((root / "reports/hog26_procedural_outcome_protocol_reassessed_20260908.json").read_text())
    artifact = load_simple_supported_decks(root / protocol["procedural_decks"]["path"])
    loader = CardDataLoader()
    setup = compile_standard_simple_setup(loader, artifact.public_cards, device=args.device,
                                         canonical_lane_globals=True)
    vocabulary = load_current_client_typed_vocabulary(DEFAULT_SIMPLE_TOKEN_VOCABULARY)
    entity_lookup, hand_lookup = _typed_lookups(setup, loader, vocabulary)
    cases = ["Fireball", "Arrows", "Poison", "Zap", "GoblinBarrel", "Log", "Musketeer"]
    base = ["HogRider", "IceGolem", "Musketeer", "Cannon", "Skeletons", "IceSpirit", "Fireball", "Log"]
    decks = [[[card] + [other for other in base if other != card][:7], base] for card in cases]

    def make_runtime():
        return setup.create_runtime(decks, entity_token_lookup=entity_lookup,
                                    hand_token_lookup=hand_lookup, canonical_lane_globals=True,
                                    max_entities=64, max_effects=64, starting_elixir=10)

    runtime, control = make_runtime(), make_runtime()
    assert runtime_hash(runtime) == runtime_hash(control)
    inventory = json.loads((root / "reports/hog26_public_effect_registry_audit_20260909.json").read_text())
    rules = compile_ordinary_rules(setup.spawn_blueprints.fast_cards, setup.cards.names, inventory)
    sidecar_token_names = vocabulary.token_names
    if args.tower_shots:
        princess = load_princess_tower_character_data(loader.data_file)
        rules, sidecar_token_names = with_public_tower_shots(
            rules, setup.tower_spec, vocabulary.token_names, princess["projectileData"]["name"],
        )
    pool_names = ["effects", "travel_effects", "death_effects", "triggered_effects",
                  "rolling_spells", "payload_containers", "positive_buff_areas"]
    records = [{"card": card, "pool_active_frame_counts": {name: 0 for name in pool_names},
                "primary_allocations": {"projectile": 0, "area": 0, "direct": 0},
                "sidecar_frames": 0, "rejected_frames": 0, "transition_gap_frames": 0,
                "first_sidecar_frame": None}
               for card in cases]
    observation_digest = hashlib.sha256()
    for tick in range(160):
        actions = torch.full((len(cases), 2), NO_OP_ACTION, dtype=torch.int64, device=args.device)
        if tick == 0:
            for index, card in enumerate(cases):
                y = 14 if card in {"Log", "Musketeer"} else 25
                actions[index, 0] = y * 18 + 3
        result = runtime.step_tick(actions)
        reference = control.step_tick(actions)
        assert torch.equal(result.action_success, reference.action_success)
        if tick == 0:
            assert result.action_success[:, 0].all(), result.action_success
        before = tensor_hash(actor_tensors(result))
        assert before == tensor_hash(actor_tensors(reference))
        observation_digest.update(before.encode())
        for index, record in enumerate(records):
            for name in pool_names:
                record["pool_active_frame_counts"][name] += int(getattr(runtime, name).active[index].sum().cpu())
            for kind in ("projectile", "area", "direct"):
                record["primary_allocations"][kind] += int(getattr(result.effect_allocation, kind)[index].sum().cpu())
            effects = replace(runtime.effects, **{
                field.name: getattr(runtime.effects, field.name)[index:index + 1]
                for field in fields(runtime.effects)
                if isinstance(getattr(runtime.effects, field.name), torch.Tensor)
            })
            if args.transition_guard:
                allocation = replace(result.effect_allocation, **{
                    field.name: getattr(result.effect_allocation, field.name)[index:index + 1]
                    for field in fields(result.effect_allocation)
                })
                try:
                    require_supported_primary_births(allocation, effects)
                except ValueError:
                    record["transition_gap_frames"] += 1
            try:
                tokens, features, mask = project_primary_effect_pool(effects, rules)
            except ValueError:
                record["rejected_frames"] += 1
            else:
                if mask.any():
                    record["sidecar_frames"] += 1
                    if record["first_sidecar_frame"] is None:
                        record["first_sidecar_frame"] = {
                            "tick": tick + 1, "tokens": tokens[mask].cpu().tolist(),
                            "features": features[mask].cpu().tolist()}
        assert before == tensor_hash(actor_tensors(result))
        if tick in {0, 39, 79, 159}:
            assert runtime_hash(runtime) == runtime_hash(control)
        if (tick + 1) % 40 == 0:
            print(json.dumps({"device": args.device, "ticks_completed": tick + 1}), flush=True)
    with args.output.open("x") as stream:
        json.dump({"status": "bounded runtime route audit; not complete event coverage",
                   "device": args.device, "ticks": 160, "cases": records,
                   "tower_shots_enabled": args.tower_shots,
                   "transition_guard_audited": args.transition_guard,
                   "sidecar_token_names": list(sidecar_token_names),
                   "unchanged_native_control_checkpoints": [1, 40, 80, 160],
                   "actor_observation_trace_sha256": observation_digest.hexdigest(),
                   "actor_observations_unchanged": True,
                   "scope": "Seven scripted single-cast/deployment fixtures. Not complete frozen-policy games, corpus enrichment, or model acceptance. Allocation counts include transient events that can vanish before a boundary observation.",
                   "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, stream, indent=2)
        stream.write("\n")
    print(json.dumps(records), flush=True)


if __name__ == "__main__":
    main()
