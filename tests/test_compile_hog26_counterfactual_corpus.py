from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from scripts.compile_hog26_counterfactual_corpus import _audit_probe, compile_corpus


def _write_probe(
    root: Path,
    *,
    stem: str,
    checkpoint_sha256: str,
    seed: int,
    parent_action: int,
    best_action: int,
    best_margin: float,
    all_terminal: bool = True,
    bootstrap_return: float = 0.0,
    best_outcome: int = 0,
) -> None:
    rows = [
        {
            "action": best_action,
            "discounted_return_mean": best_margin + bootstrap_return,
            "discounted_reward_return": best_margin,
            "discounted_bootstrap_return": bootstrap_return,
            "terminal": all_terminal,
            "terminal_outcome": best_outcome,
        },
        {
            "action": parent_action,
            "discounted_return_mean": 0.0,
            "discounted_reward_return": 0.0,
            "discounted_bootstrap_return": 0.0,
            "terminal": all_terminal,
            "terminal_outcome": 0,
        },
    ]
    if parent_action != 2304:
        rows.append(
            {
                "action": 2304,
                "discounted_return_mean": 0.0,
                "discounted_reward_return": 0.0,
                "discounted_bootstrap_return": 0.0,
                "terminal": all_terminal,
                "terminal_outcome": 0,
            }
        )
    payload = {
        "schema": "clasher.simple-counterfactual-teacher-probe.v4",
        "checkpoint_sha256": checkpoint_sha256,
        "candidate_selector": "hand-slot-spatial-stratified-v1",
        "return_estimator": "truncated-n-step-bootstrap-v1",
        "seed": seed,
        "warmup_steps": 1,
        "horizon_steps": 24,
        "realized_horizon_steps": 16,
        "stop_when_all_terminal": True,
        "label_authority": "terminal-outcome-then-discounted-reward-v1",
        "action_samples": len(rows),
        "random_candidate_fraction": 0.25,
        "opponent_strategy": "balanced",
        "parent_action": parent_action,
        "rows": rows,
    }
    json_path = root / f"{stem}.json"
    json_path.write_text(json.dumps(payload, sort_keys=True))
    action_masks = np.zeros((2, 2306), dtype=np.bool_)
    action_masks[:, [best_action, parent_action, 2304]] = True
    entity_mask = np.asarray([[True, False, True], [True, True, False]])
    expert_actions = np.asarray([12, best_action], dtype=np.int64)
    valid = np.asarray([False, True])
    np.savez_compressed(
        json_path.with_suffix(".npz"),
        entity_ids=np.asarray([[1, 0, 2], [3, 4, 0]], dtype=np.int64),
        entity_features=np.zeros((2, 3, 32), dtype=np.float32),
        entity_mask=entity_mask,
        hand_ids=np.ones((2, 5), dtype=np.int64),
        global_features=np.zeros((2, 18), dtype=np.float32),
        action_masks=action_masks,
        previous_actions=np.asarray([2304, 12], dtype=np.int64),
        previous_rewards=np.zeros(2, dtype=np.float64),
        episode_starts=np.asarray([True, False]),
        expert_actions=expert_actions,
        expert_action_supervision_valid=valid,
        expert_card_supervision_valid=valid,
        expert_tile_supervision_valid=valid,
        episode_ids=np.full(2, seed, dtype=np.int64),
        source_frames=np.arange(2, dtype=np.int64),
    )


def test_compiler_retains_all_behavior_but_only_accepted_roots(tmp_path: Path) -> None:
    checkpoint = tmp_path / "parent.pt"
    torch.save({"token_names": ["<padding>", "Knight"]}, checkpoint)
    checkpoint_sha256 = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    probes = tmp_path / "probes"
    probes.mkdir()
    _write_probe(
        probes,
        stem="accepted",
        checkpoint_sha256=checkpoint_sha256,
        seed=10,
        parent_action=2304,
        best_action=22,
        best_margin=0.03,
    )
    _write_probe(
        probes,
        stem="rejected",
        checkpoint_sha256=checkpoint_sha256,
        seed=11,
        parent_action=2304,
        best_action=23,
        best_margin=0.01,
    )
    output = tmp_path / "corpus"

    manifest = compile_corpus(
        probe_root=probes,
        output_root=output,
        checkpoint=checkpoint,
        minimum_margin=0.02,
        seed=99,
        workers=2,
        created_at="2026-08-30T00:00:00+00:00",
    )

    assert manifest["probes"] == 2
    assert manifest["accepted_probes"] == 1
    assert manifest["rows"] == 4
    assert manifest["preference_score"] == "terminal_outcome_then_discounted_reward"
    assert manifest["label_horizon_contract"] == "all-candidates-terminal"
    assert manifest["horizon_steps"] == [24]
    assert manifest["maximum_horizon_steps"] == 24
    with np.load(output / "corpus.npz", allow_pickle=False) as archive:
        assert archive["counterfactual_root_rows"].tolist() == [1]
        assert archive["root_base_actions"].tolist() == [2304]
        assert archive["root_candidate_outcomes"].tolist() == [[0, 0]]
        assert archive["expert_actions"].tolist() == [12, 2304, 12, 2304]
        assert archive["entity_mask"].tolist() == [
            [True, True, False],
            [True, True, False],
            [True, True, False],
            [True, True, False],
        ]


def test_compiler_rejects_any_nonterminal_candidate_label(tmp_path: Path) -> None:
    checkpoint = tmp_path / "parent.pt"
    torch.save({"token_names": ["<padding>", "Knight"]}, checkpoint)
    checkpoint_sha256 = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    probes = tmp_path / "probes"
    probes.mkdir()
    _write_probe(
        probes,
        stem="truncated",
        checkpoint_sha256=checkpoint_sha256,
        seed=10,
        parent_action=2304,
        best_action=22,
        best_margin=0.03,
        all_terminal=False,
    )

    try:
        compile_corpus(
            probe_root=probes,
            output_root=tmp_path / "corpus",
            checkpoint=checkpoint,
            minimum_margin=0.02,
            seed=99,
            workers=2,
            created_at="2026-08-30T00:00:00+00:00",
        )
    except ValueError as error:
        assert "nonterminal candidate labels" in str(error)
    else:
        raise AssertionError("nonterminal counterfactual labels were accepted")


def test_compiler_rejects_terminal_label_with_critic_bootstrap(tmp_path: Path) -> None:
    checkpoint = tmp_path / "parent.pt"
    torch.save({"token_names": ["<padding>", "Knight"]}, checkpoint)
    checkpoint_sha256 = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    probes = tmp_path / "probes"
    probes.mkdir()
    _write_probe(
        probes,
        stem="bootstrapped",
        checkpoint_sha256=checkpoint_sha256,
        seed=10,
        parent_action=2304,
        best_action=22,
        best_margin=0.03,
        bootstrap_return=0.01,
    )

    with pytest.raises(ValueError, match="critic bootstrap"):
        compile_corpus(
            probe_root=probes,
            output_root=tmp_path / "corpus",
            checkpoint=checkpoint,
            minimum_margin=0.02,
            seed=99,
            workers=2,
            created_at="2026-08-30T00:00:00+00:00",
        )


def test_compiler_prefers_winning_outcome_over_higher_dense_return(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "parent.pt"
    torch.save({"token_names": ["<padding>", "Knight"]}, checkpoint)
    checkpoint_sha256 = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    probes = tmp_path / "probes"
    probes.mkdir()
    _write_probe(
        probes,
        stem="winning",
        checkpoint_sha256=checkpoint_sha256,
        seed=10,
        parent_action=2304,
        best_action=22,
        best_margin=-0.5,
        best_outcome=1,
    )

    output = tmp_path / "corpus"
    manifest = compile_corpus(
        probe_root=probes,
        output_root=output,
        checkpoint=checkpoint,
        minimum_margin=0.02,
        seed=99,
        workers=2,
        created_at="2026-08-30T00:00:00+00:00",
    )

    assert manifest["accepted_probes"] == 1
    assert manifest["audits"][0]["best_action"] == 22
    assert manifest["audits"][0]["best_terminal_outcome"] == 1
    assert manifest["audits"][0]["timing_preference"] == "play"
    with np.load(output / "corpus.npz", allow_pickle=False) as archive:
        assert archive["root_candidate_outcomes"].tolist() == [[1, 0]]


def test_probe_audit_records_terminal_wait_preference(tmp_path: Path) -> None:
    checkpoint = tmp_path / "parent.pt"
    torch.save({"token_names": ["<padding>", "Knight"]}, checkpoint)
    checkpoint_sha256 = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    probes = tmp_path / "probes"
    probes.mkdir()
    _write_probe(
        probes,
        stem="wait",
        checkpoint_sha256=checkpoint_sha256,
        seed=10,
        parent_action=2304,
        best_action=22,
        best_margin=-0.5,
        best_outcome=-1,
    )

    audit, _ = _audit_probe(
        probes / "wait.json",
        checkpoint_sha256=checkpoint_sha256,
        minimum_margin=0.02,
    )

    assert audit["timing_preference"] == "wait"
    assert audit["timing_best_play_action"] == 22
    assert audit["timing_best_play_terminal_outcome"] == -1
