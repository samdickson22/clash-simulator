"""Shared I/O for the TIERS Amendment 4 builder: pins, bootstrap, capture loading.

Every pickle is executed only after its SHA-256 matched a committed pin and after
the reviewed runtime bootstrap (e4v3 ``setup_imports``), as convert_states does.
"""
import datetime
import gzip
import hashlib
import json
import operator
import os
from pathlib import Path
import pickle
import sys

# TIERS Amendment 3 e4v3 bytes (END-A3 adopted pins; measure_tiers 6066228b unchanged).
E4V3_PINS = {
    "convert_states.py": "7ce306835410792534d9290e91001312d96babc8853925cd20b3ea7037520267",
    "corpus_contract.py": "e62b6df5f4ad245a92f39a4546329dc13b183e881c9a58757f6c4a0f9ac6880c",
    "receipts.py": "839a43be635ca0de8db5f70f1a13459007a37f338e79ab6fef1fae43816460a6",
    "tier_backend.py": "02e2139f9ddc6e795e8e102f278ccd5cc53363c55d8a90288b4715adb724ca1d",
    "state_rows.py": "3899276bb99a8b29c6777cf8b476440bee1c1c493612a97539550d2e35bbf755",
    "measure_tiers.py": "6066228b89601d6cf29ff456e9dee4848fa59886f319ff38ebabd49e3c101f2e",
    "prepare_bundle.py": "a1c59fa3f9d546eaf212ef63fa3b3126bc039f4a86de384761832009e3cbe1bb",
}
E4V3_REL = "reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3"
# T1's committed END-A3 manifest for 01 (reports/explore/t1/receipts/END-A3-manifest-01-f6cebbaa.json).
END_MANIFEST_SHA256 = "bd9804c32a6ba661f18f124f63a47bb99e6f653c3ea48bb4a7c0947e2f7747e7"
NATIVE_SHA256 = "44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2"  # tier_backend.NATIVE_SHA
# TIERS Amendment 5 (COORDINATOR 46ab6923, main 8799a0d6): T1's committed END-A5 inventory diff
# (reports/explore/t1/receipts/END-A5-runtime-manifest-inventory-diff.json): END-A5 = END-A3 with only
# e4v3/fleet_validity.py changed, in both runtime_files and measurement_files.
END_A5_DIFF_SHA256 = "900bae16afeafeccd990109d23057a6f263f43a999b18e1a0e9b687b38afd69f"
FLEET_VALIDITY_REL = E4V3_REL + "/fleet_validity.py"
CORPORA_SHA256 = "3501e2acf444c2f23a5ed9f9471ebcabfc66216b412847c033759c3f4b2cde13"  # T1 corpora.json
PUBLIC_SHA256 = "282b08770d9a16b8e39b354551d62f934e7103dec769a00c511fb0b96260351e"  # T1 public 1,200
GOLDEN_SHA256 = "8b188918b95cf6c79f0db0639beaff2e80526ce11c146cdfe0edb0bb8e6f3cce"  # golden125
END_FINGERPRINT = "c09142b97ecc147efa635036a69508e16fe647347749e052d321048910040901"
END_ROWS = 1325
CORPUS_SEED_BASE = 4503603407370496
TIERS = ("K0c", "S", "K2", "K4")
HERE = Path(__file__).resolve().parent
E4V3_DIR = None  # set by add_e4v3


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def process_identity():
    import platform
    return dict(host=platform.node(), nice=os.getpriority(os.PRIO_PROCESS, 0), cpus=sorted(os.sched_getaffinity(0)),
                python=platform.python_version())


def require_low_priority():
    """Shared lab host: nice 19 on exactly one core (05 rule)."""
    if os.getpriority(os.PRIO_PROCESS, 0) != 19 or len(os.sched_getaffinity(0)) != 1:
        raise ValueError("Run under nice -n 19 taskset -c <one core>")
    if any(os.environ.get(k) != "1" for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")):
        raise ValueError("Set OMP/OPENBLAS/MKL_NUM_THREADS=1")


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def read_pinned_json(path, expected):
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("Pin mismatch: " + str(path))
    return json.loads(data)


def write_json(path, value):
    """Never overwrites; canonical key order."""
    with Path(path).open("x") as stream:
        stream.write(json.dumps(value, sort_keys=True, indent=1) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return file_sha(path)


def add_e4v3(directory, pins=E4V3_PINS):
    """Put the reviewed e4v3 package on sys.path after checking its pinned bytes."""
    global E4V3_DIR
    directory = Path(directory).resolve()
    for name, expected in pins.items():
        if file_sha(directory / name) != expected:
            raise ValueError("e4v3 pin mismatch: " + name)
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    E4V3_DIR = directory
    return {name: pins[name] for name in sorted(pins)}


E4V3_MODULES = ("receipts", "corpus_contract", "state_rows", "convert_states", "tier_backend")


def prepare_imports(extra_paths=()):
    """Import the reviewed e4v3 modules (must resolve to the pinned directory), then add
    the inherited runtime paths. No runtime bootstrap: TierBackend runs setup_imports itself,
    and setup_imports may run only once per interpreter (torch interop threads)."""
    import importlib
    if E4V3_DIR is None:
        raise ValueError("add_e4v3 must run before imports")
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 100000))
    for name in E4V3_MODULES:
        importlib.import_module(name)
    check_e4v3_modules()
    sys.path[:0] = [str(p) for p in extra_paths]


def bootstrap(runtime_root, native, extra_paths=()):
    """convert_states' bootstrap for processes that build no TierBackend: once, then check."""
    prepare_imports(extra_paths)
    from tier_backend import setup_imports
    setup_imports(runtime_root, native)
    check_e4v3_modules()


def a5_expected(manifest, diff):
    """END-A5 pins: the END-A3 manifest with exactly the fleet_validity entry replaced, as T1's
    committed inventory diff certifies (fail closed on any other difference)."""
    if diff.get("status") != "ADOPTED" or diff.get("A5_adopted") is not True or diff.get("adopted_commit") != "8799a0d6" \
            or diff["A3_runtime_3785_diff_entries"] != [FLEET_VALIDITY_REL] \
            or diff["measurement_files18_diff_entries"] != ["fleet_validity.py"] or diff["native_unchanged"] != NATIVE_SHA256[:8]:
        raise ValueError("END-A5 inventory diff is not the adopted single-file fleet_validity change")
    fleet_validity = diff["fleet_validity_sha256"]
    runtime = dict(manifest["runtime_files"])
    if FLEET_VALIDITY_REL not in runtime or len(runtime) != 3785:
        raise ValueError("END-A3 runtime_files lack the fleet_validity entry")
    runtime[FLEET_VALIDITY_REL] = fleet_validity
    measurement = dict(manifest["measurement_files"], **{"fleet_validity.py": fleet_validity})
    if measurement != diff["full_18_inventory"]:
        raise ValueError("END-A5 measurement inventory differs from END-A3 + fleet_validity")
    return runtime, measurement


def verify_runtime(runtime_root, native, end_manifest, end_a5_diff):
    """END-A5 binding (fail closed; TIERS A5, A4 erratum E3): the frozen runtime_pins of
    ``runtime_root`` and the e4v3 measurement_files equal T1's committed END-A3 manifest with
    only fleet_validity.py replaced per T1's committed END-A5 inventory diff; e4v3 is the
    runtime's own package; the native module is the frozen provenance build."""
    root = Path(runtime_root).resolve()
    if E4V3_DIR != root / E4V3_REL:
        raise ValueError("e4v3 must be the END-A5 runtime's own package")
    runtime_expected, measurement_expected = a5_expected(read_pinned_json(end_manifest, END_MANIFEST_SHA256),
                                                         read_pinned_json(end_a5_diff, END_A5_DIFF_SHA256))
    from prepare_bundle import runtime_pins
    if runtime_pins(root) != runtime_expected:
        raise ValueError("Runtime differs from the END-A5 runtime_files")
    measurement = {p.name: file_sha(p) for p in sorted(E4V3_DIR.iterdir())
                   if p.suffix in (".py", ".sh") or p.name == "spec-pins.json"}
    if measurement != measurement_expected:
        raise ValueError("e4v3 measurement_files differ from END-A5")
    if file_sha(native) != NATIVE_SHA256:
        raise ValueError("Native module is not the frozen provenance build")
    return dict(end_manifest_sha256=END_MANIFEST_SHA256, end_a5_diff_sha256=END_A5_DIFF_SHA256,
                fleet_validity_sha256=measurement_expected["fleet_validity.py"], runtime_files=len(runtime_expected),
                runtime_files_equal=True, measurement_files_equal=True, native_sha256=NATIVE_SHA256)


def runtime_arguments(parser):
    """Common runtime arguments; e4v3 is the END-A3 runtime's own package."""
    parser.add_argument("--runtime-root", type=Path, required=True, help="END-A3-equal runtime (build_runtime.sh)")
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--extra-path", type=Path, action="append", default=[])
    parser.add_argument("--end-manifest", type=Path, required=True, help="T1 END-A3-manifest-01-f6cebbaa.json (bd9804c3)")
    parser.add_argument("--end-a5-diff", type=Path, required=True, help="T1 END-A5-runtime-manifest-inventory-diff.json (900bae16)")
    parser.add_argument("--e4v3", type=Path, help="defaults to <runtime-root>/" + E4V3_REL)


def setup_runtime(args, bootstrap_runtime=True):
    """Pins, END-A3 runtime binding, then imports. A process that will construct a
    TierBackend passes bootstrap_runtime=False: the backend runs setup_imports once."""
    pins = add_e4v3(args.e4v3 or Path(args.runtime_root) / E4V3_REL)
    binding = verify_runtime(args.runtime_root, args.native, args.end_manifest, args.end_a5_diff)
    if bootstrap_runtime:
        bootstrap(args.runtime_root, args.native, args.extra_path)
    else:
        prepare_imports(args.extra_path)
    return pins, binding


def runtime_versions():
    import platform
    versions = dict(python=platform.python_version())
    for name in ("numpy", "torch"):
        if name in sys.modules:
            versions[name] = sys.modules[name].__version__
    return versions


def check_e4v3_modules():
    """Every reviewed module in use is the pinned file."""
    for name in E4V3_MODULES + tuple(n for n in ("prepare_bundle",) if n in sys.modules):
        if Path(sys.modules[name].__file__).resolve() != E4V3_DIR / (name + ".py"):
            raise ValueError("e4v3 module shadowed: " + name)


def end_digests(path, expected_sha256):
    """The committed END index digests (Amendment 3 receipt); fingerprint must be c09142b9."""
    from convert_states import fingerprint
    receipt = read_pinned_json(path, expected_sha256)
    rows = [dict(id=r["id"], canonical_sha256=r["canonical_sha256"]) for r in receipt["rows"]]
    if len(rows) != END_ROWS or fingerprint(rows) != END_FINGERPRINT or receipt["fixture_canonical_fingerprint"] != END_FINGERPRINT:
        raise ValueError("END digest receipt is not the reviewed c09142b9 fixture")
    return rows


def capture_inventory(corpora, captures):
    """The 32 capture files corpora.json pins, mapped to the local copy (tier, seed, sha)."""
    files = []
    for tier in TIERS:
        listed = corpora["tiers"][tier]["source_capture_shas"]
        if len(listed) != 8:
            raise ValueError("Expected 8 captures for " + tier)
        for source, digest in sorted(listed.items()):
            parts = Path(source).parts
            game, name = parts[-2], parts[-1]
            prefix = "corpus-" + tier + "-"
            if name != "capture.pkl.gz" or not game.startswith(prefix):
                raise ValueError("Unexpected capture path: " + source)
            index = int(game[len(prefix):])
            if index in (0, 1, 2) or not 0 <= index < 64:
                raise ValueError("Capture outside the audited corpus indices: " + source)
            files.append(dict(tier=tier, index=index, seed=CORPUS_SEED_BASE + index, source=source,
                              local=str(Path(captures) / game / name), relative=game + "/" + name, sha256=digest))
    if len(files) != 32 or len({(f["tier"], f["seed"]) for f in files}) != 32:
        raise ValueError("Expected 32 distinct capture games")
    return files


def load_capture(entry):
    """SHA-verify, then unpickle one capture (dict(counts, rows, health))."""
    if file_sha(entry["local"]) != entry["sha256"]:
        raise ValueError("Capture SHA mismatch: " + entry["relative"])
    with gzip.open(entry["local"], "rb") as stream:
        capture = pickle.load(stream)
    if set(capture) != {"counts", "rows", "health"}:
        raise ValueError("Unexpected capture layout: " + entry["relative"])
    return capture


def capture_rows(capture):
    """All retained rows of one capture, in (stratum, priority) order."""
    for stratum in sorted(capture["rows"]):
        for _, row in capture["rows"][stratum]:
            yield row


def row_identity(row, entry):
    """Fail closed unless the row's identity matches its capture file."""
    tick = operator.index(row["info"].tick)
    if tick < 0 or row.get("tier") != entry["tier"] or row.get("seed") != entry["seed"] or \
            row.get("id") != "%s-200/%d/%d" % (entry["tier"], entry["seed"], tick):
        raise ValueError("Capture row identity differs from its file: " + repr(row.get("id")))
    return tick


def sets_sha256(sets):
    return hashlib.sha256(json.dumps(sets, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_artifacts(expected):
    """{path: sha256} must match the current bytes (fail closed)."""
    for path, digest in expected.items():
        if file_sha(path) != digest:
            raise ValueError("Artifact changed since its stage receipt: " + str(path))


def work_bundle(directory, states, state_rows, sets, v1, student):
    """Offline Mac-profile bundle for TierBackend (never staged): hard links plus a minimal manifest.

    TierBackend reads only ``profile``, ``sets`` and the pinned state files; the frozen
    v1/R3a SHAs are checked here as validate_bundle would.
    """
    from state_rows import CONTAINER, INDEX
    from tier_backend import STUDENT_SHA, THRESHOLD, V1_SHA
    directory = Path(directory)
    directory.mkdir(parents=True)
    os.link(states, directory / "states.pkl")
    for name in (INDEX, CONTAINER):
        os.link(Path(state_rows) / name, directory / name)
    for source, name, expected in ((v1, "v1.pt", V1_SHA), (student, "R3a.pt", STUDENT_SHA)):
        if file_sha(source) != expected:
            raise ValueError("Wrong frozen policy: " + name)
        os.symlink(Path(source).resolve(), directory / name)
    files = {name: file_sha(directory / name) for name in ("states.pkl", INDEX, CONTAINER, "v1.pt", "R3a.pt")}
    manifest = dict(schema="clasher.e4v3.inputs.v1", final=False, profile="mac-preregistered", threshold=THRESHOLD,
                    sets=sets, files=files, note="offline TIERS Amendment 4 builder bundle on Linux; not a Mac bundle")
    write_json(directory / "tiers-pins.json", manifest)
    return manifest


def memory_status(pid="self"):
    fields = {}
    for line in Path("/proc/%s/status" % pid).read_text().splitlines():
        key, _, value = line.partition(":")
        if key in ("VmRSS", "VmHWM", "RssAnon", "RssFile", "RssShmem"):
            fields[key] = int(value.split()[0]) * 1024
    return fields
