# r4 CHAIN (from the audit driver): FROZEN end_reference.frozen_identity, imported from the STAGED r4 runtime on the
# fake 03, against the STAGED real bundle and the STAGED real native + K4 corpus (real digests: plain hashing, no
# backend, no pickle, no torch, no native load).
import sys
from pathlib import Path
from types import SimpleNamespace
RT, BUNDLE, NATIVE, CORPUS = sys.argv[1:5]
K = RT + "/reports/explore/k4s-confirm"
sys.path[:0] = [K + "/mac", K, RT + "/reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3"]
import end_reference as ER
from tier_backend import NATIVE_SHA, validate_bundle
a = SimpleNamespace(bundle=Path(BUNDLE), runtime_root=Path(RT), native=Path(NATIVE), corpus=Path(CORPUS),
    corpus_sha256=ER.K4_CORPUS_SHA256, kernel=ER.KERNEL_REL, scorer=ER.SCORER_REL,
    k4s_manifest=ER.HERE / "mac" / ER.L.MANIFEST_NAME, k4s_manifest_sha256="74314eda04a7100d7ce10141394282b646723d29d0e7bb3883355d1ef1db6357",
    sd1_manifest=ER.HERE / "SD1-MANIFEST.json", sd1_manifest_sha256="b8ce7b4c088e275894b9654a85923aacf428656e71433f60ec32bed1ae63ef76")
print("ER file:", ER.__file__)
m, pins, host_pins = ER.frozen_identity(a, validate_bundle, NATIVE_SHA)
print("FROZEN_IDENTITY_OK host_pins", host_pins, "pins keys", sorted(pins))
