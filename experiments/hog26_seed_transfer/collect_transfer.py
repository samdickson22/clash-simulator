"""Collect an externally pinned scalar pilot, or excluded preflight games."""

import argparse
import fcntl
import hashlib
import json
from pathlib import Path

import torch

from clasher.rl.simple_pytorch_backend import (
    SimpleTensorStrategyOpponent,
    _compile_public_mask_v2_tables,
    _typed_lookups,
    load_current_client_typed_vocabulary,
)
from clasher.torch_sim.simple_public_mask import SimplePublicMaskV2Provider
from clasher.torch_sim.simple_standard import compile_standard_simple_setup
from scripts.evaluate_hog26_simple_policy import load_model
from scripts.hog26_scalar_corpus import ScalarGameCorpusWriter, validate_scalar_corpus
from scripts.hog26_scalar_opening_audit import audit_scalar_opening_metadata
from scripts.hog26_scalar_openings import CanonicalOpeningSchedule, digest
from transfer_protocol import (
    assert_source_unchanged,
    build_pilot_plan,
    source_fingerprint,
    validate_pilot_plan,
)
from scripts.hog26_scalar_public_payload_mask import (
    ScalarPublicPayloadMaskProvider,
    ScalarPublicPayloadMaskRules,
)
from scripts.probe_hog26_scalar_complete_replay_20260909 import run
from scripts.probe_hog26_scalar_seeded_replay_20260909 import global_rng_digest

EXTRA_TOKENS = ("projectile:TowerPrincessProjectile", "public_tower_shot:king",
                "public_effect:chain_bolt", "building_body:SkeletonContainerNew")


def write_json(path, value):
    path = Path(path)
    if path.exists():
        if json.loads(path.read_text()) != value:
            raise ValueError(f"existing audit differs: {path}")
        return
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("preflight", "collect"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--preflight", type=Path)
    args = parser.parse_args()
    if args.output_dir.exists() and not args.resume:
        raise ValueError("existing collection requires explicit --resume")
    if args.resume and not args.output_dir.is_dir():
        raise ValueError("resume requires an existing collection directory")
    if args.mode == "collect" and (args.plan is None or args.preflight is None):
        raise ValueError("collection needs a separately frozen plan and preflight pin")
    root = Path(__file__).resolve().parents[2]
    torch.set_num_threads(1)
    checkpoint = root / "checkpoints/hog26_direct_constant_event_seed1263001/candidate.pt"
    model, builder = load_model(checkpoint, torch.device("cpu"))
    vocabulary = load_current_client_typed_vocabulary()
    resource_paths = {"checkpoint": checkpoint, "card_data": Path(builder.loader.data_file)}

    def fingerprint():
        return source_fingerprint(root, resource_paths=resource_paths,
                                  vocabulary_sha256=load_current_client_typed_vocabulary().sha256,
                                  card_definitions=builder.loader.load_card_definitions())

    authority = fingerprint()
    if args.mode == "collect":
        plan = json.loads(args.plan.read_text())
        preflight = json.loads(args.preflight.read_text())
        validate_pilot_plan(plan, authority, expected_preflight=preflight)
        if not plan["frozen"] or not plan["collection_allowed"]:
            raise ValueError("collection is not authorized by the frozen plan")
        schedules = plan["schedules"]
    else:
        plan = build_pilot_plan(authority=authority)
        schedules = []
        # One training deck per style, both seats. These seeds and roles never
        # become pilot fitting rows. Failures are not selected away.
        for style_index, deck_index in enumerate((0, 13, 20, 8, 24, 28)):
            selected = plan["schedules"][style_index * 32 + deck_index]
            pin = dict(selected["external_authority"])
            pin.update(role="diagnostic-corpus-preflight", campaign_seed=str(1279241 + style_index))
            metadata = CanonicalOpeningSchedule(
                campaign_seed=int(pin["campaign_seed"]), role=pin["role"], deck_name=pin["deck_name"],
                opponent_style=pin["opponent_style"], learner_template=pin["relative_templates"][0],
                opponent_template=pin["relative_templates"][1], canonical_names=pin["canonical_names"], episodes=1,
            ).metadata()
            schedules.append({**selected, "external_authority": pin, "metadata": metadata})
    setup = compile_standard_simple_setup(builder.loader, authority["contract"]["canonical_names"],
                                          device="cpu", canonical_lane_globals=True)
    lookup, _ = _typed_lookups(setup, builder.loader, vocabulary)
    provider = SimplePublicMaskV2Provider(_compile_public_mask_v2_tables(builder, setup, lookup))
    outcome_tokens = (*vocabulary.token_names, *EXTRA_TOKENS)
    for card in authority["contract"]["canonical_names"]:
        token = vocabulary.resolve(card, "card_action")
        if token <= 1 or not bool(provider.tables.hand_playable[token]):
            raise ValueError(f"configured card has no playable public action identity: {card}")
    mask_provider = ScalarPublicPayloadMaskProvider(provider, ScalarPublicPayloadMaskRules.compile(
        builder.loader, policy_token_names=vocabulary.token_names, outcome_token_names=outcome_tokens))
    args.output_dir.mkdir(parents=True, exist_ok=args.resume)
    run_lease = (args.output_dir / ".collector.lock").open("a+")
    fcntl.flock(run_lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    write_json(args.output_dir / "run_plan.json", plan)
    results = []
    for schedule_index, schedule in enumerate(schedules):
        scenarios = audit_scalar_opening_metadata(schedule["metadata"], expected_authority=schedule["external_authority"])
        style = schedule["external_authority"]["opponent_style"]
        for scenario in scenarios:
            for seat in schedule["learner_seats"]:
                assert_source_unchanged(authority, fingerprint())
                streams = dict(scenario.stream_seeds)
                metadata = {"schema": "clasher.scalar-pilot-game-metadata.v1", "mode": args.mode,
                            "source_authority_sha256": digest(authority), "plan_sha256": digest(plan),
                            "opening_metadata": schedule["metadata"], "opening_authority": schedule["external_authority"],
                            "scenario_id": scenario.scenario_id, "cluster_id": scenario.cluster_id,
                            "ordinal": scenario.ordinal, "learner_seat": seat, "family_id": schedule["family_id"],
                            "style": style, "outcome_token_names": list(outcome_tokens),
                            "policy_token_names": list(vocabulary.token_names),
                            "mask_semantics_digest": mask_provider.semantics_digest,
                            "retention": "all predecision learner rows through first actual terminal; no filtering by success/outcome"}
                path = args.output_dir / f"game-{schedule_index:03d}-{scenario.ordinal:03d}-{seat}.npz"
                result = None
                if not path.exists():
                    writer = ScalarGameCorpusWriter(path, metadata)
                    opponent = None if style == "random" else SimpleTensorStrategyOpponent(
                        builder, strategy_name=style, device=torch.device("cpu"))
                    rng_before = global_rng_digest()
                    result = run(model, builder, vocabulary, provider, opponent, seat=seat, seed=streams["battle"],
                                 expanded_receipts=True, opening_scenario=scenario,
                                 random_opponent_seed=streams["opponent"] if style == "random" else None,
                                 episode_writer=writer)
                    assert_source_unchanged(authority, fingerprint())
                    if global_rng_digest() != rng_before:
                        raise AssertionError("game consumed process-global RNG")
                    expected_decks = [list(deck) for deck in scenario.world_decks(seat)]
                    expected_hand = [[vocabulary.resolve(card, "card_action") for card in deck[:5]] for deck in expected_decks]
                    if (result["initial_ordered_decks"] != expected_decks or result["initial_public_hand_ids"] != expected_hand
                            or result["extra_public_effect_tokens"] != list(EXTRA_TOKENS)
                            or result["mask_semantics_digest"] != mask_provider.semantics_digest):
                        raise AssertionError("runtime opening or public appearance/mask authority differs")
                    writer.finish(terminal_tick=result["ticks"], winner=result["winner"], learner_seat=seat,
                                  terminal_tower_hp=result["terminal_tower_hp_by_slot"],
                                  initial_tower_hp=result["initial_tower_hp_by_slot"], actual_terminal=result["complete"])
                audit = validate_scalar_corpus(path, expected_metadata=metadata)
                if result is not None and audit["terminal_tower_margin"] != result["terminal_tower_margin"]:
                    raise AssertionError("independent corpus and runtime margin disagree")
                audit.pop("metadata")
                row = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                       "family_id": schedule["family_id"], "style": style, "learner_seat": seat,
                       "scenario_id": scenario.scenario_id, "cluster_id": scenario.cluster_id, **audit}
                results.append(row)
                write_json(path.with_suffix(".audit.json"), row)
                print(json.dumps({"completed_games": len(results), **row}), flush=True)
    assert_source_unchanged(authority, fingerprint())
    published = {path.name for path in args.output_dir.glob("game-*.npz")}
    if published != {row["path"] for row in results}:
        raise ValueError("unexpected game files in collection")
    expected = 384 if args.mode == "collect" else 12
    if len(results) != expected:
        raise AssertionError("collection quota incomplete")
    write_json(args.output_dir / "complete.json", {
        "status": "complete-audited", "mode": args.mode, "source_authority_sha256": digest(authority),
        "plan_sha256": digest(plan), "games": results, "game_count": len(results),
        "rows": sum(row["rows"] for row in results), "fitting_allowed": False,
    })


if __name__ == "__main__":
    main()
