# AUDIT driver: FROZEN end_reference.frozen_identity (unmodified runtime code, imported from the runtime given) with
# the frozen validate_bundle; ONLY the frozen code's own documented 'digest' hook is used, for the native/corpus
# binaries (not staged on 05). Pure file reads/hashes; no backend, no pickle, no torch.
import sys, hashlib
from pathlib import Path
from types import SimpleNamespace
RT = sys.argv[1]
K = RT + "/reports/explore/k4s-confirm"
sys.path[:0] = [K + "/mac", K, RT + "/reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3"]
import end_reference as ER
from tier_backend import NATIVE_SHA, validate_bundle
bundle = "/tmp/ia-r1-bundles-DQ3CBz/end-ref-127x03-pf00"
a = SimpleNamespace(bundle=Path(bundle), runtime_root=Path(RT), native=Path("/nonexistent/native-stub"),
    corpus=Path("/nonexistent/corpus-stub"), corpus_sha256=ER.K4_CORPUS_SHA256, kernel=ER.KERNEL_REL, scorer=ER.SCORER_REL,
    k4s_manifest=ER.HERE / "mac" / ER.L.MANIFEST_NAME, k4s_manifest_sha256="74314eda04a7100d7ce10141394282b646723d29d0e7bb3883355d1ef1db6357",
    sd1_manifest=ER.HERE / "SD1-MANIFEST.json", sd1_manifest_sha256="b8ce7b4c088e275894b9654a85923aacf428656e71433f60ec32bed1ae63ef76")
stub = {str(a.native): ER.L.NATIVE_PROVENANCE_SHA, str(a.corpus): ER.L.T1_K4_CORPUS_SHA}
print("NATIVE_SHA(tier_backend) == k4s NATIVE_PROVENANCE_SHA:", NATIVE_SHA == ER.L.NATIVE_PROVENANCE_SHA)
try:
    m, pins, host_pins = ER.frozen_identity(a, validate_bundle, NATIVE_SHA, digest=lambda p: stub[str(p)])
    print("frozen_identity OK; host_pins", host_pins, "pins keys", sorted(pins)[:8])
except BaseException as e:
    import traceback; traceback.print_exc(limit=3); print("FROZEN_IDENTITY_FAILED:", type(e).__name__, e)
