"""Diagnostic complete-game frozen-policy replay; never writes a training corpus."""

import argparse
import hashlib
import json
import subprocess
import time
from contextlib import ExitStack, contextmanager
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
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.resident_outputs import TensorPublicStructuredObservation
from clasher.torch_sim.simple_public_mask import SimplePublicMaskV2Provider
from clasher.torch_sim.simple_standard import compile_standard_simple_setup
from scripts.evaluate_hog26_simple_policy import load_model
from scripts.hog26_scalar_actor_projection import (
    build_scalar_reference_actors,
    compile_scalar_hand_lookup,
)
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


def run(model, builder, vocabulary, provider, opponent, *, seat, seed,
        opponent_deck=None, expanded_receipts=False, opening_scenario=None,
        random_opponent_seed=None, episode_writer=None, policy_selfplay=False, control_noop=False):
    action_order_seed = None
    if policy_selfplay and random_opponent_seed is not None:
        raise ValueError("choose frozen-policy mirror or random opponent, not both")
    if opening_scenario is None:
        decks = [DECK, tuple(reversed(DECK)) if opponent_deck is None else tuple(opponent_deck)]
    else:
        streams = dict(opening_scenario.stream_seeds)
        seed = streams["battle"]
        action_order_seed = streams["action-order"]
        decks = list(opening_scenario.relative_decks)
        if random_opponent_seed is not None and random_opponent_seed != streams["opponent"]:
            raise ValueError("opponent seed differs from the opening scenario authority")
    if seat == 1:
        decks.reverse()
    episode = ScalarReferenceEpisode.create(
        decks, seed=seed, learner_seat=seat, action_order_seed=action_order_seed,
    )
    battle = episode.battle
    random_opponent = None
    if random_opponent_seed is not None:
        from scripts.hog26_scalar_public_random_opponent import (
            ScalarPublicRandomOpponent,
        )

        random_opponent = ScalarPublicRandomOpponent(
            seed=random_opponent_seed, opponent_seat=1 - seat,
        )
    elif opponent is None and not policy_selfplay:
        raise ValueError("diagnostic requires an explicit opponent strategy or seed")
    initial_decks = [list(player.deck) for player in battle.players]
    hand_lookup = compile_scalar_hand_lookup(builder, vocabulary)
    for deck in initial_decks:
        for card in deck:
            hand_lookup.resolve(card)
    tower_slots = ("left_tower_hp", "right_tower_hp", "king_tower_hp")
    initial_hp_by_slot = [[float(getattr(player, name)) for name in tower_slots]
                          for player in battle.players]
    tower_setup = None if expanded_receipts else ScalarTowerReceiptSetup.compile(
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
    initial_public_hands = None
    observed_effect_tokens = set()
    began = time.perf_counter()
    with ExitStack() as stack:
        if expanded_receipts:
            from scripts.hog26_scalar_death_actor_adapter import ScalarDeathActorAdapter
            from scripts.hog26_scalar_public_payload_mask import (
                ScalarPublicPayloadMaskProvider,
                ScalarPublicPayloadMaskRules,
                scalar_policy_inputs_with_payload_mask,
            )
            from scripts.hog26_scalar_receipt_session import ScalarReceiptSession

            visible = lambda entity, player: entity.is_visible_to(player)
            session = stack.enter_context(ScalarReceiptSession(
                battle, sorted(set(decks[0]) | set(decks[1])), builder.loader, vocabulary,
                visible_to=visible,
            ))
            outcome_builder = StructuredObservationBuilder(
                token_names=session.token_names, max_entities=builder.max_entities,
                card_semantics_version=builder.card_semantics_version,
                canonical_lane_globals=True,
            )
            actor_adapter = ScalarDeathActorAdapter(
                battle, outcome_builder, session, visible_to=visible,
                hand_lookup=compile_scalar_hand_lookup(outcome_builder, vocabulary),
            )
            extra_tokens = session.extra_public_effect_tokens
            reference_provider = ScalarPublicPayloadMaskProvider(
                provider, ScalarPublicPayloadMaskRules.compile(
                    builder.loader, policy_token_names=provider.tables.token_keys,
                    outcome_token_names=session.token_names,
                ),
            )

            @contextmanager
            def expanded_frame(current):
                session.synchronize_sources()
                yield

            frame = expanded_frame
        else:
            towers = stack.enter_context(tower_setup.recorder())
            spells = stack.enter_context(ScalarSpellReceiptRecorder(
                battle, ("Fireball", "Log"), builder.loader, vocabulary,
            ))
            extra_tokens = tower_setup.extra_public_effect_tokens
        while not battle.game_over:
            if battle.tick > 6000:
                raise RuntimeError("scalar match failed to terminate at its declared horizon")
            if expanded_receipts:
                actors = actor_adapter.build(appearances=session.appearances)
            else:
                appearances = (*towers.appearances, *spells.appearances, *ordinary_appearances)
                actors = build_scalar_reference_actors(
                    battle, builder, appearances=appearances,
                    hand_lookup=hand_lookup,
                    visible_to=lambda entity, player: entity.is_visible_to(player),
                )
            for actor in actors:
                effect_rows = actor.entity_mask & (
                    (actor.entity_features[:, 6] == 1) | (actor.entity_features[:, 7] == 1)
                )
                observed_effect_tokens.update(int(token) for token in actor.entity_ids[effect_rows])
            if not trace:
                initial_public_hands = [actor.hand_ids.tolist() for actor in actors]
            if expanded_receipts:
                inputs, masks = scalar_policy_inputs_with_payload_mask(
                    actors, reference_provider, previous_actions=previous, episode_starts=starts,
                )
            else:
                inputs, masks = scalar_policy_inputs(
                    actors, provider, previous_actions=previous, episode_starts=starts,
                    extra_public_effect_tokens=extra_tokens,
                )
            policy_public = TensorPublicStructuredObservation(**{
                f.name: getattr(inputs, f.name).reshape(1, 2, *getattr(inputs, f.name).shape[2:])
                for f in fields(TensorPublicStructuredObservation)
            })
            with torch.inference_mode():
                selected, _, _, next_state, _ = model.act(inputs, state, deterministic=True)
                if random_opponent is None and not policy_selfplay:
                    scripted = opponent(SimpleNamespace(actor=policy_public, public_action_masks=masks.masks))
            if policy_selfplay:
                actions = selected[:, 0].cpu().numpy().copy()
            elif random_opponent is None:
                actions = scripted[0].numpy().copy()
            else:
                actions = np.full(2, NO_OP_ACTION, dtype=np.int64)
                actions[1 - seat] = random_opponent.sample(masks.masks[0])
            actions[seat] = int(selected[seat, 0])
            if control_noop:
                actions[:] = NO_OP_ACTION
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
            if episode_writer is not None:
                episode_writer.append(
                    actors[seat], inputs, learner_seat=seat, tick=record["tick"],
                    action=int(actions[seat]), success=record["action_success"][seat],
                )
            trace.append(record)
            state, previous, starts = next_state, actions, [False, False]
            if len(trace) % 50 == 0:
                print(json.dumps({"seat": seat, "decisions": len(trace), "tick": battle.tick,
                                  "elapsed_seconds": time.perf_counter() - began}), flush=True)
        terminal = [sum(float(getattr(player, name)) for name in
                        ("left_tower_hp", "right_tower_hp", "king_tower_hp"))
                    for player in battle.players]
        terminal_hp_by_slot = [[float(getattr(player, name)) for name in tower_slots]
                              for player in battle.players]
        fractions = np.asarray(terminal_hp_by_slot) / np.asarray(initial_hp_by_slot)
        return {"seat": seat, "seed": seed if opening_scenario is None else str(seed),
                "complete": True, "ticks": battle.tick,
                "initial_ordered_decks": initial_decks,
                "initial_public_hand_ids": initial_public_hands,
                "opening_scenario_id": None if opening_scenario is None else opening_scenario.scenario_id,
                "opening_cluster_id": None if opening_scenario is None else opening_scenario.cluster_id,
                "random_opponent_seed": None if random_opponent_seed is None else str(random_opponent_seed),
                "policy_selfplay": policy_selfplay,
                "control_noop": control_noop,
                "opponent_rng_sha256": None if random_opponent is None else hashlib.sha256(
                    repr(random_opponent.getstate()).encode()).hexdigest(),
                "expanded_receipts": expanded_receipts,
                "unavailable_public_observations": list(session.unavailable_public_observations)
                if expanded_receipts else [],
                "mask_semantics_digest": masks.semantics_digest,
                "mask_semantics": masks.semantics,
                "extra_public_effect_tokens": list(extra_tokens),
                "decision_visible_effect_token_ids": sorted(observed_effect_tokens),
                "winner": battle.winner, "remaining_tower_hp": terminal,
                "initial_tower_hp_by_slot": initial_hp_by_slot,
                "terminal_tower_hp_by_slot": terminal_hp_by_slot,
                "outcome": ("draw" if battle.winner in (None, -1) else
                            "win" if battle.winner == seat else "loss"),
                "terminal_tower_margin": float(fractions[seat].mean() - fractions[1 - seat].mean()),
                "margin_definition": "mean-own-tower-fraction-minus-mean-enemy-tower-fraction",
                "terminal_tower_hp_weighted_margin": (terminal[seat] / battle._starting_total_tower_hp[seat]
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
        if p.endswith(".py")]
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
