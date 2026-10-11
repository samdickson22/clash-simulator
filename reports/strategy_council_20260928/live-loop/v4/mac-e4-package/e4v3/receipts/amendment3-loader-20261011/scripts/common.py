"""Shared offline setup for the Amendment 3 RSS/equivalence measurements (05, nice 19, core 63)."""
import json, os, sys, time, hashlib, importlib.util
from pathlib import Path
W = Path("/mpac/sdicks02/jobs/clasher/e4-amendment3-loader-20261011")
RT = Path("/mpac/sdicks02/jobs/clasher/t1-20261010-r1/end-bundle-preparation-r1/runtime")
NATIVE = Path("/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1/native/clasher_core.abi3.so")
NEW = Path("/mpac/sdicks02/jobs/clasher/e4-amendment3-worktree/reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3")
OLD = W / "orig-e4v3"
BUNDLE = W / ("rss-bundle-" + os.environ.get("A3_RUN", "r3") if os.environ.get("A3_R3") else "rss-bundle")

def status():
    fields = {}
    for line in Path("/proc/self/status").read_text().splitlines():
        key, _, value = line.partition(":")
        if key in ("VmRSS", "VmHWM", "RssAnon", "RssFile", "RssShmem"):
            fields[key] = int(value.split()[0]) * 1024
    return fields

def prepare(package):
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19 and os.sched_getaffinity(0) == {63}
    assert all(os.environ.get(k) == "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"))
    sys.path[:0] = [str(RT / "imitation/evaluation/runtime_dependencies"), str(RT / "reports/strategy_council_20260928/imitation")]
    sys.path.insert(0, str(package))

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
