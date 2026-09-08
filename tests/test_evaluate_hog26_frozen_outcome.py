import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from clasher.rl.direct_simple_behavior import DirectSimpleBehaviorCorpus
from scripts.evaluate_hog26_frozen_outcome import evaluate_frozen_predictions


class SyntheticHead(torch.nn.Module):
    state_size = 18

    def __init__(self):
        super().__init__()
        self.register_buffer("marker", torch.zeros(()))
        self.eval()

    def forward(self, features):
        labels = features[:, 1].long()
        p = torch.full((len(features), 3), 0.01, device=features.device)
        p[torch.arange(len(features)), labels + 1] = 0.98
        return SimpleNamespace(outcome_logits=p.log(), terminal_tower_margin=labels * 0.2)


def fixture():
    protocol = json.loads((Path(__file__).parents[1] / "reports" /
        "hog26_procedural_outcome_protocol_reassessed_20260908.json").read_text())
    protocol["gates"]["cluster_bootstrap_replicates"] = 100
    loaded = []
    for role, stage in protocol["final_holdout"].items():
        control = role == "controlled_draw"
        styles = ["control"] if control else stage["opponents"]
        records = [(style, cluster, seat) for style in range(len(styles))
                   for cluster in range(8) for seat in (0, 1)]
        n = len(records)
        if control:
            stage["actor_views"] = n
        else:
            stage["expected_games"] = n
        labels = np.array([0 if control else (1 if cluster % 2 else -1)
                           for _, cluster, _ in records], dtype=np.int64)
        public = np.zeros((n * 3, 18), dtype=np.float32)
        public[:, 0] = np.tile([0.15, 0.5, 0.85], n)
        public[:, 1] = np.repeat(labels, 3)
        margins = labels.astype(np.float32) * 0.2
        corpus = DirectSimpleBehaviorCorpus(
            arrays={
                "global_features": public,
                "final_outcomes": np.repeat(labels, 3),
                "terminal_tower_margins": np.repeat(margins, 3),
                "next_global_features": public.copy(),
                "terminal_winners": np.full(n * 3, -1),
            },
            episode_offsets=np.arange(0, n * 3 + 1, 3),
            episode_stream_rows=np.arange(n),
            episode_ordinals=np.array([cluster for _, cluster, _ in records]),
            initial_hidden=np.zeros((n, 1)), initial_cell=np.zeros((n, 1)),
            episode_arrays={
                "episode_final_outcomes": labels,
                "episode_terminal_tower_margins": margins,
                "episode_learner_players": np.array([seat for _, _, seat in records]),
                "episode_opponent_indices": np.array([style for style, _, _ in records]),
                "episode_opponent_deck_indices": np.zeros(n, dtype=np.int64),
            },
        )
        metadata = {
            "schema": "clasher.hog26.complete-outcome-corpus.v1",
            "label_authority": "undiscounted-terminal-winner-and-post-action-public-tower-fractions-v1",
            "actor_input_excludes_outcome_labels": True,
            "seed": stage["seed"], "opponents": styles,
            "opponent_decks": [stage["deck"] if role == "reserved_original" else role],
            "outcome_source": "controlled-symmetric-draws" if control else "natural-strategy-games",
        }
        loaded.append((metadata, corpus))
    features = torch.tensor(np.concatenate([c.arrays["global_features"] for _, c in loaded]))
    return protocol, loaded, features


def evaluate(protocol, loaded, features, head=None):
    return evaluate_frozen_predictions(
        head or SyntheticHead(), features, loaded, torch.tensor([0.45, 0.1, 0.45]),
        protocol, seed=23, device="cpu",
    )


def test_full_metric_path_passes_exact_synthetic_forecasts_without_mutation():
    protocol, loaded, features = fixture()
    result = evaluate(protocol, loaded, features)
    assert result["passed"]
    assert result["outcome_state_sha256_before"] == result["outcome_state_sha256_after"]
    assert result["counterfactual_ranking_pending"]
    assert not result["policy_updates_allowed"]


def test_bad_control_margins_do_not_change_natural_acceptance():
    protocol, loaded, features = fixture()
    control = next(c for m, c in loaded if m["outcome_source"] == "controlled-symmetric-draws")
    control.arrays["terminal_tower_margins"][:] = 1.0
    control.episode_arrays["episode_terminal_tower_margins"][:] = 1.0
    result = evaluate(protocol, loaded, features)
    assert result["passed"]
    assert result["breakdowns"]["phase_balanced_by_source"]["controlled-symmetric-draws"]["tower_margin_mae"] == 1.0


def test_reserved_failure_cannot_hide_in_generated_games():
    protocol, loaded, features = fixture()
    offset = 0
    for metadata, corpus in loaded:
        if metadata["seed"] == protocol["final_holdout"]["reserved_original"]["seed"]:
            # Change predictions while keeping feature/corpus alignment explicit.
            features[offset:offset + corpus.row_count, 1] *= -1
            corpus.arrays["global_features"][:, 1] *= -1
        offset += corpus.row_count
    result = evaluate(protocol, loaded, features)
    assert result["public_slices"]["groups"]["generated"]["passed"]
    assert not result["public_slices"]["groups"]["reserved_original"]["passed"]
    assert not result["passed"]


def test_final_stage_omission_rejected():
    protocol, loaded, features = fixture()
    with pytest.raises(ValueError, match="every declared final corpus"):
        evaluate(protocol, loaded[:-1], features)


def test_training_mode_rejected_before_evaluation():
    protocol, loaded, features = fixture()
    head = SyntheticHead().train()
    with pytest.raises(ValueError, match="eval-mode frozen"):
        evaluate(protocol, loaded, features, head)


def test_invalid_cohort_stops_before_final_corpus_loader(tmp_path, monkeypatch):
    from scripts import evaluate_hog26_frozen_outcome as evaluator

    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")

    def forbidden(*args, **kwargs):
        pytest.fail("final corpus was opened before validating the cohort")

    monkeypatch.setattr(evaluator, "load_direct_simple_behavior_corpus", forbidden)
    with pytest.raises(ValueError, match="manifest SHA-256 mismatch"):
        evaluator.evaluate_cohort(manifest, "0" * 64, tmp_path / "result.json",
                                  root=tmp_path, device="cpu")
    assert not (tmp_path / "result.json").exists()


def test_collection_report_must_bind_the_frozen_cohort(tmp_path, monkeypatch):
    from scripts import evaluate_hog26_frozen_outcome as evaluator

    protocol, _, _ = fixture()
    stage = next(iter(protocol["final_holdout"].values()))
    report_path = tmp_path / stage["output_report"]
    report_path.parent.mkdir(parents=True)
    report_path.write_text(json.dumps({"collection_authority": {
        "frozen_cohort_sha256": "wrong", "protocol_sha256": "b" * 64,
    }}))
    count = stage.get("expected_games", stage.get("actor_views"))
    monkeypatch.setattr(evaluator, "require_current_audit", lambda *args:
                        {"seed": stage["seed"], "episodes": count, "sha256": "a" * 64})
    with pytest.raises(ValueError, match="not bound to the frozen cohort"):
        evaluator.preflight_final_corpora(protocol, {"protocol_sha256": "b" * 64},
                                         "c" * 64, root=tmp_path)


def test_reserved_metadata_cannot_substitute_another_deck(tmp_path):
    from scripts.evaluate_hog26_frozen_outcome import validate_final_metadata

    protocol, loaded, _ = fixture()
    stage = protocol["final_holdout"]["reserved_original"]
    metadata = next(m for m, _ in loaded if m["seed"] == stage["seed"])
    metadata.update(checkpoint_sha256=protocol["base_policy"]["sha256"],
                    supported_decks_sha256=protocol["original_decks"]["sha256"])
    validate_final_metadata(protocol, "reserved_original", metadata, root=tmp_path)
    metadata["opponent_decks"] = ["wrong-deck"]
    with pytest.raises(ValueError, match="reserved final corpus differs"):
        validate_final_metadata(protocol, "reserved_original", metadata, root=tmp_path)


def test_cohort_orchestration_evaluates_all_seeds_and_requires_every_pass(
    tmp_path, monkeypatch,
):
    from scripts import evaluate_hog26_frozen_outcome as evaluator

    protocol, loaded, _ = fixture()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}")
    manifest_sha = evaluator.file_sha256(manifest_path)
    manifest = {"protocol_sha256": "b" * 64}
    records = []
    by_path = {}
    for i, pair in enumerate(loaded):
        path = tmp_path / f"source-{i}"
        path.write_text(str(i))
        role = next(role for role, stage in protocol["final_holdout"].items()
                    if stage["seed"] == pair[0]["seed"])
        records.append({"path": str(path), "role": role, "sha256": evaluator.file_sha256(path)})
        by_path[path] = pair
    candidates = []
    for seed in (1278801, 1278802, 1278803):
        head = SyntheticHead()
        candidates.append(({"seed": seed}, head, {
            "sequence_steps": 128, "actor_feature_contract": "public-globals",
            "train_class_prior": [0.45, 0.1, 0.45],
        }))
    monkeypatch.setattr(evaluator, "load_frozen_cohort", lambda *a, **k: (manifest, protocol, candidates))
    monkeypatch.setattr(evaluator, "preflight_final_corpora", lambda *a, **k: records)
    monkeypatch.setattr(evaluator, "load_direct_simple_behavior_corpus", lambda p: by_path[p])
    monkeypatch.setattr(evaluator, "validate_final_metadata", lambda *a, **k: None)
    monkeypatch.setattr(evaluator, "load_model", lambda *a: ({}, SyntheticHead()))
    monkeypatch.setattr(evaluator, "extract_actor_features", lambda model, corpus, **k:
                        torch.tensor(corpus.arrays["global_features"]))
    calls = []
    def metric_result(head, features, sources, prior, protocol, *, seed, device):
        calls.append(seed)
        return {"passed": seed != 1278802 + 40_000}
    monkeypatch.setattr(evaluator, "evaluate_frozen_predictions", metric_result)
    def forbidden_optimizer(*args, **kwargs):
        pytest.fail("final evaluator instantiated an optimizer")
    monkeypatch.setattr(torch.optim, "AdamW", forbidden_optimizer)
    result = evaluator.evaluate_cohort(manifest_path, manifest_sha, tmp_path / "result.json",
                                      root=tmp_path, device="cpu")
    assert calls == [seed + 40_000 for seed in (1278801, 1278802, 1278803)]
    assert not result["public_state_gates_passed"]
    assert len(result["candidates"]) == 3
    assert not result["policy_updates_allowed"]
