"""Admitted, bounded public-script demonstration collection and fresh warm start."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

import numpy as np
import torch

from clasher.battle import STANDARD_MATCH_TICKS

from .imitation import fit_imitation_corpus, load_corpus
from .public_scripted_opponent import SUPPORTED_CARDS
from .scripted_demonstrations import collect_public_script_game
from .selfplay_env import SelfPlayBattleEnv, resolve_match_horizon
from .structured_obs import StructuredObservationBuilder
from .train_recurrent import maybe_silence_stdio

MAX_DEMONSTRATION_DECISIONS = 500_000
FULL_GAME_DECISION_LIMIT = math.ceil(resolve_match_horizon(STANDARD_MATCH_TICKS, 4) / 5)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def _training_deck_plan(path: Path, *, seed: int) -> tuple[list[dict], dict[str, int]]:
    payload = json.loads(path.read_text())
    if payload.get("role") != "training":
        raise ValueError("script collection requires the training deck role")
    decks = payload["decks"]
    for deck in decks:
        if deck.get("role") != "training" or len(deck["cards"]) != 8 or len(set(deck["cards"])) != 8 or not set(deck["cards"]) <= SUPPORTED_CARDS:
            raise ValueError("invalid or out-of-scope training deck")
        weight = float(deck.get("sampling_weight", 1.0))
        if not math.isfinite(weight) or weight <= 0:
            raise ValueError("invalid training deck sampling weight")
    by_name = {deck["name"]: deck for deck in decks}

    def family(deck: dict) -> str:
        seen = set()
        while deck.get("parent"):
            if deck["name"] in seen or deck["parent"] not in by_name:
                raise ValueError("training deck parent graph is incomplete or cyclic")
            seen.add(deck["name"])
            deck = by_name[deck["parent"]]
        return deck["name"]

    families = sorted({family(deck) for deck in decks})
    if len(families) < 2:
        raise ValueError("warm start needs two disjoint training-role families")
    rng = np.random.default_rng(seed)
    validation = set(rng.permutation(families)[:max(1, round(len(families) * .2))])
    splits = {name: int(name in validation) for name in families}
    return [deck | {"family_id": family(deck)} for deck in decks], splits


def _draw_deck(rng, decks, *, fit_split=None, splits=None):
    eligible = decks if fit_split is None else [deck for deck in decks if splits[deck["family_id"]] == fit_split]
    weights = np.asarray([deck.get("sampling_weight", 1.) for deck in eligible], dtype=np.float64)
    return eligible[int(rng.choice(len(eligible), p=weights / weights.sum()))]


def _merge_complete_games(game_paths: list[Path], output: Path, *, provenance: dict) -> dict:
    """Merge compressed game shards through owned disk arrays, trimming padding."""
    if len(game_paths) < 2:
        raise ValueError("warm start needs at least two complete games")
    summaries = []
    entity_width = 1
    keys = None
    token_names = None
    seen_episodes = set()
    for path in game_paths:
        metadata, arrays = load_corpus(path)
        if metadata.public_contract_version != 4 or metadata.label_source != "public-script":
            raise ValueError("warm-start merge only accepts public-v4 script games")
        game_provenance = json.loads(metadata.provenance or "{}")
        if not game_provenance.get("complete_game") or game_provenance.get("role") != "training":
            raise ValueError("warm-start shard does not declare a complete training-role game")
        if token_names is None:
            token_names = metadata.token_names
        if metadata.token_names != token_names or metadata.decision_interval != 5:
            raise ValueError("warm-start shard vocabulary or timing changed")
        episode_ids = np.unique(arrays["episode_ids"])
        if len(episode_ids) != 1 or int(episode_ids[0]) in seen_episodes:
            raise ValueError("warm-start shards require distinct complete episode IDs")
        seen_episodes.add(int(episode_ids[0]))
        if keys is None:
            keys = set(arrays)
        elif keys != set(arrays):
            raise ValueError("demonstration shards have different field contracts")
        width = np.count_nonzero(arrays["entity_mask"], axis=-1)
        if np.any(arrays["entity_mask"][..., 1:] & ~arrays["entity_mask"][..., :-1]):
            raise ValueError("demonstration entity rows are not packed")
        entity_width = max(entity_width, int(width.max()))
        summaries.append((path, metadata, len(arrays["expert_actions"])))
    template = summaries[0][1]
    rows = sum(item[2] for item in summaries)
    decisions = sum(item[1].decisions for item in summaries)
    if decisions > MAX_DEMONSTRATION_DECISIONS:
        raise ValueError("script corpus exceeds the 500000-opportunity ceiling")
    metadata = replace(template, created_at=datetime.now(timezone.utc).isoformat(),
        decisions=decisions, samples=rows, provenance=json.dumps(provenance, sort_keys=True))
    with tempfile.TemporaryDirectory(prefix="merge-", dir=output.parent) as directory:
        merged = {}
        offset = 0
        for path, _, count in summaries:
            _, arrays = load_corpus(path)
            for name, values in arrays.items():
                if name.startswith("entity_"):
                    values = values[:, :entity_width]
                if name not in merged:
                    merged[name] = np.lib.format.open_memmap(Path(directory) / f"{name}.npy", mode="w+", dtype=values.dtype, shape=(rows, *values.shape[1:]))
                if values.dtype != merged[name].dtype or values.shape[1:] != merged[name].shape[1:]:
                    raise ValueError(f"incompatible demonstration field {name}")
                merged[name][offset:offset + count] = values
            offset += count
        with output.open("xb") as stream:
            np.savez_compressed(stream, metadata_json=np.asarray(metadata.to_json()), **merged)
        del merged
    return {"path": str(output), "sha256": _sha(output), "samples": rows,
            "decisions": decisions, "games": len(game_paths), "stored_entity_width": entity_width}


def run_script_warmstart(*, config_path: Path, admission_path: Path, seed: int,
                         output_checkpoint: Path, decisions: int | None = None,
                         epochs: int = 1, batch_size: int = 128,
                         device: str | None = None, resume: bool = False) -> dict:
    # Shared validation happens before any environment creation or data writes.
    from .council_pilot import (load_pilot_config, require_pilot_admission,
        build_council_model_config)

    config_path, admission_path = config_path.resolve(), admission_path.resolve()
    output_checkpoint = output_checkpoint.resolve()
    config = load_pilot_config(config_path)
    require_pilot_admission(config, admission_path, levels=(11,))
    from .council_budget import budget_snapshot, require_owned_budget
    resource_ledger = Path(config.output_dir) / "resource-budget.json"
    if os.environ.get("CLASHER_PILOT_BUDGET") != str(resource_ledger):
        raise ValueError("warm start must run under the shared pilot compute ledger")
    require_owned_budget(resource_ledger)
    budget = config.warmstart_decisions if decisions is None else decisions
    if not 2 * FULL_GAME_DECISION_LIMIT <= budget <= min(MAX_DEMONSTRATION_DECISIONS, config.warmstart_decisions):
        raise ValueError("decision ceiling must allow at least two worst-case complete games and be <=500000/config limit")
    if seed not in config.seeds or epochs < 1 or batch_size < 1:
        raise ValueError("declare a pilot seed and positive fit counts")
    if os.environ.get("CLASHER_ROOT") != str(Path(config.gamedata_path).parent):
        raise ValueError("warm start requires a fresh process bound to the admitted CLASHER_ROOT")
    if Path(__file__).resolve().parents[3] != Path(config.source_root).resolve():
        raise ValueError("warm start imported source outside the admitted source root")
    from clasher.paths import gamedata_path
    if gamedata_path(must_exist=True).resolve() != Path(config.gamedata_path).resolve():
        raise ValueError("default card loader differs from admitted game data")
    torch.set_num_threads(config.torch_threads)
    selected_device = config.device if device is None else device
    learner_device = torch.device(selected_device)
    if learner_device.type == "mps" and not torch.backends.mps.is_available():
        raise ValueError("MPS is unavailable")
    if learner_device.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA is unavailable")
    decks_path = Path(config.training_decks_path)
    decks, splits = _training_deck_plan(decks_path, seed=seed)
    run_dir = output_checkpoint.parent / f"{output_checkpoint.stem}-demonstrations"
    control_checkpoint = output_checkpoint.with_name(f"{output_checkpoint.stem}-random-control.pt")
    if output_checkpoint.exists():
        raise FileExistsError("warm-start checkpoint already exists")
    if run_dir.exists() and not resume:
        raise FileExistsError("demonstrations already exist; use --resume with the identical frozen plan")
    if control_checkpoint.exists() and not resume:
        raise FileExistsError("warm-start control checkpoint already exists")
    plan = {"schema": "clasher.council-script-warmstart.v1", "seed": seed,
        "role": "training", "admission_path": str(admission_path.resolve()),
        "admission_sha256": _sha(admission_path), "pilot_config_sha256": _sha(config_path),
        "training_decks_path": str(decks_path), "training_decks_sha256": _sha(decks_path),
        "decision_ceiling": budget, "complete_game_reservation": FULL_GAME_DECISION_LIMIT,
        "fit_split_by_family": splits, "teacher_levels": [11],
        "teacher_styles": ["balanced", "pressure", "defense"],
        "sampling": "all-five-tick-opportunities; no play/wait reweight",
        "epochs": epochs, "batch_size": batch_size, "sequence_length": 128, "device": selected_device,
        "recurrence": "current-weight-full-episode-prefix"}
    paths = []
    episodes = []
    retained = 0
    if run_dir.exists():
        if json.loads((run_dir / "plan.json").read_text()) != plan:
            raise ValueError("resume plan differs from the admitted frozen collection")
        for index, record_path in enumerate(sorted(run_dir.glob("game-*.json"))):
            record = json.loads(record_path.read_text())
            path = run_dir / f"game-{index:05d}.npz"
            if record_path.stem != path.stem or str(path) != record["path"] or _sha(path) != record["sha256"]:
                raise ValueError("resume found a missing, reordered or changed game shard")
            paths.append(path)
            episodes.append(record)
            retained += record["decisions"]
        if set(run_dir.glob("game-*.npz")) != set(paths):
            raise ValueError("incomplete game publication requires audit before resume")
    else:
        output_checkpoint.parent.mkdir(parents=True, exist_ok=True)
        run_dir.mkdir()
        _write_json(run_dir / "plan.json", plan)
    if control_checkpoint.exists():
        attempt = 1
        while control_checkpoint.exists():
            control_checkpoint = output_checkpoint.with_name(f"{output_checkpoint.stem}-random-control-restart-{attempt:03d}.pt")
            attempt += 1
    builder = StructuredObservationBuilder(decks_path=decks_path, card_vocab=sorted(SUPPORTED_CARDS),
        max_entities=128, canonical_perspective=True, canonical_lane_globals=True,
        public_history_slots=4, public_seen_card_slots=8, card_semantics_version=4,
        public_entity_levels=True, public_hand_levels=True)
    while retained + FULL_GAME_DECISION_LIMIT <= budget:
        episode = len(paths)
        # Per-game RNG makes resumption independent of earlier process state.
        rng = np.random.default_rng(seed + 1009 * episode)
        # Guarantee a complete diagnostic holdout without cutting trajectories.
        forced_split = episode if episode < 2 else None
        learner_deck = _draw_deck(rng, decks, fit_split=forced_split, splits=splits)
        fit_split = splits[learner_deck["family_id"]]
        opponent_deck = _draw_deck(rng, decks, fit_split=fit_split, splits=splits)
        seat = episode % 2
        ordered_decks = (learner_deck["cards"], opponent_deck["cards"])
        if seat == 1:
            ordered_decks = tuple(reversed(ordered_decks))
        styles = tuple(str(rng.choice(plan["teacher_styles"])) for _ in range(2))
        episode_seed = seed + 1009 * episode
        env = SelfPlayBattleEnv(decks_path=decks_path, seed=episode_seed,
            decision_interval_ticks=5, max_ticks=STANDARD_MATCH_TICKS,
            canonical_perspective=True, canonical_lane_globals=True,
            public_contract_version=4, tower_levels=(11, 11), card_levels=({}, {}))
        env._structured_obs_builder = builder
        with maybe_silence_stdio(True):
            env.reset(seed=episode_seed, ordered_decks=ordered_decks)
            game = collect_public_script_game(env, builder, seed=episode_seed,
                episode_id=episode, role="training", family_id=learner_deck["family_id"],
                learner_player_id=seat, styles=styles, max_decisions=FULL_GAME_DECISION_LIMIT)
        if game.metadata.decisions > FULL_GAME_DECISION_LIMIT:
            raise ValueError("full match exceeded its reserved opportunities")
        provenance = json.loads(game.metadata.provenance)
        provenance.update({"opponent_family_id": opponent_deck["family_id"],
            "learner_deck_name": learner_deck["name"], "opponent_deck_name": opponent_deck["name"],
            "fit_split": "validation" if fit_split else "training"})
        controls = game.controls | {"fit_split": np.full(game.metadata.samples, fit_split, dtype=np.int8),
            "source_family_ids": np.full(game.metadata.samples, learner_deck["family_id"], dtype="U128")}
        game = replace(game, controls=controls, metadata=replace(game.metadata, provenance=json.dumps(provenance, sort_keys=True)))
        path = run_dir / f"game-{episode:05d}.npz"
        game.save(path)
        paths.append(path)
        retained += game.metadata.decisions
        record = {"path": str(path), "sha256": _sha(path), "decisions": game.metadata.decisions,
            "provenance": provenance, "rejected_commands": int((~game.execution["accepted_commands"]).sum())}
        episodes.append(record)
        _write_json(run_dir / f"game-{episode:05d}.json", record)
        print(json.dumps({"completed_games": len(paths), "retained_decisions": retained, "decision_ceiling": budget}), flush=True)
    corpus_path = run_dir / "corpus.npz"
    if corpus_path.exists():
        saved = json.loads((run_dir / "collection.json").read_text())
        if saved["plan"] != plan or saved["episodes"] != episodes or saved["sha256"] != _sha(corpus_path):
            raise ValueError("resume corpus differs from the completed collection receipt")
        corpus = {key: saved[key] for key in ("path", "sha256", "samples", "decisions", "games", "stored_entity_width")}
    else:
        corpus = _merge_complete_games(paths, corpus_path, provenance={"role": "training",
            "teacher": "public-script", "complete_games": True, "games": episodes,
            "fit_split_by_family": splits, "plan_sha256": _sha(run_dir / "plan.json")})
        _write_json(run_dir / "collection.json", corpus | {"plan": plan, "episodes": episodes})
    # A concurrently changed source/config invalidates fitting without discarding
    # the already retained games or their admission provenance.
    require_pilot_admission(config, admission_path, levels=(11,))
    model_config = build_council_model_config(builder)
    metrics = fit_imitation_corpus(corpus_path=corpus_path, output_checkpoint=output_checkpoint,
        control_checkpoint=control_checkpoint, decks_path=decks_path, seed=seed,
        epochs=epochs, batch_size=batch_size, learning_rate=1e-4,
        validation_fraction=.2, device=learner_device,
        d_model=128, num_heads=4, actor_layers=4, critic_layers=2, memory_size=256,
        card_semantics_version=4, model_config_override=model_config,
        checkpoint_metadata={"gamedata_sha256": config.gamedata_sha256,
            "resource_budget": budget_snapshot(resource_ledger),
            "strategy_sha256": config.strategy_sha256, "source_pins_sha256": _sha(Path(config.source_pins_path)),
            "training_decks_sha256": config.training_decks_sha256,
            "admission_sha256": _sha(admission_path), "warmstart_plan_sha256": _sha(run_dir / "plan.json")},
        sequence_length=128, trim_entity_padding=True, train_on_forced_actions=True,
        canonical_lane_globals=True, imitation_objective="exact")
    receipt = {"schema": "clasher.council-script-warmstart-result.v1", "plan": plan,
        "corpus": corpus, "fit": metrics, "checkpoint": str(output_checkpoint),
        "checkpoint_sha256": _sha(output_checkpoint), "control_checkpoint": str(control_checkpoint),
        "control_checkpoint_sha256": _sha(control_checkpoint)}
    _write_json(run_dir / "result.json", receipt)
    return receipt
