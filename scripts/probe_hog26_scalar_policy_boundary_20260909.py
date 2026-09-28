"""Reproduce scalar actor-only inference with explicit feature availability."""

import argparse
import hashlib
import json
from dataclasses import fields
from pathlib import Path

import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.dynamic_spells import create_spell_from_json
from clasher.rl.simple_pytorch_backend import (
    _compile_public_mask_v2_tables,
    _typed_lookups,
    load_current_client_typed_vocabulary,
)
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.simple_public_mask import SimplePublicMaskV2Provider
from clasher.torch_sim.simple_standard import compile_standard_simple_setup
from scripts.evaluate_hog26_simple_policy import load_model
from scripts.hog26_scalar_actor_projection import (
    build_scalar_reference_actors,
    compile_scalar_hand_lookup,
)
from scripts.hog26_scalar_policy_inputs import scalar_policy_inputs
from scripts.hog26_scalar_public_effect_adapter import ScalarArrowsAppearance


def digest(tensor):
    return hashlib.sha256(tensor.detach().cpu().contiguous().numpy().tobytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite diagnostic evidence")
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[1]
    checkpoint = root / "checkpoints/hog26_direct_constant_event_seed1263001/candidate.pt"
    model, builder = load_model(checkpoint, torch.device("cpu"))
    battle = BattleState()
    battle.rng.seed(1279011)
    vocabulary = load_current_client_typed_vocabulary()
    hand_lookup = compile_scalar_hand_lookup(builder, vocabulary)
    before = set(battle.entities)
    spell = create_spell_from_json(battle.card_loader.get_card("Arrows")._raw_entry,
                                   battle.card_loader.load_card_definitions())
    assert spell.cast(battle, 0, Position(3.5, 25.5))
    bindings = ScalarArrowsAppearance.compile(battle.card_loader, vocabulary).bind_cast(
        [e for key, e in battle.entities.items() if key not in before])
    actors = build_scalar_reference_actors(
        battle, builder, appearances=bindings, hand_lookup=hand_lookup,
        visible_to=lambda entity, seat: entity.is_visible_to(seat),
    )
    setup = compile_standard_simple_setup(builder.loader, ["Arrows", "Knight"],
                                         device="cpu", canonical_lane_globals=True)
    lookup, _ = _typed_lookups(setup, builder.loader, vocabulary)
    provider = SimplePublicMaskV2Provider(_compile_public_mask_v2_tables(builder, setup, lookup))
    inputs, masks = scalar_policy_inputs(actors, provider,
                                        previous_actions=[NO_OP_ACTION] * 2,
                                        episode_starts=[True] * 2)
    with torch.inference_mode():
        first = model.act(inputs, model.initial_state(2), deterministic=True)
        second = model.act(inputs, model.initial_state(2), deterministic=True)
    assert torch.equal(first[0], second[0])
    assert all(torch.equal(a, b) for a, b in zip(first[3], second[3], strict=True))
    assert all(torch.isfinite(value).all() for value in first[3])
    sources = [Path(__file__).relative_to(root).as_posix(),
               "scripts/hog26_scalar_policy_inputs.py", "scripts/hog26_scalar_actor_projection.py",
               "scripts/hog26_scalar_public_effect_adapter.py", "src/clasher/rl/model.py",
               "src/clasher/torch_sim/simple_public_mask.py"]
    report = {
        "status": "single_boundary_deterministic_inference_only",
        "scope": "Scripted Arrows scene, two independently initialized inference calls. "
                 "No full-game replay, corpus, training, or observation acceptance claim.",
        "actions": first[0].tolist(), "visible_counts": [int(a.entity_mask.sum()) for a in actors],
        "all_critic_inputs_absent": all(getattr(inputs, f.name) is None
                                       for f in fields(inputs) if f.name.startswith("critic")),
        "zero_reward_feedback": not bool(inputs.previous_rewards.any()),
        "input_sha256": {f.name: digest(value) for f in fields(inputs)
                         if isinstance(value := getattr(inputs, f.name), torch.Tensor)},
        "recurrent_sha256": [digest(value) for value in first[3]],
        "mask_semantics_id": masks.semantics_id, "mask_semantics_digest": masks.semantics_digest,
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "source_sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in sources},
    }
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: report[k] for k in ("status", "actions", "all_critic_inputs_absent",
                                           "zero_reward_feedback")}))


if __name__ == "__main__":
    main()
