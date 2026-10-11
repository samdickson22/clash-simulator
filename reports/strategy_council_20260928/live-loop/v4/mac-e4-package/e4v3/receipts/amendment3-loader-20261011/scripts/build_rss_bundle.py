"""Offline END-like bundle on 05: T1's END manifest sets + 05 reconstruction states.pkl + r2 state rows."""
import json, os, pickle, sys, hashlib
sys.path.insert(0, os.path.dirname(__file__))
from common import *
prepare(NEW)
from tier_backend import setup_imports
from convert_states import file_sha
setup_imports(RT, NATIVE)
rows_dir = W / "end-states-rows-r2"
BUNDLE.mkdir()
B = Path("/mpac/sdicks02/jobs/clasher/t1-20261010-r1")
with open(B / "corpus-publication-staging-r1/states.pkl", "rb") as f: public = pickle.load(f)
with open("/mpac/sdicks02/jobs/clasher/e4v3-bundle-05-final/states.pkl", "rb") as f: golden = pickle.load(f)
with open(BUNDLE / "states.pkl", "xb") as f: pickle.dump(public + golden, f, protocol=5)
del public, golden
for name in ("states-rows.json", "states-rows.bin"):
    os.link(rows_dir / name, BUNDLE / name)
for name in ("v1.pt", "R3a.pt"):
    os.symlink(Path("/mpac/sdicks02/jobs/clasher/e4v3-bundle-05-final") / name, BUNDLE / name)
manifest = json.loads((B / "END-manifest-template-01-r1.json").read_text())
index = json.loads((BUNDLE / "states-rows.json").read_text())
manifest["files"] = {"states.pkl": index["source"]["sha256"],  # declared 0addf7c0; file is the 05 re-dump
                     "states-rows.json": file_sha(BUNDLE / "states-rows.json")[0],
                     "states-rows.bin": index["container"]["sha256"]}
manifest["note"] = "offline Amendment 3 measurement bundle, 05; states.pkl is the 05 re-dump " + file_sha(BUNDLE / "states.pkl")[0]
(BUNDLE / "tiers-pins.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
print(json.dumps(dict(bundle=str(BUNDLE), redump_sha256=file_sha(BUNDLE / "states.pkl")[0], files=manifest["files"])))
