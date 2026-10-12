#!/usr/bin/env python3
"""No-copy Mac staging (TIERS Amendment 4; coordinator 22:31Z ruling and 22:30:53Z scope message): the frozen prepare_bundle, no data copy.

Why a runtime substitution: ``prepare_bundle.py`` (a1c59fa3) is in every bundle's
``measurement_files`` (END-A3 manifests 01/08; fleet_pool binds them across hosts),
so its bytes cannot change. It also cannot accept pre-placed files: it creates
``--output`` with ``exist_ok=False`` and ``copy_file`` refuses an existing
destination. This helper therefore imports the UNMODIFIED frozen module from the
reviewed e4v3 directory and replaces only its module-level ``copy_file`` for the
bundle's three fixture files (``states.pkl``, ``states-rows.json``,
``states-rows.bin``). Every other file goes through the frozen ``copy_file``, and
all manifest content is computed by the frozen code, so ``tiers-pins.json`` is
byte-identical to a plain ``prepare_bundle.py`` run on the same inputs.

Placement, in order, each SHA-256 verified against its source (fail closed):
  1. APFS clone (``clonefile(2)`` via libc; macOS only; copy-on-write, own inode);
  2. hard link (same filesystem);
  3. data copy, ONLY if free space after it stays >= 10 GiB; otherwise fail.

Before importing, the e4v3 directory's measurement_files (prepare_bundle's own formula)
must equal END-A3's exactly, so the frozen code that runs is the END code. This file
must live outside e4v3 (``measurement_files``) and outside ``--runtime-root``
(``runtime_files`` hashes every .py there); both are checked.
After placement, the source and bundle copies of the three files are made read-only
(chmod a-w; coordinator condition 3) and that is recorded. A receipt is written beside,
never inside, the bundle. Immediately before the Mac session, ``--verify-bundle``
re-hashes the three files (present, read-only, SHA-equal to the receipt and to
tiers-pins.json) and writes a timestamped verification receipt for the session receipt
(condition 5). Coordinator ruling at 23:04Z on 2026-10-11 (COORDINATOR 684195b3) approved this helper; no re-pins
hold only while nothing frozen changes (condition 6). Usage:
  stage_nocopy.py --e4v3 <reviewed e4v3 dir> -- <prepare_bundle.py arguments>
  stage_nocopy.py --verify-bundle <bundle dir>
"""
import ctypes
import ctypes.util
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import sys

FIXTURE = ("states.pkl", "states-rows.json", "states-rows.bin")
# END-A3 measurement_files (T1 END-A3-manifest-01-f6cebbaa.json, bd9804c3): every e4v3 .py/.sh + spec-pins.json.
FROZEN_MEASUREMENT_FILES = {
    "build_tiers.sh": "3656f88ecf80cd9aec83c94607dad44088e0b7fbb2d244d06d47c74561e45372",
    "classify_failure.py": "9ab2f0383c0eec1a4998a0f48406f43b681109a176cef339a3d80f5d1663cc47",
    "convert_states.py": "7ce306835410792534d9290e91001312d96babc8853925cd20b3ea7037520267",
    "corpus_contract.py": "e62b6df5f4ad245a92f39a4546329dc13b183e881c9a58757f6c4a0f9ac6880c",
    "fleet_end.py": "76d5ce317915b2c6364310e1bd6a513d7906ce13521029b9737c80e31cbd2260",
    "fleet_pool.py": "572ad68272694d4974bef474fb27f2efa5ba809abe92730326f4ef5e7032a252",
    "fleet_profile.py": "5e482f0adc43ec1ffb56a7fc271fbf93e3258b9704a7d2e32c15594c0249fc8a",
    "fleet_reference.py": "c767a6e063a3c50a171b370cb10868ed5e125b56b6289594cb4734363bcfa764",
    "fleet_validity.py": "0775b704905324d70f9a43bc580bcbba1548cb2d2a4835c84ff61a0d8b64ae0f",
    "measure_tiers.py": "6066228b89601d6cf29ff456e9dee4848fa59886f319ff38ebabd49e3c101f2e",
    "prepare_bundle.py": "a1c59fa3f9d546eaf212ef63fa3b3126bc039f4a86de384761832009e3cbe1bb",
    "prepare_fleet_smoke.py": "69190b46ff379b6f75cf38b47d10b5fcd551583e2255301f8a0466a282a0ab1f",
    "receipts.py": "839a43be635ca0de8db5f70f1a13459007a37f338e79ab6fef1fae43816460a6",
    "replay_load.py": "1d0e12cca4191c5f451619b667fe7c744de301f462ddf92ccad322304a019624",
    "spec-pins.json": "823d2e1de642e2c2621960f5aad85fc935b7f10947da3ed1b7acf6e5adb46c6f",
    "state_rows.py": "3899276bb99a8b29c6777cf8b476440bee1c1c493612a97539550d2e35bbf755",
    "telemetry.py": "808d6fab49304c12b98581e67a5150e87274db5eef137f6ce351346c31c7fd24",
    "tier_backend.py": "02e2139f9ddc6e795e8e102f278ccd5cc53363c55d8a90288b4715adb724ca1d",
}

HEADROOM_BYTES = 10 * 2**30  # Mac precondition: >= 10 GiB free after staging
PLACED = []


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def measurement_files(e4v3):
    """prepare_bundle's own measurement_files formula, for the e4v3 directory about to be imported."""
    return {p.name: sha(p) for p in sorted(Path(e4v3).iterdir()) if p.suffix in (".py", ".sh") or p.name == "spec-pins.json"}


def clonefile(source, destination):
    """macOS clonefile(2); raises OSError when the volume cannot clone. Never falls back to a copy."""
    libc = ctypes.CDLL(ctypes.util.find_library("c"), use_errno=True)
    function = libc.clonefile
    function.argtypes, function.restype = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32), ctypes.c_int
    if function(os.fsencode(source), os.fsencode(destination), 0) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(destination))


def place(source, destination, frozen_copy, bundle, system=None, disk_usage=shutil.disk_usage):
    """Clone / hard link / space-checked copy for the bundle's fixture files; the frozen copy for the rest."""
    destination = Path(destination)
    if destination.name not in FIXTURE or destination.parent.resolve() != Path(bundle).resolve():
        return frozen_copy(source, destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    expected, attempts, method = sha(source), [], None
    for name, action in ((("apfs-clone", clonefile),) if (system or platform.system()) == "Darwin" else ()) + (("hardlink", os.link),):
        try:
            action(source, destination)
            method = name
            break
        except OSError as failure:
            attempts.append("%s: %s" % (name, failure))
            if destination.exists():
                raise FileExistsError("Partial placement left behind: " + str(destination))
    if method is None:
        size, free = Path(source).stat().st_size, disk_usage(destination.parent).free
        if free - size < HEADROOM_BYTES:
            raise OSError("No-copy placement failed (%s) and a data copy would leave %d bytes free (< %d)"
                          % ("; ".join(attempts), free - size, HEADROOM_BYTES))
        frozen_copy(source, destination)
        method = "data-copy"
    actual = sha(destination)
    if actual != expected:
        raise ValueError("Placed fixture file differs from its source: " + str(destination))
    # Coordinator condition 3: source and bundle copies read-only (a hard link shares one inode).
    protected = [read_only(source), read_only(destination)]
    PLACED.append(dict(file=destination.name, method=method, source=str(Path(source).resolve()), sha256=actual,
                       bytes=destination.stat().st_size, failed_attempts=attempts, read_only=protected))


def read_only(path):
    """chmod a-w; returns the resulting octal mode (fails closed if any write bit remains)."""
    path = Path(path)
    os.chmod(path, stat.S_IMODE(path.stat().st_mode) & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
        raise PermissionError("Could not make read-only: " + str(path))
    return dict(path=str(path.resolve()), mode=oct(mode))


def verify_bundle(bundle):
    """Coordinator condition 5: immediately before the Mac session, re-verify the three placed files.

    Each must be present, read-only and SHA-equal to both the staging receipt and the bundle's
    tiers-pins.json ``files``. Writes a new, timestamped verification receipt beside the bundle
    and returns it; its content goes into the session receipt. Fails closed.
    """
    bundle = Path(bundle).resolve()
    staging = json.loads((bundle.parent / (bundle.name + ".nocopy-receipt.json")).read_text())
    manifest = json.loads((bundle / "tiers-pins.json").read_text())
    if staging["tiers_pins_sha256"] != sha(bundle / "tiers-pins.json"):
        raise ValueError("tiers-pins.json differs from the staging receipt")
    files = []
    for placed in staging["placed"]:
        path = bundle / placed["file"]
        actual = sha(path)
        mode = stat.S_IMODE(path.stat().st_mode)
        if actual != placed["sha256"] or actual != manifest["files"][placed["file"]]:
            raise ValueError("Staged fixture file changed: " + placed["file"])
        if mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
            raise PermissionError("Staged fixture file is writable again: " + placed["file"])
        files.append(dict(file=placed["file"], method=placed["method"], sha256=actual, mode=oct(mode)))
    if sorted(f["file"] for f in files) != sorted(FIXTURE):
        raise ValueError("Staging receipt does not cover the three fixture files")
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = dict(schema="clasher.tiers-a4.nocopy-session-verification.v1", utc=now, host=platform.node(),
                   helper_used=True, helper_sha256=sha(Path(__file__).resolve()),
                   staging_receipt_sha256=sha(bundle.parent / (bundle.name + ".nocopy-receipt.json")),
                   tiers_pins_sha256=staging["tiers_pins_sha256"], files=files, passes=True)
    target = bundle.parent / (bundle.name + ".nocopy-verify-" + now.replace(":", "") + ".json")
    with target.open("x") as stream:
        stream.write(json.dumps(receipt, sort_keys=True, indent=1) + "\n")
    return receipt


def inside(path, directory):
    try:
        Path(path).resolve().relative_to(Path(directory).resolve())
        return True
    except ValueError:
        return False


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) == 2 and argv[0] == "--verify-bundle":
        print(json.dumps(verify_bundle(argv[1]), sort_keys=True), flush=True)
        return
    if len(argv) < 3 or argv[0] != "--e4v3" or argv[2] != "--":
        raise SystemExit(__doc__)
    e4v3, arguments = Path(argv[1]).resolve(), argv[3:]
    for flag in ("--output", "--runtime-root"):
        if arguments.count(flag) != 1:
            raise SystemExit("prepare_bundle arguments need exactly one " + flag)
    bundle = Path(arguments[arguments.index("--output") + 1]).resolve()
    runtime = Path(arguments[arguments.index("--runtime-root") + 1]).resolve()
    here = Path(__file__).resolve()
    if inside(here, e4v3) or inside(here, runtime):
        raise SystemExit("stage_nocopy.py must live outside e4v3 and the runtime root (pinned file sets)")
    if measurement_files(e4v3) != FROZEN_MEASUREMENT_FILES:
        raise SystemExit("e4v3 measurement_files differ from END-A3 (prepare_bundle a1c59fa3 et al.)")
    sys.path.insert(0, str(e4v3))
    import prepare_bundle
    if Path(prepare_bundle.__file__).resolve() != e4v3 / "prepare_bundle.py":
        raise SystemExit("Imported a prepare_bundle other than the reviewed e4v3 file")
    frozen_copy = prepare_bundle.copy_file
    prepare_bundle.copy_file = lambda source, destination: place(source, destination, frozen_copy, bundle)
    sys.argv = [str(e4v3 / "prepare_bundle.py")] + arguments
    prepare_bundle.main()
    if sorted(p["file"] for p in PLACED) != sorted(FIXTURE):
        raise SystemExit("Expected the three fixture files to be placed by stage_nocopy: " + repr(PLACED))
    receipt = dict(schema="clasher.tiers-a4.nocopy-staging.v1",
                   utc=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   host=platform.node(), system=platform.system(), helper_sha256=sha(here),
                   prepare_bundle_sha256=sha(e4v3 / "prepare_bundle.py"), bundle=str(bundle),
                   tiers_pins_sha256=sha(bundle / "tiers-pins.json"), placed=PLACED,
                   free_bytes_after=shutil.disk_usage(bundle).free)
    target = bundle.parent / (bundle.name + ".nocopy-receipt.json")
    with target.open("x") as stream:
        stream.write(json.dumps(receipt, sort_keys=True, indent=1) + "\n")
    print(json.dumps(dict(receipt=str(target), placed=[(p["file"], p["method"]) for p in PLACED])), flush=True)


if __name__ == "__main__":
    main()
