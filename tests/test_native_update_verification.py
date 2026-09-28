import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "verify_native_update",
    Path(__file__).parents[1] / "scripts/verify_native_update.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixtures(tmp_path):
    root = tmp_path / "update"
    root.mkdir()
    (root / "fingerprint.json").write_bytes(b"fingerprint")
    (root / "data.toml").write_bytes(b"payload")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "source_files": {
                    "runtime-update/data.toml": hashlib.sha256(b"payload").hexdigest()
                }
            }
        )
    )
    engine = tmp_path / "engine.json"
    engine.write_text(
        json.dumps(
            {
                "runtime_content_version": "test",
                "runtime_fingerprint_sha256": hashlib.sha256(
                    b"fingerprint"
                ).hexdigest(),
            }
        )
    )
    return root, manifest, engine


def test_fingerprint_alone_cannot_certify_missing_or_corrupt_update(tmp_path):
    args = fixtures(tmp_path)
    assert module.verify(*args)["status"] == "matched"
    data = args[0] / "data.toml"
    data.write_bytes(b"wrong")
    assert module.verify(*args)["status"] == "mismatch"
    data.unlink()
    assert module.verify(*args)["status"] == "mismatch"


def test_rejects_escaping_manifest_path(tmp_path):
    root, manifest, engine = fixtures(tmp_path)
    manifest.write_text(
        json.dumps({"source_files": {"runtime-update/../outside": "bad"}})
    )
    with pytest.raises(ValueError, match="unsafe"):
        module.verify(root, manifest, engine)
