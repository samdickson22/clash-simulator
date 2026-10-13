# AUDIT driver: S5 verify-received (scratch copy of s5s6s7-r3/k4s_end_preflight.py, unmodified) on the fake 05.
import importlib.util, sys
spec = importlib.util.spec_from_file_location("k4s_end_preflight", "/dev/shm/ia-r1/code/s5s6s7-r3/k4s_end_preflight.py")
S5 = importlib.util.module_from_spec(spec); sys.modules["k4s_end_preflight"] = S5; spec.loader.exec_module(S5)
sys.exit(S5.main(sys.argv[1:]))
