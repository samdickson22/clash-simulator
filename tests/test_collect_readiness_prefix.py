"""Exercise the runnable collector with a real ledger and an offline native double."""

import argparse
import importlib
import json
import runpy
from pathlib import Path

import pytest

from clasher.paths import gamedata_path, project_root
from clasher.rl.readiness_capture_ownership import (
    AttemptDeclaration,
    EpisodeSpec,
    declare_attempt,
)
from clasher.rl.readiness_execution import canonical_sha, file_sha
from clasher.rl.readiness_native_config import materialize_configs
from clasher.rl.readiness_root_bank import RootBank, RootRequest, generate_root_bank
from clasher.rl.training_readiness_v2 import Protocol


@pytest.mark.parametrize(
    "reject,close_failure", [(False, False), (True, False), (False, True)]
)
def test_cli_binds_real_ledger_before_fake_native_prefix_and_seals_receipt(
    tmp_path, monkeypatch, reject, close_failure
):
    workspace = project_root()
    monkeypatch.syspath_prepend(str(workspace / "scripts"))
    cli = importlib.import_module("collect_readiness_prefix")
    fixtures = runpy.run_path(str(workspace / "tests/test_readiness_prefix.py"))
    native = fixtures["NativeDouble"](reject=reject)
    deck = fixtures["DECK"]
    bank = generate_root_bank(192801)
    rows = list(bank.requests)
    index = next(
        i for i, r in enumerate(rows) if r.focal_card == "Cannon" and r.root_owner == 0
    )
    rows[index] = RootRequest(
        **{
            **rows[index].model_dump(),
            "decks": (deck, deck),
            "prefix_styles": ("pressure", "pressure"),
            "context": "own_half_threat",
            "stop_tick": 100,
            "prefix_owner_min_elixir": 0,
        }
    )
    bank = RootBank(
        schema_version="readiness-v2-root-bank-v1",
        master_seed=bank.master_seed,
        requests=tuple(rows),
    )
    native_configs = tmp_path / "configs"
    capture = (
        workspace
        / "reports/calibration_development_20260915/deck-mix-development/mix0-reversed"
    )
    manifest = materialize_configs(
        bank,
        template_capture=capture,
        expected_template_plan_sha256="4c47d7839a9e5dd9fe49312949b3276b5bd332dd139225285ea4fb56bc591259",
        gamedata=gamedata_path(),
        expected_gamedata_sha256=file_sha(gamedata_path()),
        output=native_configs,
    )
    chosen = manifest.episodes[index]
    request = rows[index]
    catalog = workspace / "tests/fixtures/native_projectiles_15_535_86.csv"
    source_files = [
        *sorted((workspace / "src/clasher").rglob("*.py")),
        *[
            workspace / "scripts" / name
            for name in [
                "collect_readiness_prefix.py",
                "read_native_public_levels.py",
                "run_readiness_v2.py",
                "smoke_reference_battle.py",
            ]
        ],
    ]
    source_pins = {str(path): file_sha(path) for path in source_files}
    input_pins = {
        str(path): file_sha(path)
        for path in [
            native_configs / "manifest.json",
            native_configs / "root-bank.json",
            gamedata_path(),
            catalog,
        ]
    }
    attestation = {"ok": True, "attestation": {"synthetic_test_only": True}}
    declaration = AttemptDeclaration(
        attempt_id="synthetic-prefix-integration",
        evidence_role="opened_development",
        root_bank_sha256=canonical_sha(bank.model_dump(mode="json")),
        generator_sha256=file_sha(workspace / "src/clasher/rl/readiness_root_bank.py"),
        converter_manifest_sha256=file_sha(native_configs / "manifest.json"),
        pre_protocol=Protocol(
            attempt_id="synthetic-prefix-integration", source_pins=source_pins
        ),
        native_attestation_sha256=canonical_sha(attestation),
        catalog_sha256=file_sha(catalog),
        gamedata_sha256=file_sha(gamedata_path()),
        workspace_gamedata_sha256=file_sha(gamedata_path()),
        source_pins=source_pins,
        input_pins=input_pins,
        episodes=(
            EpisodeSpec(
                family_id=request.family_id,
                source_episode_id=request.source_episode_id,
                config_path=str(native_configs / chosen.config_path),
                config_file_sha256=chosen.config_file_sha256,
                config_sha256=chosen.config_sha256,
                root_request_sha256=chosen.root_request_sha256,
                root_owner=0,
            ),
        ),
    )
    ledger = tmp_path / "ownership.sqlite"
    declare_attempt(ledger, declaration)

    def transport(port, text):
        if text == "attest":
            return attestation
        if text == "observe-rich":
            return {"schema": "native-rich-telemetry.v3"}
        if text.startswith("configure "):
            import sqlite3

            with sqlite3.connect(ledger) as db:
                assert (
                    db.execute("SELECT count(*) FROM episode_claims").fetchone()[0] == 1
                )
        return native.command(text)

    monkeypatch.setattr(cli, "native_request", transport)
    sessions = []

    class SessionDouble:
        def __init__(self, *args, **kwargs):
            assert kwargs["expected_attestation_sha256"] == canonical_sha(attestation)
            self.state = "new"
            self.reads = 0
            sessions.append(self)

        def __enter__(self):
            assert native.tick == 0
            assert any(c.startswith("configure ") for c in native.calls)
            self.state = "open"
            return self

        def read_levels(self):
            assert self.state == "open"
            self.reads += 1
            return {
                "ordinary": native.ordinary(),
                "verified_session": {"read_index": self.reads},
            }

        def __exit__(self, exc_type, exc, tb):
            self.state = "failed" if close_failure or exc is not None else "verified"
            if close_failure:
                raise ValueError("synthetic closing verification failed")
            return False

        @property
        def provenance(self):
            assert self.state in ("verified", "failed"), (
                "provenance accessed before context close"
            )
            return {
                "status": self.state,
                "reads_completed": self.reads,
                "synthetic_test_only": True,
            }

    monkeypatch.setattr(cli, "VerifiedNativeReadSession", SessionDouble)
    make_builder = cli.public_reference_builder

    def builder(*args, **kwargs):
        native.builder = make_builder(*args, **kwargs)
        return native.builder

    monkeypatch.setattr(cli, "public_reference_builder", builder)
    monkeypatch.setattr(
        cli,
        "public_views",
        lambda frame, adapter, maps, history: native.project(frame, history),
    )
    output = tmp_path / "prefixes"
    summary = cli.collect(
        argparse.Namespace(
            registry=ledger,
            attempt_id=declaration.attempt_id,
            manifest=native_configs / "manifest.json",
            catalog=catalog,
            catalog_sha256=file_sha(catalog),
            adb=Path("/unused-offline-test"),
            port=26789,
            serial="offline-test",
            family_id=None,
            output=output,
        )
    )
    expected_status = "failed" if reject or close_failure else "selected"
    assert summary["episodes"][0]["status"] == expected_status, summary
    receipt = json.loads((output / "episode-00" / "capture-receipt.json").read_text())
    if reject or close_failure:
        assert receipt["selected_family"] is None
        assert receipt["prefix_complete"] is False
    else:
        assert (
            receipt["selected_family"]["independence_id"] == request.source_episode_id
        )
        assert receipt["selected_family"]["role"] == "opened_development"
        assert receipt["capture_binding"]["root_tick"] == 95
    assert receipt["game_complete"] is False
    assert "transport.jsonl.gz" in receipt["artifact_hashes"]
    assert "native-read-session.json" in receipt["artifact_hashes"]
    assert len(sessions) == 1 and sessions[0].reads >= 1
    proof = json.loads((output / "episode-00" / "native-read-session.json").read_text())
    assert proof["status"] == ("failed" if reject or close_failure else "verified")
    if close_failure:
        result = json.loads((output / "episode-00" / "result.json").read_text())
        assert result["selection"]["status"] == "selected"
        assert result["status"] == "failed" and result["prefix_complete"] is False
        assert "closing verification failed" in receipt["failure"]

    assert len([c for c in native.calls if c.startswith("configure ")]) == 1
    repeated = cli.collect(
        argparse.Namespace(
            registry=ledger,
            attempt_id=declaration.attempt_id,
            manifest=native_configs / "manifest.json",
            catalog=catalog,
            catalog_sha256=file_sha(catalog),
            adb=Path("/unused-offline-test"),
            port=26789,
            serial="offline-test",
            family_id=None,
            output=tmp_path / "repeat-forbidden",
        )
    )
    assert repeated["episodes"][0]["status"] == "failed"
    assert repeated["episodes"][0]["claimed"] is False
    assert len([c for c in native.calls if c.startswith("configure ")]) == 1
