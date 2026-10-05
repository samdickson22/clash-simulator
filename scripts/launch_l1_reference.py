"""Launch the unchanged offline reference with a loopback screenshot gRPC endpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path.home() / ".cache/clasher-native-reference"
ADB = CACHE / "android-sdk/platform-tools/adb"
EMULATOR = CACHE / "android-sdk/emulator/emulator"
PACKAGE = "nullsroyale.rel.free"
CAPTURE = ROOT / "artifacts/worktree-data/clasher-simulator-fidelity-20260913/reports/calibration_development_20260915/expanded-deck-development/forward-0"
EXPECTED_ATTESTATION = "864227bf7208aa9c06cd976db3fa0734a32277b0552f92e496ad283a917b4a93"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--resume-owned", type=Path)
    parser.add_argument("--gpu", choices=("swiftshader", "host"), default="swiftshader")
    parser.add_argument("--console-port", type=int, default=5580)
    parser.add_argument("--probe-port", type=int, default=26789)
    parser.add_argument("--read-only", action="store_true", default=True)
    parser.add_argument("--grpc-port", type=int, default=8554)
    args = parser.parse_args()
    if args.console_port % 2 or not 5554 <= args.console_port <= 5682:
        raise ValueError("Console port must be an even supported emulator port")
    if not 1024 <= args.probe_port <= 65535:
        raise ValueError("Invalid host probe port")
    serial = f"emulator-{args.console_port}"
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    log = output / "adb-operations.jsonl"

    def adb(*args: str, check: bool = True) -> subprocess.CompletedProcess:
        result = subprocess.run(
            [str(ADB), "-s", serial, *args], capture_output=True,
            text=True, timeout=60, check=False,
        )
        with log.open("a") as target:
            target.write(json.dumps({"args": args, "returncode": result.returncode,
                                     "stdout": result.stdout, "stderr": result.stderr}) + "\n")
        if check and result.returncode:
            raise RuntimeError(f"ADB operation failed: {args[0]}")
        return result

    devices = subprocess.check_output([str(ADB), "devices"], text=True)
    resume = args.resume_owned
    if resume is None and serial in devices:
        raise RuntimeError("Reference emulator already exists; do not take it over")
    if resume is None:
        existing = subprocess.run(
            ["pgrep", "-f", "qemu-system.*clasher_reference_api35"],
            text=True, capture_output=True,
        )
        if existing.returncode == 0:
            if len(existing.stdout.split()) >= 2:
                raise RuntimeError("L1 permits at most two emulator instances")
            if not args.read_only:
                raise RuntimeError("Reference emulator process already exists")
            for value in existing.stdout.split():
                running = subprocess.check_output(
                    ["ps", "-p", value, "-o", "command="], text=True
                )
                if " -read-only" not in running:
                    raise RuntimeError("Shared AVD requires every existing instance to be read-only")
    env = dict(os.environ, ANDROID_AVD_HOME=str(CACHE / "avd"),
               ANDROID_HOME=str(CACHE / "android-sdk"))
    command = [str(EMULATOR), "-avd", "clasher_reference_api35", "-port", str(args.console_port),
               "-no-window", "-no-audio", "-no-snapshot", "-no-boot-anim",
               "-gpu", args.gpu, "-memory", "3072", "-cores", "2", "-grpc", str(args.grpc_port), "-grpc-use-token"]
    if args.read_only:
        command.append("-read-only")
    process = None
    if resume is not None:
        launch = json.loads((resume / "launch.json").read_text())
        pid = int(launch["pid"])
        running = subprocess.check_output(["ps", "-p", str(pid), "-o", "command="], text=True)
        if launch["command"] != command or "clasher_reference_api35" not in running:
            raise RuntimeError("Owned emulator identity changed")
    else:
        with (output / "emulator.log").open("wb") as target:
            process = subprocess.Popen(command, env=env, stdout=target,
                                       stderr=subprocess.STDOUT, start_new_session=True)
        pid = process.pid
    (output / "launch.json").write_text(json.dumps(
        {"pid": pid, "command": command, "avd_home": env["ANDROID_AVD_HOME"],
         "resumed_from": None if resume is None else str(resume)}, indent=2) + "\n")
    print(f"Using owned reference emulator PID {pid}", flush=True)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError("Reference emulator exited during startup")
        if adb("shell", "getprop", "sys.boot_completed", check=False).stdout.strip() == "1":
            break
        time.sleep(2)
    else:
        raise TimeoutError("Reference emulator boot deadline expired")
    adb("root")
    adb("wait-for-device")
    adb("shell", "svc", "wifi", "disable")
    adb("shell", "svc", "data", "disable")
    package = adb("shell", "dumpsys", "package", PACKAGE).stdout
    match = re.search(r"\b(?:userId|appId)=(\d+)\b", package)
    if match is None:
        raise RuntimeError("Cannot establish installed reference app UID")
    uid = match.group(1)
    for firewall in ("iptables", "ip6tables"):
        rule = ["OUTPUT", "-m", "owner", "--uid-owner", uid, "!", "-o", "lo", "-j", "REJECT"]
        if adb("shell", firewall, "-C", *rule, check=False).returncode:
            adb("shell", firewall, "-A", *rule)
        adb("shell", firewall, "-C", *rule)
    adb("shell", "am", "compat", "disable", "NATIVE_HEAP_POINTER_TAGGING", PACKAGE)
    adb("forward", f"tcp:{args.probe_port}", "tcp:26789")
    adb("shell", "am", "start", "-n", PACKAGE + "/com.supercell.clashroyale.GameApp")
    sys.path.insert(0, str(ROOT / "scripts"))
    from smoke_reference_battle import request

    print("Reference app launched with network isolation; checking attestation", flush=True)
    deadline = time.monotonic() + 120
    last_error = None
    while time.monotonic() < deadline:
        try:
            attestation = request(args.probe_port, "attest")
            if attestation.get("attestation", {}).get("production_ready") is not True:
                last_error = "runtime content is still warming up"
                time.sleep(2)
                continue
            break
        except (OSError, ValueError) as error:
            last_error = str(error)
            time.sleep(2)
    else:
        raise RuntimeError(f"Reference probe unavailable: {last_error}")
    digest = hashlib.sha256(json.dumps(attestation, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    (output / "attestation.json").write_text(json.dumps(attestation, indent=2) + "\n")
    if digest != EXPECTED_ATTESTATION:
        raise ValueError("Live attestation differs from pinned reference")
    config = json.loads((CAPTURE / "plan.json").read_text())["config"]
    configured = request(args.probe_port, "configure " + json.dumps(config, separators=(",", ":")))
    status = request(args.probe_port, "status")
    (output / "status.json").write_text(json.dumps(status, indent=2) + "\n")
    if status.get("ready") is not True or status.get("paused") is not True:
        raise RuntimeError("Configured reference is not ready and paused")
    (output / "complete.json").write_text(json.dumps({
        "pid": pid, "app_uid": int(uid), "attestation_sha256": digest,
        "serial": serial, "probe_port": args.probe_port, "read_only_avd": args.read_only, "grpc_port": args.grpc_port,
        "configured": configured, "status": "ready_paused_development_only",
        "cloud_resources": False, "policy_training": False,
    }, indent=2) + "\n")
    print("Pinned reference ready and paused for development study", flush=True)


if __name__ == "__main__":
    main()
