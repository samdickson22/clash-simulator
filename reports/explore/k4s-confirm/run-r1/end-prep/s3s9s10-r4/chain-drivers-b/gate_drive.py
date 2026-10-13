# r4 CHAIN-b driver: the s5s6s7-r4 S7 gate (unmodified bytes, loaded from its own directory so its canonical bootstrap
# finds safe_input / host tool beside it); documented module constants redirected to SCRATCH: LAUNCH_BASE, RECEIVE,
# STAGING_BUNDLES (nothing is written under run-r1). Runs build-argv / validate_roots only (no ssh).
import importlib.util, sys
path = "/mpac/sdicks02/k4s-runner/run-r1/end-prep/s5s6s7-r4/k4s_end_launch_gate.py"
spec = importlib.util.spec_from_file_location("k4s_end_launch_gate", path)
G = importlib.util.module_from_spec(spec); sys.modules["k4s_end_launch_gate"] = G; spec.loader.exec_module(G)
G.LAUNCH_BASE = "/tmp/k4s-r4chainb-H1qWfE/end-launch"
G.RECEIVE = {"end": "/tmp/k4s-r4chainb-H1qWfE/end-received", "preflight": "/tmp/k4s-r4chainb-H1qWfE/preflight-received"}
G.STAGING_BUNDLES = "/tmp/k4s-r4chainb-H1qWfE/staging-bundles"
sys.exit(G.main(sys.argv[1:]))
