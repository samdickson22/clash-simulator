# AUDIT driver used as the wrapper's measurement command: argv[1] = the staged <tools>/k4s_end_preflight.py (loaded by
# path, unmodified); the rest is its CLI. Only `hostinfo` is supplied (audit runs at nice 19, not 10).
import importlib.util, sys
path = sys.argv[1]
spec = importlib.util.spec_from_file_location("k4s_end_preflight", path)
S5 = importlib.util.module_from_spec(spec); sys.modules["k4s_end_preflight"] = S5; spec.loader.exec_module(S5)
a = S5.parser().parse_args(sys.argv[2:])
host = sys.argv[sys.argv.index("--out") + 1].split("/preflight-")[1][:6]
sys.exit(S5.run(a, hostinfo=dict(host=host, nice=10, sched_other=True, optimized=False)))
