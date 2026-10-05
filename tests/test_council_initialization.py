"""Council python-backend initialization: fail-closed binding and seed invariance.

Synthetic fixtures only (tmp): a two-game always-wait corpus with a replaced
simulator step is fitted by the real ``fit_imitation_corpus`` at the full council
actor contract, producing the scripted checkpoint and its matched control with a
typed BudgetSnapshot, exactly as the warm start writes them. This checks the
initialization plumbing, not gameplay fitting or playing strength.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from clasher.rl.council_pilot import (
    load_pilot_config,
    publish_initial_pool,
    require_initialized_weights,
    state_dict_sha256,
    validate_council_initial_policy,
)
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.train_recurrent import _load_initial_policy_state

CONFIG = Path("configs/council-pilot-local.toml")


def _active_budget_snapshot(tmp_path):
    """The warm start runs as the ledger's active child, so the snapshot is nested."""
    from clasher.rl.council_budget import BudgetSnapshot, budget_snapshot

    ledger = tmp_path / "resource-budget.json"
    ledger.write_text(json.dumps({
        "schema": "clasher.local-pilot-budget.v1",
        "config_sha256": "a" * 64,
        "cpu_core_hour_ceiling": 4608.0,
        "accelerator_hour_ceiling": 72.0,
        "cpu_core_hours_used": 1.25,
        "accelerator_hours_used": 0.0,
        "active": {
            "argv": ["python", "-B", "scripts/run_council_warmstart.py"],
            "started_at": 1.0, "cpu_cores": 2, "accelerator": False, "pid": 4242,
        },
        "jobs": [],
    }))
    snapshot = budget_snapshot(ledger)
    BudgetSnapshot.model_validate(snapshot)
    return snapshot


def _synthetic_council_corpus(tmp_path, monkeypatch):
    """Two complete two-decision always-wait games at the council entity width."""
    from dataclasses import replace

    import numpy as np

    from clasher.rl.council_warmstart import _merge_complete_games
    from clasher.rl.public_scripted_opponent import (
        SUPPORTED_CARDS,
        PublicScriptedOpponent,
    )
    from clasher.rl.scripted_demonstrations import collect_public_script_game
    from clasher.rl.selfplay_env import SelfPlayBattleEnv, StepInfo
    from clasher.rl.structured_obs import StructuredObservationBuilder

    decks_path = Path(load_pilot_config(CONFIG).training_decks_path)
    # Identical builder to council_warmstart.run_script_warmstart.
    builder = StructuredObservationBuilder(
        decks_path=decks_path, card_vocab=sorted(SUPPORTED_CARDS), max_entities=128,
        canonical_perspective=True, canonical_lane_globals=True,
        public_history_slots=4, public_seen_card_slots=8, card_semantics_version=4,
        public_entity_levels=True, public_hand_levels=True,
    )
    monkeypatch.setattr(PublicScriptedOpponent, "select_action", lambda self, packet: 2304)
    paths = []
    for split in (0, 1):
        env = SelfPlayBattleEnv(
            decks_path=decks_path, decision_interval_ticks=5, seed=3 + split,
            canonical_lane_globals=True, public_contract_version=4,
        )
        env._structured_obs_builder = builder
        env.reset(seed=3 + split)

        def synthetic_step(actions, *, pre_action_masks, env=env):
            env.battle.tick += 5
            env.battle.game_over = env.battle.tick == 10
            return {0: 0.0, 1: 0.0}, env.battle.game_over, StepInfo({0: True, 1: True}, 5)

        monkeypatch.setattr(env, "step", synthetic_step)
        game = collect_public_script_game(
            env, builder, seed=3 + split, episode_id=split, role="training",
            family_id=f"synthetic-{split}",
        )
        game = replace(game, controls=game.controls | {
            "episode_ids": np.full(game.metadata.samples, split, dtype=np.int64),
            "fit_split": np.full(game.metadata.samples, split, dtype=np.int8),
        })
        path = tmp_path / f"game-{split}.npz"
        game.save(path)
        paths.append(path)
    corpus = tmp_path / "corpus.npz"
    _merge_complete_games(paths, corpus, provenance={"role": "training", "complete_games": True})
    return corpus, decks_path, builder


@pytest.fixture(scope="module")
def council_fixture(tmp_path_factory):
    from clasher.rl.council_pilot import build_council_model_config
    from clasher.rl.imitation import fit_imitation_corpus

    tmp_path = tmp_path_factory.mktemp("council-init")
    monkeypatch = pytest.MonkeyPatch()
    try:
        corpus, decks_path, builder = _synthetic_council_corpus(tmp_path, monkeypatch)
    finally:
        monkeypatch.undo()
    real = load_pilot_config(CONFIG)
    pins = tmp_path / "source-pins.json"
    pins.write_text(json.dumps({"src/clasher/rl/council_pilot.py": "0" * 64}))
    admission = tmp_path / "admission-placeholder.json"
    admission.write_text("{}\n")
    plan = tmp_path / "plan.json"
    plan.write_text("{}\n")
    snapshot = _active_budget_snapshot(tmp_path)  # ledger at tmp/resource-budget.json
    pilot = real.model_copy(
        update={
            "output_dir": str(tmp_path),
            "source_pins_path": str(pins),
            "gamedata_sha256": "a" * 64,
        }
    )
    metadata = {
        "gamedata_sha256": pilot.gamedata_sha256,
        "strategy_sha256": pilot.strategy_sha256,
        "training_decks_sha256": pilot.training_decks_sha256,
        "source_pins_sha256": _sha(pins),
        "admission_sha256": _sha(admission),
        "warmstart_plan_sha256": _sha(plan),
        "resource_budget": snapshot,
    }
    config = build_council_model_config(builder)
    torch.manual_seed(7)
    fit_imitation_corpus(
        corpus_path=corpus, output_checkpoint=tmp_path / "scripted.pt",
        control_checkpoint=tmp_path / "scripted-random-control.pt",
        decks_path=decks_path, seed=2901, epochs=1, batch_size=4,
        learning_rate=1e-3, validation_fraction=0.5, device=torch.device("cpu"),
        d_model=128, num_heads=4, actor_layers=4, critic_layers=2, memory_size=256,
        model_config_override=config, checkpoint_metadata=metadata,
        card_semantics_version=4, sequence_length=4, train_on_forced_actions=True,
        trim_entity_padding=True, canonical_lane_globals=True,
        imitation_objective="exact",
    )
    paths = {"scripted": tmp_path / "scripted.pt", "scratch": tmp_path / "scripted-random-control.pt"}
    pool = tmp_path / "opponents" / "pool.json"
    publish_initial_pool(
        pilot, pool_path=pool, initialization_paths=(paths["scripted"], paths["scratch"])
    )
    return SimpleNamespace(
        pilot=pilot, builder=builder, config=config, paths=paths, pool=pool,
        admission=admission, snapshot=snapshot, tmp_path=tmp_path,
    )


def _sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _args(fixture, arm, **overrides):
    values = {
        "council_admission": fixture.admission,
        "council_arm": arm,
        "council_opponent_pool": fixture.pool,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _load(path):
    return torch.load(path, map_location="cpu", weights_only=False)


def _initialize_like_trainer(fixture, arm, seed):
    """Mirror train_recurrent.main: seed, build, validate, strict load, verify."""
    payload = _load(fixture.paths[arm])
    torch.manual_seed(seed)
    record = validate_council_initial_policy(
        fixture.pilot, payload, initialization_path=fixture.paths[arm],
        args=_args(fixture, arm), builder=fixture.builder,
    )
    config = PolicyConfig.from_dict(payload["model_config"])
    model = ClasherPolicy(config, fixture.builder.card_stat_features)
    fresh_digest = state_dict_sha256(model.state_dict())
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, eps=1e-5, weight_decay=1e-5)
    model.load_state_dict(payload["model_state_dict"], strict=True)
    return fresh_digest, require_initialized_weights(model, record, optimizer), record


def test_budget_snapshot_initializer_gives_identical_weights_across_pilot_seeds(
    council_fixture,
):
    seeds = council_fixture.pilot.seeds
    assert len(seeds) == 3
    results = {
        arm: [_initialize_like_trainer(council_fixture, arm, seed) for seed in seeds]
        for arm in ("scripted", "scratch")
    }
    for arm, rows in results.items():
        payload = _load(council_fixture.paths[arm])
        assert payload["resource_budget"] == council_fixture.snapshot
        expected = state_dict_sha256(payload["model_state_dict"])
        # The seeds do change fresh construction, but never the initialized learner.
        assert len({fresh for fresh, _, _ in rows}) == 3
        assert {loaded for _, loaded, _ in rows} == {expected}
        for _, _, record in rows:
            assert record["arm"] == arm and record["optimizer_reset"]
            assert not record["checkpoint_optimizer_state_present"]
    assert results["scripted"][0][1] != results["scratch"][0][1]


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda p: p | {"token_names": tuple(reversed(p["token_names"]))}, "vocabulary"),
        (lambda p: p | {"model_config": p["model_config"] | {"card_semantics_version": 3}}, "card_semantics_version"),
        (lambda p: p | {"model_config": p["model_config"] | {"public_contract_version": 3}}, "public_contract_version"),
        (lambda p: p | {"model_config": p["model_config"] | {"d_model": 64}}, "actor contract"),
        (lambda p: p | {"gamedata_sha256": "b" * 64}, "gamedata_sha256"),
        (lambda p: p | {"strategy_sha256": "b" * 64}, "strategy_sha256"),
        (lambda p: p | {"admission_sha256": "b" * 64}, "admission_sha256"),
        (lambda p: {k: v for k, v in p.items() if k != "resource_budget"}, "BudgetSnapshot"),
        (lambda p: p | {"resource_budget": p["resource_budget"] | {"extra": 1}}, "Extra inputs"),
        (lambda p: p | {"resource_budget": p["resource_budget"] | {"ledger_path": "/elsewhere/resource-budget.json"}}, "different pilot ledger"),
        (lambda p: p | {"resource_budget": p["resource_budget"] | {"active_job": None}}, "budget-owned"),
        (lambda p: p | {"args": p["args"] | {"initialization": "matched_random_control"}}, "scripted arm"),
    ],
)
def test_initializer_metadata_mismatch_fails_closed(council_fixture, mutate, message):
    payload = mutate(_load(council_fixture.paths["scripted"]))
    with pytest.raises((ValueError, TypeError), match=message):
        validate_council_initial_policy(
            council_fixture.pilot, payload,
            initialization_path=council_fixture.paths["scripted"],
            args=_args(council_fixture, "scripted"), builder=council_fixture.builder,
        )


def test_arm_swap_unpublished_file_and_tampered_weights_are_rejected(council_fixture, tmp_path):
    fixture = council_fixture
    with pytest.raises(ValueError, match="scratch arm"):
        validate_council_initial_policy(
            fixture.pilot, _load(fixture.paths["scripted"]),
            initialization_path=fixture.paths["scripted"],
            args=_args(fixture, "scratch"), builder=fixture.builder,
        )
    copy = tmp_path / "copy.pt"
    payload = _load(fixture.paths["scripted"])
    torch.save(payload | {"metrics": {"changed": 1.0}}, copy)
    with pytest.raises(ValueError, match="published initial opponent"):
        validate_council_initial_policy(
            fixture.pilot, _load(copy), initialization_path=copy,
            args=_args(fixture, "scripted"), builder=fixture.builder,
        )
    _, _, record = _initialize_like_trainer(fixture, "scripted", 2901)
    model = ClasherPolicy(PolicyConfig.from_dict(payload["model_config"]), fixture.builder.card_stat_features)
    model.load_state_dict(payload["model_state_dict"], strict=True)
    with torch.no_grad():
        next(model.parameters()).view(-1)[0] += 1.0
    with pytest.raises(ValueError, match="digest"):
        require_initialized_weights(model, record)
    model.load_state_dict(payload["model_state_dict"], strict=True)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    for parameter in model.parameters():
        parameter.grad = torch.zeros_like(parameter)
    optimizer.step()  # zero gradients still create AdamW moment state
    model.load_state_dict(payload["model_state_dict"], strict=True)  # weights match again
    with pytest.raises(RuntimeError, match="fresh optimizer"):
        require_initialized_weights(model, record, optimizer)


def _gate_args(tmp_path, **overrides):
    checkpoint = tmp_path / "gate.pt"
    torch.save({"format_version": 2}, checkpoint)
    values = {
        "initialize_policy_from": str(checkpoint), "simulation_backend": "python",
        "council_config": None, "public_contract_version": 4,
        "resume_latest": False, "resume_from": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


@pytest.mark.parametrize(
    "overrides",
    [
        {},  # python backend without the council config
        {"council_config": Path("configs/council-pilot-local.toml"), "public_contract_version": 3},
    ],
)
def test_python_backend_initialization_stays_gated_off_the_council_path(tmp_path, overrides):
    with pytest.raises(ValueError, match="gated"):
        _load_initial_policy_state(_gate_args(tmp_path, **overrides), torch.device("cpu"))


def test_council_initialization_never_combines_with_resume(tmp_path):
    args = _gate_args(
        tmp_path, council_config=Path("configs/council-pilot-local.toml"),
        resume_from="x.pt",
    )
    with pytest.raises(ValueError, match="resume"):
        _load_initial_policy_state(args, torch.device("cpu"))
