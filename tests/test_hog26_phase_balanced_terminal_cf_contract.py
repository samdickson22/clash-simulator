from __future__ import annotations

import hashlib
import json
from pathlib import Path

from clasher.rl.counterfactual_schedule import phase_balanced_query_ticks

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "reports/hog26_phase_balanced_terminal_cf_contract_v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _deck_signatures(path: Path) -> set[tuple[str, ...]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {tuple(sorted(row["cards"])) for row in payload["decks"]}


def test_phase_balanced_contract_pins_inputs_schedule_and_disjoint_decks() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    assert contract["status"] == "ready_after_weighted_overtime_rescreen"
    assert contract["launch_condition"] == {
        "runtime_identity_audit_sha256": "59395974c1ca5f5d8e06f108f50a99f4f8749dfc4a21bbb6ce88befd89bd7f0f",
        "runtime_identity_unknown_visible": 0,
        "chain_lightning_targeted_audit_sha256": "52e7a0d06ea5ee1e93a5526d14f2e1aee379d45582175faf93a0ea67a3fb6ce2",
        "chain_lightning_targeted_x86_audit_sha256": "0e486b8b2a2b55808c3baa53f04af74a4ebcffa3234fe8dcf5d49c0d00d6bc8c",
        "chain_lightning_targeted_unknown_visible": 0,
        "chain_lightning_targeted_visible": 5814,
        "tick3600_overtime_canary_npz_sha256": "21f9fdb40340e760f7060f13d13c4a578cd5e002bef3ed51741d6cf9a41d80a1",
        "tick3600_overtime_canary_report_sha256": "53c221591a1fc58f737491f506c163d347a240a53fbd0c3290aecd7c31ecbb65",
        "tick3600_overtime_canary_root_tick": 3608,
        "royal_delivery_payload_audit_sha256": "d141630a33607a236e000f9a14ea7bdfff71d195414419f65eeb903c38532020",
        "skeleton_barrel_payload_audit_sha256": "36ea6a86d2ac03d50713b7225998829be5d8fadcce0d824b5c370d643c3fbcad",
        "payload_identity_targeted_unknown_visible": 0,
        "overtime_train_screen_manifest_sha256": "6ccbc32ab812d53e0e6788e7db3902ef62fa5a066e2a8a90bad696027a4b5191",
        "overtime_train_screen_selected_games": 69,
        "overtime_validation_screen_manifest_sha256": "c14638f575ebd1f213bf136d936c210b703db6d7c760361ae19df8bf0cd0194c",
        "overtime_validation_screen_selected_games": 27,
        "overtime_supplement_canary_npz_sha256": "0f2366203c26c821c45e99a7df765468db0f9a960e353e57ec9df438c5f9b5f5",
        "overtime_supplement_canary_report_sha256": "e1beefd5798e071123f118fffc6acb1e1304b66b108567b1223436e513367b73",
        "overtime_supplement_canary_path": "reports/hog26_phase_balanced_terminal_cf_v3_seed1175001/best_action_order_overtime_canary.npz",
        "overtime_supplement_canary_tick": 3600,
        "best_action_order_canary_npz_sha256": "06b2f828256f3d66607f2ecd22ae45d1c31c2e32353418ba9b92f5838b6c7a1e",
        "best_action_order_canary_report_sha256": "5acb9856323014c23a9468a01484c35d0990b6dee3a97ff7905c3c33c9e69546",
        "best_action_order_canary_path": "reports/hog26_phase_balanced_terminal_cf_v3_seed1175001/best_action_order_canary.npz",
        "best_action_order_canary_mismatches": 0,
        "sampling_weight_rejection_sha256": "5157ed3c2c2c017b04625df100dcc48f25c5a7c05e09fe7aafe059051e383fd7",
        "rejected_sampling_total_variation": 0.363,
        "weighted_asymmetric_sampling_focused_tests": 8,
        "weighted_sampling_canary_path": "reports/hog26_asymmetric_weighted_sampling_canary_seed1190001.json",
        "weighted_sampling_canary_sha256": "cb48713e4a210fecc269b18b08a21b421b0fff42f77ccccd3ad8e4e1ad98d7f9",
        "weighted_sampling_canary_games": 800,
        "weighted_sampling_canary_total_variation": 0.045,
        "v2_canary_npz_sha256": "9da106d63f057b426dcd6dc7922fdfc9cf954ecd90f52670990f812e620f4508",
        "v2_canary_report_sha256": "26d64c655481149b20063d255767d7a07e0a78804cb0993318138a587cc7bd70",
        "promotion_authorized": False,
    }
    authorities = [
        contract["policy"],
        contract["deck_authority"]["runtime_decks"],
        contract["deck_authority"]["learner"],
        contract["deck_authority"]["train_opponents"],
        contract["deck_authority"]["validation_opponents"],
        contract["collection"]["schedule_source"],
        contract["required_state_contract"]["snapshot_source"],
        *contract["pipeline_sources"].values(),
    ]
    for authority in authorities:
        assert _sha256(ROOT / authority["path"]) == authority["sha256"]
    launch = contract["launch_condition"]
    for prefix in ("best_action_order_canary", "overtime_supplement_canary"):
        canary = ROOT / launch[f"{prefix}_path"]
        assert _sha256(canary) == launch[f"{prefix}_npz_sha256"]
        assert _sha256(canary.with_suffix(".json")) == launch[
            f"{prefix}_report_sha256"
        ]
    weighted_canary = ROOT / launch["weighted_sampling_canary_path"]
    assert _sha256(weighted_canary) == launch["weighted_sampling_canary_sha256"]
    train = ROOT / contract["deck_authority"]["train_opponents"]["path"]
    validation = ROOT / contract["deck_authority"]["validation_opponents"][
        "path"
    ]
    assert not _deck_signatures(train) & _deck_signatures(validation)
    collection = contract["collection"]
    expected_targets = phase_balanced_query_ticks(
        minimum_tick=256,
        max_ticks=collection["max_ticks"],
        states_per_game=collection["states_per_game"],
        decision_interval=collection["decision_interval_ticks"],
        phase_boundaries=(collection["overtime_start_tick"],),
    )
    assert tuple(collection["target_ticks"]) == expected_targets


def test_phase_balanced_contract_requires_complete_time_and_memory_scope() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    minimum = contract["minimum_roots"]

    assert minimum["train_total"] >= sum(minimum["train_by_phase"].values())
    assert minimum["validation_total"] >= sum(
        minimum["validation_by_phase"].values()
    )
    assert minimum["train_by_phase"]["overtime_ge_3600"] > 0
    assert minimum["validation_by_phase"]["overtime_ge_3600"] > 0
    state = contract["required_state_contract"]
    assert state["name"] == "public-actor-v2-action-time-recurrence"
    assert set(state["additional_arrays"]) == {
        "structured_recurrent_cell",
        "structured_previous_play_hazard",
    }
    assert state["cell_semantics"]["0"] == "model_owned_decision_clock"
    assert "opponent_elixir" in state["cell_semantics"]["1"]
    assert "leaky" in state["cell_semantics"]["2:64"]
    assert "exact_opponent_hand" in state["forbidden"]
    assert contract["decision"]["required_independent_model_seeds"] == 3
    assert contract["decision"]["single_seed_promotion_authorized"] is False
