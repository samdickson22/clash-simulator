"""Paired decision reports must be bound to unmodified production parents."""

import importlib
import json
from pathlib import Path

import pytest


def fixture(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    module = importlib.import_module("audit_calibration_decisions")
    rows = [
        {
            "response_seed": 7,
            "candidate": c,
            "engine": e,
            "failure": None,
            "commands": [],
            "decision_counts": [1, 1],
            "terminal": {
                "winner": 0,
                "tick": 3601,
                "towers": [{"owner": 0, "hp": 100}],
            },
        }
        for c in ("wait", "recorded")
        for e in ("native", "scalar")
    ]
    parents = {}
    for engine in ("native", "scalar"):
        p = tmp_path / engine
        p.mkdir()
        for name, data in {
            "results.json": [r for r in rows if r["engine"] == engine],
            "provenance.json": {},
            "complete.json": {"sources_unchanged": True},
        }.items():
            (p / name).write_text(json.dumps(data))
        parents[str(p)] = {
            n: module.digest(p / n)
            for n in ("results.json", "provenance.json", "complete.json")
        }
    paired = tmp_path / "paired"
    paired.mkdir()
    for name, data in {
        "results.json": rows,
        "complete.json": {
            "sources_unchanged": True,
            "runtime_override": None,
            "parents": parents,
        },
        "protocol.json": {
            "family": "f",
            "root_duplicate_group_id": "r",
            "root_tick": 90,
            "owner": 0,
            "response_seeds": [7],
            "candidates": [{"name": c} for c in ("wait", "recorded")],
        },
    }.items():
        (paired / name).write_text(json.dumps(data))
    return module, paired


def test_verified_production_results_are_loaded(tmp_path, monkeypatch):
    module, path = fixture(tmp_path, monkeypatch)
    roots, hashes = module.load_paired(path)
    assert len(roots) == 1 and roots[0].family_id == "f"
    assert len(hashes) == 3


@pytest.mark.parametrize("fault", ["parent", "paired", "override", "family"])
def test_tampered_or_unscoped_inputs_are_rejected(tmp_path, monkeypatch, fault):
    module, path = fixture(tmp_path, monkeypatch)
    if fault == "parent":
        (tmp_path / "native" / "provenance.json").write_text('{"changed": true}')
    elif fault == "paired":
        p = path / "results.json"
        rows = json.loads(p.read_text())
        rows[0]["terminal"]["winner"] = 1
        p.write_text(json.dumps(rows))
    elif fault == "override":
        p = path / "complete.json"
        data = json.loads(p.read_text())
        data["runtime_override"] = "prototype"
        p.write_text(json.dumps(data))
    else:
        p = path / "protocol.json"
        data = json.loads(p.read_text())
        del data["family"]
        p.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        module.load_paired(path)
