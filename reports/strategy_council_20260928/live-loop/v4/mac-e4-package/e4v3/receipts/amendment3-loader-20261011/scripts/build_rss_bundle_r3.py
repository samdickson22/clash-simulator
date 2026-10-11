"""Offline bundle bound to the SHA-verified --states conversion (r3s) of the 05 re-dump states.pkl."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *
sys.path.insert(0, str(NEW))
from convert_states import file_sha
run = os.environ.get("A3_RUN", "r3"); out = W / ("rss-bundle-" + run); out.mkdir()
os.link(W / "rss-bundle/states.pkl", out / "states.pkl")
for name in ("states-rows.json", "states-rows.bin"):
    os.link(W / ("end-states-rows-" + run + "s") / name, out / name)
for name in ("v1.pt", "R3a.pt"):
    os.symlink(Path("/mpac/sdicks02/jobs/clasher/e4v3-bundle-05-final") / name, out / name)
manifest = json.loads(Path("/mpac/sdicks02/jobs/clasher/t1-20261010-r1/END-manifest-template-01-r1.json").read_text())
manifest["files"] = {n: file_sha(out / n)[0] for n in ("states.pkl", "states-rows.json", "states-rows.bin")}
manifest["note"] = "offline Amendment 3 measurement bundle on 05; states.pkl is the 05 re-dump of the END fixture"
(out / "tiers-pins.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
print(json.dumps(manifest["files"]))
