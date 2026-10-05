"""Real optimizer/checkpoint regression for structured warm-start budget metadata.

Synthetic two-decision contract fixtures only: the simulator step is replaced, the
teacher always waits, and every artifact lives under pytest's tmp directory. This
checks software plumbing, not gameplay fitting or playing strength.
"""

import json
from dataclasses import replace

import numpy as np
import pytest
import torch

from clasher.rl.council_budget import BudgetSnapshot, budget_snapshot
from clasher.rl.council_warmstart import _merge_complete_games
from clasher.rl.deck_curriculum import pilot_curriculum
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.imitation import _sequence_batch_inputs, fit_imitation_corpus, load_corpus
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl.scripted_demonstrations import collect_public_script_game
from clasher.rl.selfplay_env import SelfPlayBattleEnv, StepInfo
from clasher.rl.structured_obs import StructuredObservationBuilder

SHA_A = "a" * 64
SHA_B = "b" * 64


def _synthetic_corpus(tmp_path, monkeypatch):
    from clasher.rl.public_scripted_opponent import PublicScriptedOpponent

    pool = pilot_curriculum()
    decks_path = tmp_path / "pilot.json"
    decks_path.write_text(json.dumps({"decks": sum(pool.values(), [])}))
    builder = StructuredObservationBuilder(
        decks_path=decks_path, max_entities=16, card_semantics_version=4,
        canonical_perspective=True, canonical_lane_globals=True,
        public_entity_levels=True, public_hand_levels=True,
        public_history_slots=4, public_seen_card_slots=8,
    )
    monkeypatch.setattr(PublicScriptedOpponent, "select_action", lambda self, packet: 2304)
    paths = []
    for split in (0, 1):
        env = SelfPlayBattleEnv(
            decks_path=decks_path, decision_interval_ticks=5, seed=3 + split,
            canonical_lane_globals=True, public_contract_version=4,
        )
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
    config = PolicyConfig(
        num_tokens=builder.spec.num_tokens, max_entities=16, card_semantics_version=4,
        public_contract_version=4, public_token_names=builder.token_names,
        public_observation_confidence=True, canonical_lane_globals=True,
        public_history_slots=4, public_seen_card_slots=8, d_model=32, num_heads=4,
        actor_layers=1, critic_layers=1, memory_size=32,
    )
    return corpus, decks_path, config, builder


def _active_budget_snapshot(tmp_path):
    """The warm start runs as the ledger's active child, so the snapshot is nested."""
    ledger = tmp_path / "resource-budget.json"
    ledger.write_text(json.dumps({
        "schema": "clasher.local-pilot-budget.v1",
        "config_sha256": SHA_A,
        "cpu_core_hour_ceiling": 4608.0,
        "accelerator_hour_ceiling": 72.0,
        "cpu_core_hours_used": 1.25,
        "accelerator_hours_used": 0.0,
        "active": {
            "argv": ["python", "-B", "scripts/run_council_warmstart.py"],
            "started_at": 1.0,
            "cpu_cores": 2,
            "accelerator": False,
            "pid": 4242,
        },
        "jobs": [],
    }))
    snapshot = budget_snapshot(ledger)
    assert isinstance(snapshot["active_job"], dict)
    BudgetSnapshot.model_validate(snapshot)
    return snapshot


def _fit(corpus, decks_path, config, tmp_path, metadata, name="fit"):
    return fit_imitation_corpus(
        corpus_path=corpus, output_checkpoint=tmp_path / f"{name}.pt",
        control_checkpoint=tmp_path / f"{name}-control.pt", decks_path=decks_path,
        seed=2901, epochs=2, batch_size=4, learning_rate=1e-2,
        validation_fraction=0.5, device=torch.device("cpu"), d_model=32,
        num_heads=4, actor_layers=1, critic_layers=1, memory_size=32,
        model_config_override=config, checkpoint_metadata=metadata,
        card_semantics_version=4, sequence_length=4, train_on_forced_actions=True,
        trim_entity_padding=True, canonical_lane_globals=True,
        imitation_objective="exact",
    )


def test_structured_budget_metadata_survives_real_optimizer_and_checkpoint_reload(
    tmp_path, monkeypatch
):
    corpus, decks_path, config, builder = _synthetic_corpus(tmp_path, monkeypatch)
    snapshot = _active_budget_snapshot(tmp_path)
    metadata = {
        "gamedata_sha256": SHA_A,
        "strategy_sha256": SHA_B,
        "warmstart_plan_sha256": SHA_A,
        "resource_budget": snapshot,
    }
    manifest = _fit(corpus, decks_path, config, tmp_path, metadata)
    assert manifest["recurrence"] == "current-weight-full-episode-prefix"
    assert manifest["train_samples"] > 0 and manifest["validation_samples"] > 0

    trained = torch.load(tmp_path / "fit.pt", map_location="cpu", weights_only=False)
    control = torch.load(tmp_path / "fit-control.pt", map_location="cpu", weights_only=False)
    for payload in (trained, control):
        # Exact structured round trip, still a valid typed budget after reload.
        assert payload["resource_budget"] == snapshot
        restored = BudgetSnapshot.model_validate(payload["resource_budget"])
        assert restored.active_job is not None and restored.active_job.cpu_cores == 2
        for key in ("gamedata_sha256", "strategy_sha256", "warmstart_plan_sha256"):
            assert payload[key] == metadata[key]
        assert payload["args"]["seed"] == 2901
    assert trained["args"]["initialization"] == "public_script_imitation"

    # Real optimizer steps changed weights relative to the matched untrained control.
    changed = [
        name for name, tensor in trained["model_state_dict"].items()
        if tensor.is_floating_point()
        and not torch.equal(tensor, control["model_state_dict"][name])
    ]
    assert changed, "optimizer did not update any parameter"
    assert all(
        torch.isfinite(tensor).all()
        for tensor in trained["model_state_dict"].values()
        if tensor.is_floating_point()
    )

    # The production loader reconstructs the model with the saved weights.
    loaded = load_policy_checkpoint(tmp_path / "fit.pt", device=torch.device("cpu"), decks_path=decks_path)
    assert loaded.checkpoint["resource_budget"] == snapshot
    for name, tensor in loaded.model.state_dict().items():
        torch.testing.assert_close(tensor, trained["model_state_dict"][name])
    _, arrays = load_corpus(corpus)
    inputs = _sequence_batch_inputs(arrays, np.asarray([[0, 1, 2]]), torch.device("cpu"))
    fresh = ClasherPolicy(config, builder.card_stat_features).eval()
    fresh.load_state_dict(control["model_state_dict"])
    with torch.no_grad():
        after = loaded.model(inputs).joint_logits
        before = fresh(inputs).joint_logits
    assert torch.isfinite(after[torch.isfinite(before)]).all()
    assert not torch.equal(after, before)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda snap: snap | {"unexpected": 1}, "Extra inputs"),
        (lambda snap: snap | {"cpu_core_hours_used": -1.0}, "greater than or equal"),
        (lambda snap: snap | {"accounting": "host wide"}, "accounting"),
        (lambda snap: "c" * 64, "valid dictionary"),
    ],
)
def test_malformed_budget_metadata_is_rejected_before_any_checkpoint(
    tmp_path, monkeypatch, mutate, message
):
    corpus, decks_path, config, _ = _synthetic_corpus(tmp_path, monkeypatch)
    snapshot = _active_budget_snapshot(tmp_path)
    with pytest.raises(ValueError, match=message):
        _fit(corpus, decks_path, config, tmp_path,
             {"gamedata_sha256": SHA_A, "resource_budget": mutate(snapshot)})
    assert not (tmp_path / "fit.pt").exists()
    assert not (tmp_path / "fit-control.pt").exists()


@pytest.mark.parametrize(
    "metadata, message",
    [
        ({"gamedata_sha256": "not-a-digest"}, "SHA-256"),
        ({"gamedata_sha256": SHA_A.upper()}, "SHA-256"),
        ({"model_state_dict": SHA_A}, "unsupported"),
        ({"args": SHA_A}, "unsupported"),
    ],
)
def test_non_budget_provenance_stays_digest_only(tmp_path, metadata, message):
    # Validation precedes corpus loading, so no dataset is needed here.
    with pytest.raises(ValueError, match=message):
        fit_imitation_corpus(
            corpus_path=tmp_path / "missing.npz", output_checkpoint=tmp_path / "x.pt",
            control_checkpoint=tmp_path / "c.pt", decks_path=tmp_path / "d.json",
            seed=1, epochs=1, batch_size=1, learning_rate=1e-3,
            validation_fraction=0.5, device=torch.device("cpu"), d_model=32,
            num_heads=4, actor_layers=1, critic_layers=1, memory_size=32,
            checkpoint_metadata=metadata,
        )
