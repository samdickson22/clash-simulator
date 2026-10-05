from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_location_stage_does_not_overwrite_integrity_verified_combined_corpus() -> None:
    script = (REPO_ROOT / "scripts/run_tv_royale_2000_location_imitation.sh").read_text(
        encoding="utf-8"
    )

    assert "combine_tv_royale_location_sidecars.py" not in script
    assert "tv_royale_raw_cascade_2000_locations.npz" not in script
    assert "split_tv_royale_location_sidecars.py" in script


def test_postprocess_verifies_publication_before_location_stage() -> None:
    script = (REPO_ROOT / "scripts/run_tv_royale_2000_postprocess.sh").read_text(
        encoding="utf-8"
    )

    integrity = script.index("scripts/verify_tv_royale_run_integrity.py")
    human_meta = script.index("scripts/verify_tv_royale_human_meta_gate.py")
    type_readiness = script.index("scripts/verify_tv_royale_type_split.py")
    location = script.index("scripts/run_tv_royale_2000_location_imitation.sh")
    assert integrity < human_meta < type_readiness < location


def test_rl_pilot_rejects_stale_bounded_checkpoints_before_training() -> None:
    script = (
        REPO_ROOT / "scripts/run_tv_royale_2000_diversified_rl_pilot.sh"
    ).read_text(encoding="utf-8")

    stale_guard = script.index("refusing stale bounded-phase checkpoint")
    training = script.index("scripts/run_clasher.py train")
    assert stale_guard < training


def test_rl_pilot_uses_fail_closed_finalizer_for_promotion() -> None:
    script = (
        REPO_ROOT / "scripts/run_tv_royale_2000_diversified_rl_pilot.sh"
    ).read_text(encoding="utf-8")

    assert "scripts/finalize_tv_royale_rl_pilot.py" in script
    assert "promotion_path.write_text" not in script


def test_public_v2_finalizer_verifies_before_splitting_and_handoff() -> None:
    script = (REPO_ROOT / "scripts/run_tv_royale_public_v2_1000_finalize.sh").read_text(
        encoding="utf-8"
    )

    integrity = script.index("scripts/verify_tv_royale_run_integrity.py")
    quality = script.index("scripts/verify_tv_royale_public_state_quality.py")
    visual = script.index("scripts/build_tv_royale_public_contact_sheets.py")
    split = script.index("scripts/split_tv_royale_raw_cascade.py")
    public_split = script.index("scripts/split_tv_royale_public_sidecars.py")
    handoff = script.index("pretraining_inputs_ready_v1")
    assert integrity < quality < visual < split < public_split < handoff
    assert "--require-public-state-v2" in script
    assert "--minimum-arena-entity-hp-coverage 0.45" in script
    assert ': > "$success_marker"' not in script
    assert 'if [[ -e "$success_marker" ]]' in script
    assert '> "$success_marker_tmp"' in script
    assert 'mv -- "$success_marker_tmp" "$success_marker"' in script


def test_final_mechanics_gate_selects_before_heldout_evaluation() -> None:
    script = (
        REPO_ROOT / "scripts/run_tv_royale_public_v2_final_mechanics_gate.sh"
    ).read_text(encoding="utf-8")

    visual_audit = script.index("unsupported final visual-audit schema")
    finetune = script.index("scripts/finetune_mechanics_slot_probe.py")
    selector = script.index("scripts/select_mechanics_slot_candidate.py")
    archetype = script.index("--human-archetype-corpus")
    chronology = script.index("--human-chronology-corpus")
    materialized = script.index("scripts/evaluate_mechanics_slot_policy_candidate.py")
    handoff = script.index("development_candidate_ready_v1")
    assert visual_audit < finetune < selector < materialized < archetype < handoff
    assert visual_audit < finetune < selector < materialized < chronology < handoff
    assert script.count("--finetune-report") == 3
    assert "external_replay_disjoint" in (
        REPO_ROOT / "scripts/select_mechanics_slot_candidate.py"
    ).read_text(encoding="utf-8")


def test_mechanics_gameplay_gate_requires_offline_handoff_and_finalizer() -> None:
    script = (
        REPO_ROOT / "scripts/run_mechanics_slot_candidate_gameplay_gate.sh"
    ).read_text(encoding="utf-8")

    marker_guard = script.index('[[ ! -f "$offline_marker" ]]')
    direct = script.index('"$root/direct_${split}12.metrics.json"')
    paired = script.index("run_paired_workload random12")
    hog = script.index('"$root/${role}_hog12.decisions.json"')
    finalizer = script.index("scripts/finalize_mechanics_slot_gameplay_gate.py")
    handoff = script.index("mechanics_rl_initializer_ready_v1")
    assert marker_guard < direct < paired < hog < finalizer < handoff
    assert (
        "--validation-decks datasets/deck_curriculum_v2_seed1040001/validation.json"
        in script
    )
    assert '--heldout-decks "$heldout_decks"' in script
    assert "--hog-decks training_decks/katacr_hog26_only.json" in script
    assert 'if [[ -e "$root" ]]' in script
    assert 'mv -- "$ready_marker_tmp" "$ready_marker"' in script


def test_mechanics_pfsp_pilot_is_gated_and_uses_strict_deck_pools() -> None:
    script = (
        REPO_ROOT / "scripts/run_mechanics_slot_diversified_pfsp_pilot.sh"
    ).read_text(encoding="utf-8")

    marker = script.index('[[ ! -f "$initializer_marker" ]]')
    preflight = script.index("pfsp_pilot_preflight_passed")
    parent_benchmark = script.index('"$root/parent_strategy.json"')
    training = script.index("scripts/run_clasher.py train")
    stability = script.index("scripts/verify_rl_training_stability.py")
    direct = script.index('"$root/direct_${split}12.metrics.json"')
    win_condition_matrix = script.index("run_win_condition_utilization parent")
    human = script.index("scripts/evaluate_recurrent_corpus.py")
    finalizer = script.index("scripts/finalize_mechanics_slot_pfsp_pilot.py")
    handoff = script.index("mechanics_pfsp_development_candidate_ready_v1")
    assert (
        marker
        < preflight
        < parent_benchmark
        < training
        < stability
        < direct
        < win_condition_matrix
        < human
        < finalizer
        < handoff
    )
    assert "train_strict_v2_holdouts_card_balanced.json" in script
    assert "pfsp_tuning_strict_v2_holdouts.json" in script
    assert "--pfsp-strategy-workers 8" in script
    assert "--trainable-prefix mechanics_slot_choice_query." in script
    assert "--anchor-rehearsal-corpus" in script
    assert "verify_win_condition_manifest" in script
    assert '--win-condition-root "$win_condition_root"' in script
    assert '--win-condition-manifest "$win_condition_manifest"' in script
    assert 'if [[ -e "$root" || -e "$checkpoint_dir" ]]' in script
    assert 'mv -- "$marker_tmp" "$ready_marker"' in script


def test_mechanics_pfsp_runner_accepts_explicit_zero_initializer_inputs() -> None:
    script = (
        REPO_ROOT / "scripts/run_mechanics_slot_diversified_pfsp_pilot.sh"
    ).read_text(encoding="utf-8")

    assert "CLASHER_PFSP_INITIALIZER_ROOT" in script
    assert "CLASHER_PFSP_INITIALIZER_MARKER" in script
    assert "CLASHER_PFSP_PARENT" in script
    assert "CLASHER_PFSP_TAG" in script
    assert "CLASHER_PFSP_SPLIT_ROOT" in script
    assert '$(<"$initializer_marker") != "$initializer_marker_value"' in script
    assert "CLASHER_PFSP_START_UPDATE" in script
    assert "CLASHER_PFSP_END_UPDATE" in script
    assert '--start-update "$start_update"' in script
    assert '--end-update "$end_update"' in script
    assert "CLASHER_PFSP_TRAIN_ACTION_TYPE" in script
    assert '"${trainable_actor_args[@]}"' in script


def test_zero_initializer_runner_requires_equivalence_before_evaluation() -> None:
    script = (
        REPO_ROOT / "scripts/run_zero_mechanics_rl_initializer_gate.sh"
    ).read_text(encoding="utf-8")

    equivalence = script.index("exact_equivalence.json")
    evaluation = script.index("run_workload random12")
    finalizer = script.index("finalize_zero_mechanics_rl_initializer.py")
    handoff = script.index("zero_mechanics_rl_initializer_ready_v1")
    assert equivalence < evaluation < finalizer < handoff
    assert "CLASHER_ZERO_SOURCE_CHECKPOINT" in script
    assert "CLASHER_ZERO_CANDIDATE_CHECKPOINT" in script
    assert "CLASHER_ZERO_EQUIVALENCE_REPORT" in script
    assert "CLASHER_ZERO_INITIALIZER_ROOT" in script


def test_zero_pfsp_runner_requires_clean_holdout_and_final_visual_audit() -> None:
    script = (
        REPO_ROOT / "scripts/run_zero_mechanics_diversified_pfsp_pilot.sh"
    ).read_text(encoding="utf-8")

    initializer = script.index("zero_mechanics_rl_initializer_ready_v1")
    post260 = script.index("post260_evaluation_inputs_ready_v1")
    parent_selection = script.index("targeted_repair_parent_verified")
    visual = script.index("verify_tv_royale_final_visual_audit.py")
    launch = script.index(
        "exec zsh scripts/run_mechanics_slot_diversified_pfsp_pilot.sh"
    )
    assert initializer < post260 < parent_selection < visual < launch
    assert "--expected-games 1000" in script
    assert "final1000_visual_audit_verification.json" in script
    assert "CLASHER_PFSP_PARENT" in script
    assert "CLASHER_PFSP_SPLIT_ROOT" in script
    assert "CLASHER_PFSP_START_UPDATE=20" in script
    assert "CLASHER_PFSP_END_UPDATE=24" in script
    assert "CLASHER_PFSP_TRAIN_ACTION_TYPE=0" in script
    assert "compact_vs_accepted6m_v3.json" in script
    assert "repair_pilot_authorized" in script


def test_post260_split_reserves_architecture_development_prefix() -> None:
    script = (
        REPO_ROOT / "scripts/run_tv_royale_public_v2_post260_finalize.sh"
    ).read_text(encoding="utf-8")

    assert "--target-games 1000" in script
    assert "--reserve-first-completed 260" in script
    assert "verify_tv_royale_post260_split.py" in script
    assert "--reserved-games 260" in script
    assert "post260_evaluation_inputs_ready_v1" in script
