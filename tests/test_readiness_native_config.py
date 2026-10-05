"""Concrete native configs preserve the declared episode and exercised settings."""

import copy
import json

import pytest

from clasher.data import CardDataLoader
from clasher.paths import gamedata_path, project_root
from clasher.rl.readiness_execution import canonical_sha, file_sha
from clasher.rl.readiness_native_config import (
    ConfigManifest,
    config_for_request,
    load_verified_template,
    materialize_configs,
)
from clasher.rl.readiness_root_bank import generate_root_bank

CAPTURE = (
    project_root()
    / "reports/calibration_development_20260915/deck-mix-development/mix0-reversed"
)
PLAN_SHA = "4c47d7839a9e5dd9fe49312949b3276b5bd332dd139225285ea4fb56bc591259"


def template():
    return load_verified_template(CAPTURE, PLAN_SHA)


def test_actual_native_ids_match_both_ordered_decks_and_only_declared_fields_change():
    original = template()
    loader = CardDataLoader()
    old_loader = CardDataLoader(CAPTURE / "gamedata.json")
    bank = generate_root_bank(192801)
    for request in bank.requests:
        config = config_for_request(request, original, loader, old_loader)
        assert config["rndSeed"] == request.episode_seed
        for seat, deck in enumerate(request.decks):
            assert config["battle"][f"deck{seat}"]["sp"] == [
                {"d": loader.get_card(name)._raw_entry["id"]} for name in deck
            ]
            assert request.focal_card in request.decks[request.root_owner]
            assert (
                config["battle"][f"deck{seat}"]["sc"]
                == original["battle"][f"deck{seat}"]["sc"]
            )
        restored = copy.deepcopy(config)
        restored["rndSeed"] = original["rndSeed"]
        for seat in (0, 1):
            restored["battle"][f"deck{seat}"]["sp"] = original["battle"][f"deck{seat}"][
                "sp"
            ]
        assert restored == original
    assert original == template()


def test_materialized_manifest_binds_exact_files_and_identity(tmp_path):
    bank = generate_root_bank(192801)
    output = tmp_path / "configs"
    manifest = materialize_configs(
        bank,
        template_capture=CAPTURE,
        expected_template_plan_sha256=PLAN_SHA,
        gamedata=gamedata_path(),
        expected_gamedata_sha256=file_sha(gamedata_path()),
        output=output,
    )
    assert manifest.configured_count == 32 and manifest.failed_count == 0
    assert manifest.status == "uncaptured_unregistered"
    assert (
        ConfigManifest.model_validate_json((output / "manifest.json").read_text())
        == manifest
    )
    assert manifest.root_bank_sha256 == canonical_sha(bank.model_dump(mode="json"))
    for entry, request in zip(manifest.episodes, bank.requests):
        config = json.loads((output / entry.config_path).read_text())
        assert entry.root_request_sha256 == canonical_sha(
            request.model_dump(mode="json")
        )
        assert entry.config_file_sha256 == file_sha(output / entry.config_path)
        assert entry.config_sha256 == canonical_sha(config)
        assert entry.source_episode_id == request.source_episode_id
        assert entry.root_owner == request.root_owner
        assert entry.ordered_decks == request.decks
        assert entry.prefix_styles == request.prefix_styles
    with pytest.raises(FileExistsError):
        materialize_configs(
            bank,
            template_capture=CAPTURE,
            expected_template_plan_sha256=PLAN_SHA,
            gamedata=gamedata_path(),
            expected_gamedata_sha256=file_sha(gamedata_path()),
            output=output,
        )


def test_unsupported_card_retains_every_failed_request_without_replacement(
    tmp_path, monkeypatch
):
    original = CardDataLoader.get_card

    def missing(self, name):
        if self.data_file == gamedata_path() and name == "Zap":
            return None
        return original(self, name)

    monkeypatch.setattr(CardDataLoader, "get_card", missing)
    bank = generate_root_bank(192801)
    manifest = materialize_configs(
        bank,
        template_capture=CAPTURE,
        expected_template_plan_sha256=PLAN_SHA,
        gamedata=gamedata_path(),
        expected_gamedata_sha256=file_sha(gamedata_path()),
        output=tmp_path / "configs",
    )
    expected = {
        r.family_id for r in bank.requests if any("Zap" in deck for deck in r.decks)
    }
    failed = {
        entry.family_id for entry in manifest.episodes if entry.status == "unsupported"
    }
    assert failed == expected and failed
    assert len(manifest.episodes) == 32
    assert manifest.failed_count == len(expected)
    assert all(
        e.config_path is None and "Zap" in e.failure
        for e in manifest.episodes
        if e.status == "unsupported"
    )


@pytest.mark.parametrize("change", ["cap", "form", "observed_order", "events"])
def test_rejects_unsupported_template_settings(tmp_path, change):
    for name in ["plan.json", "initial.json", "result.json"]:
        (tmp_path / name).write_bytes((CAPTURE / name).read_bytes())
    plan = json.loads((tmp_path / "plan.json").read_text())
    if change == "cap":
        plan["config"]["battle"]["lvlcap"] = 12
    elif change == "form":
        plan["config"]["battle"]["deck0"]["sp"][0]["e"] = 1
    elif change == "events":
        plan["config"]["evt"] = [{"tick": 100}]
    elif change == "observed_order":
        initial = json.loads((tmp_path / "initial.json").read_text())
        initial["players"][0]["deck"][0]["cardId"] = -1
        (tmp_path / "initial.json").write_text(json.dumps(initial))
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    with pytest.raises(ValueError):
        load_verified_template(tmp_path, file_sha(tmp_path / "plan.json"))


def test_changed_source_pin_fails_before_output_creation(tmp_path):
    with pytest.raises(ValueError, match="gamedata hash changed"):
        materialize_configs(
            generate_root_bank(1),
            template_capture=CAPTURE,
            expected_template_plan_sha256=PLAN_SHA,
            gamedata=gamedata_path(),
            expected_gamedata_sha256="0" * 64,
            output=tmp_path / "missing",
        )
    assert not (tmp_path / "missing").exists()
