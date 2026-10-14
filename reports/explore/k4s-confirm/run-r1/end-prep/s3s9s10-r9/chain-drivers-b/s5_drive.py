# AUDIT driver: S5 run() of the STAGED <base>/tools/k4s_end_preflight.py (unmodified, loaded by its own path so its
# canonical bootstrap finds safe_input/host tool beside it), real Frozen factory; only `hostinfo` is supplied (the
# documented test hook) because the audit runs at nice 19, not the production nice 10.
import importlib.util, sys
path = "/mpac/sdicks02/jobs/clasher/k4s-end-r1/tools/k4s_end_preflight.py"
spec = importlib.util.spec_from_file_location("k4s_end_preflight", path)
S5 = importlib.util.module_from_spec(spec); sys.modules["k4s_end_preflight"] = S5; spec.loader.exec_module(S5)
a = S5.parser().parse_args(sys.argv[1:])
host = sys.argv[sys.argv.index("--out") + 1].split("/preflight-")[1][:6]
rc = S5.run(a, hostinfo=dict(host=host, nice=10, sched_other=True, optimized=False))
print("S5 run rc", rc)
