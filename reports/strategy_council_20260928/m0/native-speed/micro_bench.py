"""Transport micro-benchmark on one idle instance (read-only commands only)."""
import json, statistics, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]
import read_native_public_levels as reader
from smoke_reference_battle import request
from clasher.rl.native_probe_transport import PersistentProbeSession

port, serial, out = int(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
adb = Path("/Users/sam/.cache/clasher-native-reference/android-sdk/platform-tools/adb")
def timed(fn, n):
    samples = []
    for _ in range(n):
        t = time.perf_counter(); fn(); samples.append(time.perf_counter() - t)
    return {"n": n, "median_ms": round(statistics.median(samples) * 1000, 3),
            "p90_ms": round(sorted(samples)[int(n * .9)] * 1000, 3)}
report = {"port": port, "serial": serial}
report["probe_status_per_command_connection"] = timed(lambda: request(port, "status"), 100)
report["probe_observe_per_command_connection"] = timed(lambda: request(port, "observe"), 100)
with PersistentProbeSession(port) as s:
    report["probe_status_session_v1"] = timed(lambda: s("status"), 100)
    report["probe_observe_session_v1"] = timed(lambda: s("observe"), 100)
with reader._PersistentAdbShell(adb, serial) as shell:
    pid = shell.pid()
    status = request(port, "status")
    manager = int(status["manager"], 16)
    report["adb_exchange_true"] = timed(lambda: shell._exchange("true", max_bytes=16), 100)
    report["adb_exchange_pidof"] = timed(lambda: shell.pid(), 50)
    report["adb_exchange_dd_8_bytes"] = timed(lambda: shell.read(pid, [(manager + 0xa8, 8)]), 100)
    report["adb_exchange_dd_16x8_bytes"] = timed(lambda: shell.read(pid, [(manager + 0xa8, 8)] * 16), 50)
out.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=1))
