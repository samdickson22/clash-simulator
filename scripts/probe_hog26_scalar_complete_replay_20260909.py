"""Diagnostic complete-game frozen-policy replay; never writes a training corpus."""

import argparse
import hashlib
import json
import subprocess
import time
from contextlib import contextmanager
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

from clasher.entities import Building, Troop
from clasher.rl.simple_pytorch_backend import (
    SimpleTensorStrategyOpponent,
    _compile_public_mask_v2_tables,
    _typed_lookups,
    load_current_client_typed_vocabulary,
)
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.resident_outputs import TensorPublicStructuredObservation
from clasher.torch_sim.simple_public_mask import SimplePublicMaskV2Provider
from clasher.torch_sim.simple_standard import compile_standard_simple_setup
from scripts.evaluate_hog26_simple_policy import load_model
from scripts.hog26_scalar_actor_projection import build_scalar_reference_actors
from scripts.hog26_scalar_policy_inputs import scalar_policy_inputs
from scripts.hog26_scalar_projectile_receipts import (
    ScalarOrdinaryProjectileDescriptor,
    ScalarProjectileReceiptRecorder,
)
from scripts.hog26_scalar_reference_episode import ScalarReferenceEpisode
from scripts.hog26_scalar_spell_receipts import ScalarSpellReceiptRecorder
from scripts.hog26_scalar_tower_receipts import ScalarTowerReceiptSetup

DECK = ("HogRider", "Musketeer", "IceGolem", "Skeletons", "IceSpirits", "Cannon", "Fireball", "Log")


def hash_tensors(values):
    result = hashlib.sha256()
    for value in values:
        array = value.detach().cpu().contiguous().numpy() if isinstance(value, torch.Tensor) else value
        result.update(str((array.shape, array.dtype)).encode())
        result.update(array.tobytes())
    return result.hexdigest()


def run(model, builder, vocabulary, provider, opponent, *, seat, seed):
    decks = [DECK, tuple(reversed(DECK))]
    if seat == 1:
        decks.reverse()
    episode = ScalarReferenceEpisode.create(decks, seed=seed, learner_seat=seat)
    battle = episode.battle
    tower_setup = ScalarTowerReceiptSetup.compile(
        battle, tuple(battle.entities.values()), builder.loader, vocabulary,
        source_visible_to=lambda source, player: source.is_visible_to(player),
    )
    ordinary = {name: ScalarOrdinaryProjectileDescriptor.compile(name, builder.loader, vocabulary)
                for name in ("Musketeer", "Cannon")}
    ordinary_appearances = []

    @contextmanager
    def frame(current):
        sources = [(entity, ordinary[entity.card_stats.name]) for entity in current.entities.values()
                   if type(entity) in (Troop, Building) and entity.is_alive
                   and getattr(entity, "card_stats", None) is not None
                   and entity.card_stats.name in ordinary]
        with ScalarProjectileReceiptRecorder(current, sources) as recorder:
            yield
            ordinary_appearances.extend(recorder.appearances)

    state = model.initial_state(2)
    previous = np.full(2, NO_OP_ACTION, dtype=np.int64)
    starts = [True, True]
    trace = []
    began = time.perf_counter()
    with tower_setup.recorder() as towers, ScalarSpellReceiptRecorder(
        battle, ("Fireball", "Log"), builder.loader, vocabulary
    ) as spells:
        while not battle.game_over:
            if battle.tick > 6000:
                raise RuntimeError("scalar match failed to terminate at its declared horizon")
            appearances = (*towers.appearances, *spells.appearances, *ordinary_appearances)
            actors = build_scalar_reference_actors(
                battle, builder, appearances=appearances,
                visible_to=lambda entity, player: entity.is_visible_to(player),
            )
            inputs, masks = scalar_policy_inputs(
                actors, provider, previous_actions=previous, episode_starts=starts,
                extra_public_effect_tokens=tower_setup.extra_public_effect_tokens,
            )
            policy_public = TensorPublicStructuredObservation(**{
                f.name: getattr(inputs, f.name).reshape(1, 2, *getattr(inputs, f.name).shape[2:])
                for f in fields(TensorPublicStructuredObservation)
            })
            with torch.inference_mode():
                selected, _, _, next_state, _ = model.act(inputs, state, deterministic=True)
                scripted = opponent(SimpleNamespace(actor=policy_public, public_action_masks=masks.masks))
            actions = scripted[0].numpy().copy()
            actions[seat] = int(selected[seat, 0])
            record = {
                "tick": battle.tick,
                "actor_sha256": hash_tensors([getattr(a, f.name) for a in actors for f in fields(a)]),
                "policy_input_sha256": hash_tensors([getattr(inputs, f.name) for f in fields(inputs)
                                                     if isinstance(getattr(inputs, f.name), torch.Tensor)]),
                "recurrent_sha256": hash_tensors(next_state), "actions": actions.tolist(),
                "visible_counts": [int(a.entity_mask.sum()) for a in actors],
                "attempted_cards": [builder.token_names[int(inputs.hand_ids[s, 0, int(actions[s]) // 576])]
                                    if actions[s] < NO_OP_ACTION else None for s in (0, 1)],
            }
            record.update(episode.step(actions, masks.masks[0].numpy(), tick_context=frame))
            trace.append(record)
            state, previous, starts = next_state, actions, [False, False]
            if len(trace) % 50 == 0:
                print(json.dumps({"seat": seat, "decisions": len(trace), "tick": battle.tick,
                                  "elapsed_seconds": time.perf_counter() - began}), flush=True)
        terminal = [sum(float(getattr(player, name)) for name in
                        ("left_tower_hp", "right_tower_hp", "king_tower_hp"))
                    for player in battle.players]
        return {"seat": seat, "seed": seed, "complete": True, "ticks": battle.tick,
                "winner": battle.winner, "remaining_tower_hp": terminal,
                "outcome": ("draw" if battle.winner in (None, -1) else
                            "win" if battle.winner == seat else "loss"),
                "terminal_tower_margin": (terminal[seat] / battle._starting_total_tower_hp[seat]
                                          - terminal[1 - seat] / battle._starting_total_tower_hp[1 - seat]),
                "initial_tower_hp": [battle._starting_total_tower_hp[i] for i in (0, 1)],
                "trace": trace, "battle_rng_sha256": hashlib.sha256(repr(battle.rng.getstate()).encode()).hexdigest(),
                "order_rng_sha256": hashlib.sha256(repr(episode.action_order_rng.getstate()).encode()).hexdigest(),
                "elapsed_seconds": time.perf_counter() - began}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refusing to overwrite diagnostic evidence")
    torch.set_num_threads(1)
    root = Path(__file__).resolve().parents[1]
    source_paths = [p for p in subprocess.check_output(
        ["rg", "--files", "src/clasher", "scripts"], cwd=root, text=True).splitlines()
        if p.endswith(".py") and (p.startswith("src/clasher/") or "scalar_" in p
                                  or p == "scripts/evaluate_hog26_simple_policy.py")]
    source_hashes = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in sorted(source_paths)}
    checkpoint = root / "checkpoints/hog26_direct_constant_event_seed1263001/candidate.pt"
    model, builder = load_model(checkpoint, torch.device("cpu"))
    vocabulary = load_current_client_typed_vocabulary()
    setup = compile_standard_simple_setup(builder.loader, DECK, device="cpu", canonical_lane_globals=True)
    lookup, _ = _typed_lookups(setup, builder.loader, vocabulary)
    provider = SimplePublicMaskV2Provider(_compile_public_mask_v2_tables(builder, setup, lookup))
    opponent = SimpleTensorStrategyOpponent(builder, strategy_name="balanced", device=torch.device("cpu"))
    runs = []
    for seat in (0, 1):
        pair = [run(model, builder, vocabulary, provider, opponent, seat=seat, seed=1279041)
                for _ in range(2)]
        comparable = [{k: v for k, v in row.items() if k != "elapsed_seconds"} for row in pair]
        if comparable[0] != comparable[1]:
            raise AssertionError("complete scalar replay diverged")
        runs.extend(pair)
    report = {"status": "diagnostic_complete_replay_only", "runs": runs,
              "scope": "Frozen policy versus existing public balanced strategy, paired seats and exact repeats. "
                       "Not training/evaluation corpus, calibration acceptance, or full actor visibility certification.",
              "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
              "mask_semantics_digest": provider.tables.semantics_digest,
              "source_sha256": source_hashes, "vocabulary_sha256": vocabulary.sha256,
              "card_data_sha256": hashlib.sha256(Path(builder.loader.data_file).read_bytes()).hexdigest()}
    if any(hashlib.sha256((root / p).read_bytes()).hexdigest() != h for p, h in source_hashes.items()):
        raise RuntimeError("source changed during diagnostic replay")
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "ticks": [r["ticks"] for r in runs]}), flush=True)


if __name__ == "__main__":
    main()
