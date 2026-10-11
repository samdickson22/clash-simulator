import sys, pickle, hashlib, json, time
sys.path.insert(0, sys.argv[1])  # package dir
from convert_states import HashWriter, load_inventory
from tier_backend import setup_imports
rt = sys.argv[2]
sys.path[:0] = [rt + "/imitation/evaluation/runtime_dependencies", rt + "/reports/strategy_council_20260928/imitation"]
setup_imports(rt, "/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1/native/clasher_core.abi3.so")
import numpy, torch
B = "/mpac/sdicks02/jobs/clasher/t1-20261010-r1"
t = time.monotonic()
with open(B + "/corpus-publication-staging-r1/states.pkl", "rb") as f:
    public = pickle.load(f)
w = HashWriter(); pickle.dump(public, w, protocol=5)
inv = load_inventory(B + "/corpus-publication-staging-r1/corpora.json", "3501e2acf444c2f23a5ed9f9471ebcabfc66216b412847c033759c3f4b2cde13")
match = sum(inv.get(str(r["id"])) == hashlib.sha256(pickle.dumps(r, protocol=5)).hexdigest() for r in public)
first_bad = next((str(r["id"]) for r in public if inv.get(str(r["id"])) != hashlib.sha256(pickle.dumps(r, protocol=5)).hexdigest()), None)
print(json.dumps(dict(numpy=numpy.__version__, torch=torch.__version__, public_rows=len(public),
    public_redump_sha=w.digest.hexdigest(), public_redump_bytes=w.size, public_file_sha="282b0877...",
    inventory_match=match, first_mismatch=first_bad, seconds=time.monotonic()-t)), flush=True)
r = public[0]
print({k: type(v).__module__ + "." + type(v).__name__ for k, v in r.items()})
