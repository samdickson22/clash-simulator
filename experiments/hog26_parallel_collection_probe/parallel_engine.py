"""One complete game using the unchanged collector engine and isolated RNG streams."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from clasher.rl.simple_pytorch_backend import (
    SimpleTensorStrategyOpponent,
    _compile_public_mask_v2_tables,
    _typed_lookups,
    load_current_client_typed_vocabulary,
)
from clasher.torch_sim.simple_public_mask import SimplePublicMaskV2Provider
from clasher.torch_sim.simple_standard import compile_standard_simple_setup
from scripts.collect_hog26_scalar_pilot import EXTRA_TOKENS
from scripts.evaluate_hog26_simple_policy import load_model
from scripts.hog26_scalar_corpus import ScalarGameCorpusWriter, validate_scalar_corpus
from scripts.hog26_scalar_opening_audit import audit_scalar_opening_metadata
from scripts.hog26_scalar_openings import digest
from scripts.hog26_scalar_pilot_protocol import source_fingerprint
from scripts.hog26_scalar_public_payload_mask import (
    ScalarPublicPayloadMaskProvider,
    ScalarPublicPayloadMaskRules,
)
from scripts.probe_hog26_scalar_complete_replay_20260909 import run
from scripts.probe_hog26_scalar_seeded_replay_20260909 import global_rng_digest


@dataclass(frozen=True)
class Engine:
    root: Path
    model: object
    builder: object
    vocabulary: object
    provider: object
    mask_provider: object
    outcome_tokens: tuple[str, ...]


def initialize(root, canonical_names):
    torch.set_num_threads(1)
    model, builder = load_model(root / "checkpoints/hog26_direct_constant_event_seed1263001/candidate.pt", torch.device("cpu"))
    vocabulary = load_current_client_typed_vocabulary()
    setup = compile_standard_simple_setup(builder.loader, canonical_names, device="cpu", canonical_lane_globals=True)
    lookup, _ = _typed_lookups(setup, builder.loader, vocabulary)
    provider = SimplePublicMaskV2Provider(_compile_public_mask_v2_tables(builder, setup, lookup))
    if any(vocabulary.resolve(card, "card_action") <= 1 or not bool(provider.tables.hand_playable[vocabulary.resolve(card, "card_action")])
           for card in canonical_names):
        raise ValueError("parallel engine has an unresolved playable identity")
    outcome_tokens = (*vocabulary.token_names, *EXTRA_TOKENS)
    mask_provider = ScalarPublicPayloadMaskProvider(provider, ScalarPublicPayloadMaskRules.compile(
        builder.loader, policy_token_names=vocabulary.token_names, outcome_token_names=outcome_tokens))
    return Engine(root, model, builder, vocabulary, provider, mask_provider, outcome_tokens)


def fingerprint(engine, resources):
    return source_fingerprint(engine.root, resource_paths=resources,
                              vocabulary_sha256=engine.vocabulary.sha256,
                              card_definitions=engine.builder.loader.load_card_definitions())


def play(engine, *, plan, case, path, mode):
    resources = {key: value["path"] for key, value in plan["source_authority"]["resources"].items()}
    if fingerprint(engine, resources) != plan["source_authority"]:
        raise ValueError("parallel engine source differs before game")
    schedule, seat = case["schedule"], case["seat"]
    scenarios = audit_scalar_opening_metadata(schedule["metadata"], expected_authority=schedule["external_authority"])
    scenario = scenarios[case["ordinal"]]
    if scenario.ordinal != case["ordinal"] or seat not in schedule["learner_seats"]:
        raise ValueError("parallel case identity differs")
    style = schedule["external_authority"]["opponent_style"]
    metadata = {"schema": "clasher.scalar-pilot-game-metadata.v1", "mode": mode,
                "source_authority_sha256": digest(plan["source_authority"]), "plan_sha256": digest(plan),
                "opening_metadata": schedule["metadata"], "opening_authority": schedule["external_authority"],
                "scenario_id": scenario.scenario_id, "cluster_id": scenario.cluster_id,
                "ordinal": scenario.ordinal, "learner_seat": seat, "family_id": schedule["family_id"],
                "style": style, "outcome_token_names": list(engine.outcome_tokens),
                "policy_token_names": list(engine.vocabulary.token_names),
                "mask_semantics_digest": engine.mask_provider.semantics_digest,
                "retention": "all predecision learner rows through first actual terminal; no filtering by success/outcome"}
    writer = ScalarGameCorpusWriter(path, metadata)
    opponent = None if style == "random" else SimpleTensorStrategyOpponent(engine.builder, strategy_name=style, device=torch.device("cpu"))
    streams = dict(scenario.stream_seeds)
    rng_before = global_rng_digest()
    result = run(engine.model, engine.builder, engine.vocabulary, engine.provider, opponent,
                 seat=seat, seed=streams["battle"], expanded_receipts=True, opening_scenario=scenario,
                 random_opponent_seed=streams["opponent"] if style == "random" else None, episode_writer=writer)
    if global_rng_digest() != rng_before or fingerprint(engine, resources) != plan["source_authority"]:
        raise ValueError("parallel game changed global RNG or pinned source")
    expected_decks = [list(deck) for deck in scenario.world_decks(seat)]
    expected_hand = [[engine.vocabulary.resolve(card, "card_action") for card in deck[:5]] for deck in expected_decks]
    if (result["initial_ordered_decks"] != expected_decks or result["initial_public_hand_ids"] != expected_hand
            or result["extra_public_effect_tokens"] != list(EXTRA_TOKENS)
            or result["mask_semantics_digest"] != engine.mask_provider.semantics_digest):
        raise ValueError("parallel runtime opening or mask differs")
    writer.finish(terminal_tick=result["ticks"], winner=result["winner"], learner_seat=seat,
                  terminal_tower_hp=result["terminal_tower_hp_by_slot"], initial_tower_hp=result["initial_tower_hp_by_slot"],
                  actual_terminal=result["complete"])
    audit = validate_scalar_corpus(path, expected_metadata=metadata)
    if audit["terminal_tower_margin"] != result["terminal_tower_margin"]:
        raise ValueError("parallel runtime and independent margin audit differ")
    return audit


def compare_arrays(original_path, replay_path):
    with np.load(original_path, allow_pickle=False) as original, np.load(replay_path, allow_pickle=False) as replay:
        if set(original.files) != set(replay.files):
            raise ValueError("parallel replay field inventory differs")
        compared = []
        for key in original.files:
            if key == "metadata_json":
                continue
            a, b = original[key], replay[key]
            if a.dtype != b.dtype or a.shape != b.shape or a.tobytes() != b.tobytes():
                raise ValueError("parallel replay array differs: " + key)
            compared.append(key)
    return compared
