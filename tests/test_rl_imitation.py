import json
from pathlib import Path

import numpy as np
import torch

from clasher.rl import imitation as imitation_module
from clasher.rl.imitation import (
    collect_oracle_corpus,
    fit_imitation_corpus,
    load_corpus,
    split_indices,
)
from clasher.rl.oracle_corpus import manifest_path


def test_split_indices_is_reproducible_and_disjoint():
    episode_ids = np.asarray([0, 0, 1, 1, 2, 2], dtype=np.int64)
    train_a, validation_a = split_indices(episode_ids, validation_fraction=0.33, seed=7)
    train_b, validation_b = split_indices(episode_ids, validation_fraction=0.33, seed=7)

    assert np.array_equal(train_a, train_b)
    assert np.array_equal(validation_a, validation_b)
    assert not set(train_a).intersection(validation_a)
    assert set(episode_ids[train_a]).isdisjoint(set(episode_ids[validation_a]))


def test_fixed_corpus_builds_matched_v2_control_and_warm_start(tmp_path: Path):
    corpus = tmp_path / "oracle_corpus.npz"
    metadata = collect_oracle_corpus(
        output_path=corpus,
        decks_path=Path("decks.json").resolve(),
        decisions=2,
        seed=31,
        decision_interval=1,
        max_ticks=20,
        planner_depth=1,
        planner_simulations=1,
        planner_action_samples=4,
        max_entities=16,
        quiet_engine=True,
    )

    loaded_metadata, arrays = load_corpus(corpus)
    assert loaded_metadata == metadata
    assert loaded_metadata.reward_profile == "defense-v2"
    assert arrays["expert_actions"].shape == (4,)
    assert np.all(arrays["action_masks"][np.arange(4), arrays["expert_actions"]])

    imitation = tmp_path / "imitation.pt"
    control = tmp_path / "control.pt"
    manifest = fit_imitation_corpus(
        corpus_path=corpus,
        output_checkpoint=imitation,
        control_checkpoint=control,
        decks_path=Path("decks.json").resolve(),
        seed=41,
        epochs=1,
        batch_size=2,
        learning_rate=1e-4,
        validation_fraction=0.25,
        device=torch.device("cpu"),
        d_model=16,
        num_heads=2,
        actor_layers=1,
        critic_layers=1,
        memory_size=16,
    )

    imitation_payload = torch.load(imitation, weights_only=False)
    control_payload = torch.load(control, weights_only=False)
    assert imitation_payload["format_version"] == 2
    assert control_payload["format_version"] == 2
    assert imitation_payload["imitation"]["trained"] is True
    assert control_payload["imitation"]["trained"] is False
    assert "optimizer_state_dict" not in imitation_payload
    assert "optimizer_state_dict" not in control_payload
    assert manifest["train_samples"] + manifest["validation_samples"] == 4
    assert any(
        not torch.equal(
            imitation_payload["model_state_dict"][name],
            control_payload["model_state_dict"][name],
        )
        for name in imitation_payload["model_state_dict"]
    )


def test_parallel_corpus_collection_has_disjoint_episode_ids(tmp_path: Path):
    corpus = tmp_path / "parallel_oracle_corpus.npz"
    metadata = collect_oracle_corpus(
        output_path=corpus,
        decks_path=Path("decks.json").resolve(),
        decisions=2,
        seed=71,
        decision_interval=1,
        max_ticks=20,
        planner_depth=1,
        planner_simulations=1,
        planner_action_samples=4,
        max_entities=16,
        quiet_engine=True,
        workers=2,
    )

    loaded_metadata, arrays = load_corpus(corpus)
    assert loaded_metadata == metadata
    assert metadata.workers == 2
    assert arrays["episode_ids"].tolist() == [0, 0, 1, 1]


def test_completed_oracle_shard_resumes_without_recollection(
    tmp_path: Path,
    monkeypatch,
):
    output = tmp_path / "oracle.npz"
    kwargs = {
        "output_path": output,
        "decks_path": Path("decks.json").resolve(),
        "decisions": 1,
        "seed": 71,
        "decision_interval": 1,
        "max_ticks": 20,
        "planner_depth": 1,
        "planner_simulations": 1,
        "planner_action_samples": 4,
        "max_entities": 16,
        "quiet_engine": True,
        "workers": 1,
    }
    first = collect_oracle_corpus(**kwargs)
    output.unlink()

    def fail_recollection(_config):
        raise AssertionError("completed shard should be reused")

    monkeypatch.setattr(
        imitation_module,
        "_collect_oracle_shard",
        fail_recollection,
    )
    resumed = collect_oracle_corpus(**kwargs)
    loaded, arrays = load_corpus(output)

    assert first.samples == resumed.samples == loaded.samples == 2
    assert arrays["expert_actions"].shape == (2,)
    manifest = json.loads(manifest_path(output).read_text())
    assert manifest["complete"] is True
    assert manifest["completed_shards"] == [0]
