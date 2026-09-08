import json
from pathlib import Path

import pytest

from scripts import collect_hog26_frozen_final as collector
from scripts.freeze_hog26_outcome_cohort import require_unopened_final_paths


@pytest.fixture
def protocol():
    return json.loads((Path(__file__).parents[1] / "reports" /
        "hog26_procedural_outcome_protocol_reassessed_20260908.json").read_text())


def test_final_arguments_preserve_declared_counts_and_authorities(protocol, tmp_path):
    generated = collector.final_collection_args(protocol, "generated", root=tmp_path, device="cpu")
    assert generated.episodes_per_seat == 16
    assert generated.opponent_family_id == tuple(protocol["final_holdout"]["generated"]["family_ids"])
    assert generated.opponent_deck_split == "holdout"
    reserved = collector.final_collection_args(protocol, "reserved_original", root=tmp_path, device="cpu")
    assert reserved.opponent_decks == "RHogs AQ 2.9 Cycle"
    assert reserved.opponent_deck_split == ""
    assert reserved.supported_decks_path == tmp_path / protocol["original_decks"]["path"]
    draw = collector.final_collection_args(protocol, "controlled_draw", root=tmp_path, device="cpu")
    assert draw.battles * draw.episodes_per_battle == 8


def test_invalid_manifest_prevents_any_collection(tmp_path, monkeypatch):
    path = tmp_path / "manifest.json"
    path.write_text("{}")
    def forbidden(*args, **kwargs):
        pytest.fail("collector ran before cohort validation")
    monkeypatch.setattr(collector, "collect_natural", forbidden)
    with pytest.raises(ValueError, match="manifest SHA-256 mismatch"):
        collector.collect_final_stage(path, "0" * 64, "generated", root=tmp_path, device="cpu")


def test_failed_collection_leaves_receipt_and_cannot_be_retried_or_refrozen(
    protocol, tmp_path, monkeypatch,
):
    manifest = {"protocol_sha256": "b" * 64}
    monkeypatch.setattr(collector, "load_frozen_cohort", lambda *a, **k: (manifest, protocol, []))
    def fail(args):
        raise RuntimeError("simulated collector failure")
    monkeypatch.setattr(collector, "collect_natural", fail)
    with pytest.raises(RuntimeError, match="simulated collector failure"):
        collector.collect_final_stage(tmp_path / "manifest", "a" * 64, "generated", root=tmp_path, device="cpu")
    with pytest.raises(ValueError, match="already started"):
        collector.collect_final_stage(tmp_path / "manifest", "a" * 64, "generated", root=tmp_path, device="cpu")
    with pytest.raises(ValueError, match="already exist"):
        require_unopened_final_paths(protocol, tmp_path)


def test_collection_publishes_authority_only_after_audit(protocol, tmp_path, monkeypatch):
    manifest_path = tmp_path / "manifest.json"
    protocol_path = tmp_path / "protocol.json"
    manifest_path.write_text("{}")
    protocol_path.write_text(json.dumps(protocol))
    manifest_sha = collector.file_sha256(manifest_path)
    manifest = {"protocol": str(protocol_path), "protocol_sha256": collector.file_sha256(protocol_path)}
    monkeypatch.setattr(collector, "load_frozen_cohort", lambda *a, **k: (manifest, protocol, []))
    stage = protocol["final_holdout"]["reserved_original"]
    def collect(args):
        args.output.parent.mkdir(parents=True)
        args.output.write_text("synthetic test bytes")
        report = {
            "seed": stage["seed"], "checkpoint_sha256": protocol["base_policy"]["sha256"],
            "opponents": stage["opponents"], "opponent_decks": [stage["deck"]],
            "supported_decks_sha256": protocol["original_decks"]["sha256"],
        }
        args.report.write_text(json.dumps(report))
        return report
    def audit(paths, **kwargs):
        report = json.loads((tmp_path / stage["output_report"]).read_text())
        assert "collection_authority" not in report
        return {"status": "passed", "episodes": stage["expected_games"]}
    monkeypatch.setattr(collector, "collect_natural", collect)
    monkeypatch.setattr(collector, "audit", audit)
    result = collector.collect_final_stage(manifest_path, manifest_sha, "reserved_original", root=tmp_path, device="cpu")
    assert result["collection_authority"]["frozen_cohort_sha256"] == manifest_sha
    assert (tmp_path / stage["audit_report"]).exists()
