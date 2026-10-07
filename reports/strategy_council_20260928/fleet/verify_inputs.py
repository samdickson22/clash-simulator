"""Verify transferred source and historical certificate receipts without resealing."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
FLEET = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

pins = json.loads((FLEET / "source-mac.json").read_text())
errors = []
for name, expected in pins["files"].items():
    path = ROOT / name
    if not path.exists() or sha(path) != expected:
        errors.append(name)
stage = ROOT / "reports/strategy_council_20260928/engine-speed/stage6"
cards = set()
receipts = 0
manifests = 0
for path in sorted(stage.glob("*manifest.json")):
    cert = json.loads(path.read_text())
    if not cert.get("receipts"):
        continue
    manifests += 1
    cards.update(cert.get("cards", []))
    assert cert.get("mismatches") == 0, path
    for name, expected in cert["receipts"].items():
        receipts += 1
        item = stage / name
        if not item.exists() or sha(item) != expected:
            errors.append(str(item.relative_to(ROOT)))
replay_pins = json.loads((FLEET / "replay-inputs-mac.json").read_text())
for name, expected in replay_pins["files"].items():
    path = ROOT / name
    if not path.exists() or sha(path) != expected:
        errors.append(name)
catalog = Path.home() / ".cache/clasher-native-reference/decoded-logic-1e505767/projectiles.csv"
if not catalog.exists() or sha(catalog) != replay_pins["projectiles_sha256"]:
    errors.append(str(catalog))
native = ROOT / "engine-rs/clasher_core.abi3.so"
expected_binary = FLEET / "evidence/environment-linux.json"
if sys.platform.startswith("linux") and expected_binary.exists():
    expected = json.loads(expected_binary.read_text())["native_sha256"]
    if not native.exists() or sha(native) != expected:
        errors.append("Linux native extension hash")
result = dict(native_sha256=sha(native) if native.exists() else None, replay_inputs=len(replay_pins["files"])+1, source_files=len(pins["files"]), certificate_manifests=manifests,
              certificate_receipts=receipts, incremental_cards=len(cards),
              gamedata_sha256=sha(ROOT / "gamedata.json"), errors=errors,
              note="Historical receipt integrity only; Linux differential reruns are separate. No S122 admission.")
print(json.dumps(result, indent=2))
sys.exit(bool(errors))
