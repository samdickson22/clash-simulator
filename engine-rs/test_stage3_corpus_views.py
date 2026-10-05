"""Gate consumed views/actions against the actual OQ checkpoint builder."""

import json
from pathlib import Path
import sys
import cloudpickle
import clasher_core
from differential import ES, config, snapshot
from stage2_matches import PILOT
from test_stage3 import metadata, verify_view, fingerprint
from clasher.rl.public_action_mask import PublicActionMaskBuilder

sys.path.insert(0, str(ES / "srp_reference"))
from oq_lib import Context

ctx = Context()
builder = ctx.loaded.builder
scripts = clasher_core.NativeScripts(json.dumps(metadata(builder)))
mask = PublicActionMaskBuilder(builder)
cfg = config(PILOT)
roots = cloudpickle.loads(
    (Path.home() / ".cache/clasher-engine-speed/stage3-srp-snapshots.pkl").read_bytes()
)
for i, b in enumerate(roots):
    verify_view(
        b,
        clasher_core.BattleState(snapshot(b, cfg)),
        scripts,
        builder,
        mask,
        actions=True,
    )
    if i % 25 == 0:
        print(i, "PASS", flush=True)
(ES / "results/stage3_corpus_views.json").write_text(
    json.dumps(
        dict(roots=len(roots), seats=2, styles=4, fingerprint=fingerprint()), indent=2
    )
    + "\n"
)
print("PASS", len(roots), "roots, actual OQ builder", flush=True)
