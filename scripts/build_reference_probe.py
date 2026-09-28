"""Cross-compile the pinned reference probe for an Android ARM64 guest."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path


def sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--ndk", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.source_manifest.read_text())
    source_root = Path(manifest["root"]).resolve()
    for record in manifest["files"]:
        path = (source_root / record["path"]).resolve()
        if not path.is_relative_to(source_root) or sha256(path) != record["sha256"]:
            raise ValueError("probe source differs from pinned manifest")
    host = {"Darwin": "darwin-x86_64", "Linux": "linux-x86_64"}[platform.system()]
    toolchain = args.ndk / "toolchains/llvm/prebuilt" / host / "bin"
    compiler = toolchain / "aarch64-linux-android24-clang++"
    if not compiler.is_file():
        raise FileNotFoundError(compiler)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir / "libcrprobe.so"
    sources = [
        source_root / "native_runner/probe" / filename
        for filename in (
            "cr_replay_probe.cpp",
            "native_touch_interceptor.cpp",
            "native_call_arm64.S",
            "remaining_runtime_arm64.S",
        )
    ]
    command = [
        str(compiler),
        "-std=c++17",
        "-O2",
        "-fPIC",
        "-fvisibility=hidden",
        "-Wall",
        "-Wextra",
        "-shared",
        "-Wl,-z,max-page-size=16384",
        "-o",
        str(output),
        *map(str, sources),
        "-llog",
        "-ldl",
        "-lz",
    ]
    with (args.output_dir / "build.log").open("w") as log:
        result = subprocess.run(
            command, stdout=log, stderr=subprocess.STDOUT, check=False
        )
    receipt = {
        "source_commit": manifest["commit"],
        "command": command,
        "source_manifest_sha256": sha256(args.source_manifest),
        "exit_code": result.returncode,
        "runtime_tested": False,
    }
    if result.returncode == 0:
        receipt["probe_sha256"] = sha256(output)
        receipt["bytes"] = output.stat().st_size
        details = subprocess.run(
            [str(toolchain / "llvm-readelf"), "-h", "-l", str(output)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        (args.output_dir / "elf.txt").write_text(details)
    (args.output_dir / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
