"""Ad-hoc NON-COUNTED Darwin check of stage_nocopy on synthetic data, reusing the FrozenPrepareBundle fixture:
expects method 'clonefile' (own inode, APFS copy-on-write), byte-identical tiers-pins, verify_bundle pass,
and fail-closed on write access."""
import contextlib, json, os, sys, unittest
from io import StringIO
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parent)); sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))
import stage_nocopy
import test_stage_nocopy as t
case = t.FrozenPrepareBundle("test_refuses_helper_inside_runtime_root"); case.setUp()
with contextlib.redirect_stdout(StringIO()):
    with mock.patch.object(sys, "argv", ["prepare_bundle.py"] + case.arguments("plain")):
        case.pb.main()
    stage_nocopy.PLACED.clear(); frozen = case.pb.copy_file
    try:
        stage_nocopy.main(["--e4v3", t.E4V3, "--"] + case.arguments("nocopy"))
    finally:
        case.pb.copy_file = frozen
plain, nocopy = case.r / "plain", case.r / "nocopy"
out = dict(platform=sys.platform,
  tiers_pins_identical=(plain/"tiers-pins.json").read_bytes() == (nocopy/"tiers-pins.json").read_bytes(),
  sidecar_identical=(plain/"tiers-pins.sha256").read_bytes() == (nocopy/"tiers-pins.sha256").read_bytes())
v = stage_nocopy.verify_bundle(nocopy)
out["verify_passes"] = v["passes"]; out["methods"] = {f["file"]: f["method"] for f in v["files"]}
out["read_only"] = {n: oct(os.stat(nocopy/n).st_mode & 0o777) for n in stage_nocopy.FIXTURE}
os.chmod(nocopy/"states-rows.json", 0o644)
try:
    stage_nocopy.verify_bundle(nocopy); out["fail_closed_on_writable"] = False
except PermissionError:
    out["fail_closed_on_writable"] = True
print(json.dumps(out, sort_keys=True)); case.tearDown()
