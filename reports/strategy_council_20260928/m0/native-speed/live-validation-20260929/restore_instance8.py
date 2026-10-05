"""Restore the reference app on the already-running emulator-5594 (pool instance-8).

Same post-boot procedure as readiness/start_local_reference.py (network
isolation, heap tagging compat, owned forward, app launch, pinned attestation,
configure with the same capture config, ready+paused check), but every adb call
is scoped with -s emulator-5594 and no global `adb devices` listing is made.
The emulator process itself is not touched. Receipts go to OUTPUT.

Usage: restore_instance8.py OUTPUT
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "reports/strategy_council_20260928/m0/readiness"))
import start_local_reference as launcher  # noqa: E402  (constants only)
from smoke_reference_battle import request  # noqa: E402

SERIAL, PORT = "emulator-5594", 26796
EMULATOR_PID = 98464


def main():
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=False)
    log = output / "adb-operations.jsonl"

    def adb(*args, check=True):
        result = subprocess.run([str(launcher.ADB), "-s", SERIAL, *args], capture_output=True,
                                text=True, timeout=60, check=False)
        with log.open("a") as target:
            target.write(json.dumps({"args": args, "returncode": result.returncode,
                                     "stdout": result.stdout[-2000:], "stderr": result.stderr}) + "\n")
        if check and result.returncode:
            raise RuntimeError(f"ADB operation failed: {args}")
        return result

    running = subprocess.check_output(["ps", "-p", str(EMULATOR_PID), "-o", "command="], text=True)
    if "-port 5594" not in running or "-read-only" not in running:
        raise RuntimeError("emulator-5594 process identity changed")
    if adb("shell", "getprop", "sys.boot_completed").stdout.strip() != "1":
        raise RuntimeError("emulator-5594 not booted")
    if adb("shell", "id", "-u").stdout.strip() != "0":
        raise RuntimeError("adbd is not root on emulator-5594")
    adb("shell", "svc", "wifi", "disable")
    adb("shell", "svc", "data", "disable")
    package = adb("shell", "dumpsys", "package", launcher.PACKAGE).stdout
    uid = re.search(r"\b(?:userId|appId)=(\d+)\b", package).group(1)
    for firewall in ("iptables", "ip6tables"):
        rule = ["OUTPUT", "-m", "owner", "--uid-owner", uid, "!", "-o", "lo", "-j", "REJECT"]
        if adb("shell", firewall, "-C", *rule, check=False).returncode:
            adb("shell", firewall, "-A", *rule)
        adb("shell", firewall, "-C", *rule)
    adb("shell", "am", "compat", "disable", "NATIVE_HEAP_POINTER_TAGGING", launcher.PACKAGE)
    adb("forward", f"tcp:{PORT}", "tcp:26789")
    if adb("shell", "pidof", launcher.PACKAGE, check=False).stdout.strip():
        raise RuntimeError("app already running; refusing to start a second instance")
    adb("shell", "am", "start", "-n", launcher.PACKAGE + "/com.supercell.clashroyale.GameApp")
    deadline, last = time.monotonic() + 180, None
    while time.monotonic() < deadline:
        try:
            attestation = request(PORT, "attest")
            if attestation.get("attestation", {}).get("production_ready") is True:
                break
            last = "warming up"
        except (OSError, ValueError) as error:
            last = str(error)
        time.sleep(2)
    else:
        raise RuntimeError(f"probe unavailable: {last}")
    digest = hashlib.sha256(json.dumps(attestation, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    (output / "attestation.json").write_text(json.dumps(attestation, indent=2) + "\n")
    if digest != launcher.EXPECTED_ATTESTATION:
        raise ValueError("live attestation differs from pinned reference")
    config = json.loads((launcher.CAPTURE / "plan.json").read_text())["config"]
    configured = request(PORT, "configure " + json.dumps(config, separators=(",", ":")))
    render = request(PORT, "render status")
    status = request(PORT, "status")
    (output / "status.json").write_text(json.dumps(status, indent=2) + "\n")
    if status.get("ready") is not True or status.get("paused") is not True:
        raise RuntimeError("configured reference is not ready and paused")
    pid = adb("shell", "pidof", launcher.PACKAGE).stdout.strip()
    (output / "complete.json").write_text(json.dumps({
        "emulator_pid": EMULATOR_PID, "app_pid": pid, "app_uid": int(uid),
        "attestation_sha256": digest, "serial": SERIAL, "probe_port": PORT,
        "configured": configured, "render_status": render,
        "renderSuppressed": status.get("renderSuppressed"),
        "status": "ready_paused_development_only",
        "procedure": "start_local_reference.py post-boot steps, adb scoped to emulator-5594",
    }, indent=2) + "\n")
    print(json.dumps({"digest": digest, "pid": pid, "paused": status["paused"],
                      "ready": status["ready"], "renderSuppressed": status.get("renderSuppressed")}))


if __name__ == "__main__":
    main()
