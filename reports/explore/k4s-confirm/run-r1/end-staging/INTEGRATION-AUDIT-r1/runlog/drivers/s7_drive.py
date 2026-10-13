# AUDIT driver: S7 gate (scratch copy of s5s6s7-r3, unmodified) with its test hook SSH_BINARY -> fake ssh.
import importlib.util, sys
path = "/dev/shm/ia-r1/code/s5s6s7-r3/k4s_end_launch_gate.py"
spec = importlib.util.spec_from_file_location("k4s_end_launch_gate", path)
G = importlib.util.module_from_spec(spec); sys.modules["k4s_end_launch_gate"] = G; spec.loader.exec_module(G)
G.SSH_BINARY = "/dev/shm/ia-r1/drivers/fake-ssh-s7"
sys.exit(G.main(sys.argv[1:]))
