"""Build and sign a task-local, single-engine reference APK from staged sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import shutil
import subprocess
import zipfile
from pathlib import Path


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--engine-pin", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cache = args.cache.resolve()
    stage = cache / "apk-probe-stage-1e505767"
    java = Path("/opt/homebrew/opt/openjdk@17/bin/java")
    tools = cache / "android-sdk/build-tools/35.0.0"
    apktool = cache / "apktool_2.12.1.jar"
    pin = json.loads(args.engine_pin.read_text())
    if (
        digest(apktool)
        != "66cf4524a4a45a7f56567d08b2c9b6ec237bcdd78cee69fd4a59c8a0243aeafa"
    ):
        raise ValueError("apktool identity mismatch")
    if digest(stage / "lib/arm64-v8a/libg.so") != pin["libg_sha256"]:
        raise ValueError("staged engine identity mismatch")
    args.output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(args.probe, stage / "lib/arm64-v8a/libcrprobe.so")
    keys = cache / "local-build-signing"
    keys.mkdir(mode=0o700, exist_ok=True)
    password = keys / "password"
    keystore = keys / "reference.keystore"
    if keystore.exists() != password.exists():
        raise ValueError("incomplete signing material")
    log = args.output / "build.log"

    def run(command):
        with log.open("a") as output:
            subprocess.run(
                list(map(str, command)),
                check=True,
                stdout=output,
                stderr=subprocess.STDOUT,
            )

    if not keystore.exists():
        with password.open("x") as target:
            password.chmod(0o600)
            target.write(secrets.token_hex(32))
        run(
            [
                java.parent / "keytool",
                "-genkeypair",
                "-keystore",
                keystore,
                "-storepass:file",
                password,
                "-keypass:file",
                password,
                "-alias",
                "clasher-reference",
                "-keyalg",
                "RSA",
                "-keysize",
                "2048",
                "-validity",
                "3650",
                "-dname",
                "CN=Clasher Local Reference",
                "-noprompt",
            ]
        )
        keystore.chmod(0o600)
    unsigned = args.output / "unsigned.apk"
    aligned = args.output / "aligned.apk"
    signed = args.output / "reference.apk"
    run([java, "-jar", apktool, "build", stage, "--jobs", "2", "--output", unsigned])
    run([tools / "zipalign", "-P", "16", "-f", "4", unsigned, aligned])
    run(
        [
            java,
            "-jar",
            tools / "lib/apksigner.jar",
            "sign",
            "--ks",
            keystore,
            "--ks-key-alias",
            "clasher-reference",
            "--ks-pass",
            f"file:{password}",
            "--out",
            signed,
            aligned,
        ]
    )
    run([java, "-jar", tools / "lib/apksigner.jar", "verify", "--verbose", signed])
    with zipfile.ZipFile(signed) as archive:
        for name, expected in (
            ("lib/arm64-v8a/libg.so", pin["libg_sha256"]),
            ("lib/arm64-v8a/libcrprobe.so", digest(args.probe)),
        ):
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError("packaged native library identity mismatch")
    receipt = {
        "status": "signed_and_payload_verified_not_runtime_tested",
        "output": str(signed),
        "sha256": digest(signed),
        "probe_sha256": digest(args.probe),
        "engine_sha256": pin["libg_sha256"],
        "outer_apk_variant": "publisher-1e505767",
        "upstream_exact_apk_claimed": False,
        "signing": "task-local key; not publisher signature",
        "mode": "single GameApp engine",
    }
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
