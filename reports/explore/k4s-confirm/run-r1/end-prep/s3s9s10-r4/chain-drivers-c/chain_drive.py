# r4 CHAIN driver: the r4 package code UNMODIFIED, imported top-of-DAG first (s11 -> s10 -> ...); documented test hooks
# only: S10.SSH_BINARY -> the chain fake ssh; and SIMULATED-A3: HOST_PYTHON -> 05's e4v3-venv (bound into the fake
# host by the fake ssh), version 3.12.12 (the real END interpreter is pending a coordinator ruling).
import os, sys
sys.path.insert(0, "/mpac/sdicks02/k4s-runner/run-r1/end-prep/s3s9s10-r4")
import s11_host_repository as S11
S10, S9 = S11.S10, S11.S9
S10.SSH_BINARY = "/dev/shm/s3s9s10r4-scratch/drivers-c/fake-ssh"
S10.HOST_PYTHON = "/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python"
S10.HOST_PYTHON_VERSION = "3.12.12"
S10.HOST_PYTHON_INFO = ()
for kv in os.environ.get("CHAIN_PATCH", "").split(";"):
    if kv:
        mod, name, value = kv.split(":", 2)
        setattr({"S9": S9, "S10": S10, "S11": S11}[mod], name, value)
tool = sys.argv[1]
sys.exit({"s9": S9.main, "s10": S10.main, "s11": S11.main}[tool](sys.argv[2:]))
