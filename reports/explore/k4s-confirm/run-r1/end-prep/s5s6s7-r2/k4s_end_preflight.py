"""K4S END on-host PREFLIGHT (S5 candidate r2, RC-2 / P2-3). Non-claiming, non-timing. Never launches games.

r2: every read, hash, stat, open, write, subprocess and git call goes through the pinned safe_input layer
(ruling P2-1/P2-4), loaded from this directory only after its SHA-256 and constants fingerprint match.

Runs on 127x03/127x04 from the final runtime export, a per-preflight bundle (the attempt bundle except
``reference_load_profile.guard.job``) and the preflight's OWN fresh ``k4s-end-guard-r1-pfNN`` guard job. In order:

  before any runtime module is imported (stdlib + safe_input only)
    layout            every path argument equals the declared k4s-end-r1 layout (si.END_BASES, Q4 guard parent)
    bundle_stamp      bundle tiers-pins.json read with its pinned SHA; S4 test-only stamps refused
    guard_repo        frozen-reader ruling: the guard job's repo/ verified through safe_input, then Q3
                      ``git cat-file -e`` of b2f9e25e and ce042b97 (si.git_run)
    repository_clone  the --repository clone verified the same way
    frozen_git_env    global git config checked; inherited GIT_* scrubbed; P2-4 git environment set
    pre_import_pins   the K4S manifest of record (FIXED constant 74314eda, never caller-supplied) and every file of
                      its frozen closure (k4s_files, end_files, reused_readonly, k4s_kernel.files, SD1 manifest),
                      each read through safe_input with its pinned SHA-256
    frozen_import     end_reference, end_background; every loaded runtime module must be a verified closure file
  then end_reference.reference() order, except the claim and the measurement (r1 table, README §S5)
    frozen_helpers .. post_pins, cleanup; NEVER pool_context / producer_claim / K4SStore(REFERENCE_SCOPE) / measure()

Output: one fresh directory <base>/preflight/<job>/<job> created exclusively through safe_input and sealed with
scope K4S-END-PREFLIGHT. preflight-result.json exports the mode (binding | diagnostic), the load (reference-slot
work, background slots), the duration (requested and measured loaded seconds), the loaded cumulative bus % and its
P2-3 band (proceed <= 0.3 %, coordinator-decision, stop >= 0.7 %, unavailable). A background-only run
(--no-reference-work) is a NON-QUALIFYING diagnostic. It never writes under the attempt parent or the registry.

  nice -n 10 python -B k4s_end_preflight.py run --bundle B --bundle-pins-sha256 S --runtime-root R --native N \
      --corpus C --corpus-inventory CI --corpus-inventory-sha256 S --k4s-manifest-sha256 74314eda... \
      --sd1-manifest-sha256 S --end-evidence E --end-evidence-sha256 S --repository REPO --attempt-parent AP \
      --compare-bundle ATTEMPT_BUNDLE --compare-bundle-pins-sha256 S --hold-seconds 960 --out JOB/JOB
  python3 -I k4s_end_preflight.py verify-received --receive RECEIVE_DIR     (05 only)
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import traceback
import types
from pathlib import Path
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
SAFE_INPUT_SHA256 = "806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00"
SAFE_INPUT_FINGERPRINT = "33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592"
HOST_TOOL_SHA256 = "cf19269071d57f0d1fe9b7ce5f865b4641ecda62c88e418cd73b711a57a5d6f3"
SCHEMA = "clasher.k4s.end-preflight.v2"
VERIFIED_SCHEMA = "clasher.k4s.end-preflight-verified.v2"
SCOPE = "K4S-END-PREFLIGHT"
STUDY_REL = "reports/explore/k4s-confirm"
HOSTS = ("127x03", "127x04")
MIN_SAMPLES = 60
MIN_HOLD_SECONDS = {"127x03": 120, "127x04": 900}         # requested hold (03 >= 2 min; 04 RC-2 >= 15 min)
MIN_LOADED_SECONDS = {"127x03": 60, "127x04": 900}        # measured loaded guard span for a BINDING run (P2-3)
BUS_PROCEED_MAX, BUS_STOP_MIN = 0.3, 0.7                  # P2-3: <= 0.3 proceed; >= 0.7 STOP; between: coordinator
WINDOWS_SECONDS = (1, 10, 30, 60, 300)
BLOCK_SECONDS_RANGE = (1, 300)
GUARD_SIDE_FILES = ("allowlist-occurrences.jsonl", "op2-confirmations.jsonl", "ssh-family-occurrences.jsonl",
                    "parent-source-seed-admission.json")    # fleet_reference.py:219
HOLD_PHASE = "preflight-hold"
RECEIVE_BASE = "/mpac/sdicks02/k4s-runner/run-r1/preflight-received"
RECEIVE_NAMES = ("exit.json", "TRANSFER-DONE.json", "argv.nul", "detach.json", "detach.log")
SEAL_FILES = ("receipt-manifest.json", "receipt-manifest.sha256")
PREFLIGHT_NAME = re.compile(r"preflight-(127x0[34])-l([0-9]{2})")
BUNDLE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
RUNTIME_NAME = re.compile(r"runtime-[0-9a-f]{12}")
SYNTHETIC_KEY = "k4s_s4_synthetic"                        # assemble_fleet_reference.py:836-837 (S10-F4 / S5-F2)
BUNDLE_FILES = ("tiers-pins.json", "tiers-pins.sha256", "assembly-receipt.json")
ASSEMBLY_SCHEMA = "clasher.k4s.end-fleet-reference-assembly.v2"
CORPUS_INVENTORY_REL = "reports/explore/t1/corpora/corpus-03-a51ea64c/corpora.json"   # K4S manifest corpus.inventory
SEED_COMMITS = ("b2f9e25e1002d43cc910a4bb476716cc4cd32623",   # FROZEN-T1 parent_source_seeds (03; 08 join)
                "ce042b9775f80cb495c327b14a4712730ae95c85")   # coordinator 15:41Z Q3: git cat-file -e first
MANIFEST_REL = STUDY_REL + "/mac/K4S-MAC-MANIFEST.json"
K4S_MANIFEST_SHA256 = "74314eda04a7100d7ce10141394282b646723d29d0e7bb3883355d1ef1db6357"   # S5-F1: fixed anchor
END_SOURCES = (STUDY_REL + "/end_reference.py", STUDY_REL + "/end_pool.py", STUDY_REL + "/end_background.py",
               STUDY_REL + "/end_evidence.py", STUDY_REL + "/mac/k4s_backend.py", STUDY_REL + "/mac/k4s_logic.py")
# The frozen closure of 74314eda (k4s_files + end_files + reused_readonly + k4s_kernel.files + the SD1 manifest):
# exactly what k4s_logic.load_k4s_manifest (k4s_logic.py:131-157) verifies, as code constants. pre_import_pins checks
# that the anchored manifest yields exactly this table, then hashes every file through safe_input before any import.
FROZEN_CLOSURE = {
    'reports/explore/e1/planner.py': '4f608829289acfb4130f8f2022fd1f0d61755209e20230d1432595eec4c08bd6',
    'reports/explore/k4s-confirm/SD1-MANIFEST.json': 'b8ce7b4c088e275894b9654a85923aacf428656e71433f60ec32bed1ae63ef76',
    'reports/explore/k4s-confirm/anchor_x.py': 'cf528473278d4fbf9ffd8aecfd4a3350fe1dbb6bbeb0d441870c9f88bad3ec98',
    'reports/explore/k4s-confirm/end_background.py': 'a872bd2d810161d82467075567439d8000817eaa1c1082d00a73d4a5b008e839',
    'reports/explore/k4s-confirm/end_evidence.py': '6337e4bc2dbfeaf8a5303ac107e0e74174643aa88898dbdf610365dea131c61e',
    'reports/explore/k4s-confirm/end_pool.py': '069c22e7d68e1488291873c6c2d9e87cb1daf328fbe8bf254415d1fc2af06da2',
    'reports/explore/k4s-confirm/end_reference.py': '5cb4751e97436dc1208d5a6d6ab7e46c31a31b4ce53ab1d0d289fc4815f96fa9',
    'reports/explore/k4s-confirm/mac/K4S-MAC-PROCEDURE.md': '1b747d945c7a34bd91dc8b246a45b503f0547c6186db104984903ca5640bb9b0',
    'reports/explore/k4s-confirm/mac/build_manifest.py': '2e255fb939c2b1720749a8a38e99a4a66e397f1149f4d63f7a24d62cb82343f7',
    'reports/explore/k4s-confirm/mac/classify_k4s_failure.py': 'ac8aca3e9ee426561b3869d366751b662e91a7136c71a0fb279decc33f6f1600',
    'reports/explore/k4s-confirm/mac/k4s_backend.py': '8c8da476109e0b8390a9db8f91a8711644619172e7dbf78ca20d444c13f35954',
    'reports/explore/k4s-confirm/mac/k4s_logic.py': '2e4d7a5ce5363a9778eb088be7487d5f1ef7291706f743e9dd4c7c65ee5d4864',
    'reports/explore/k4s-confirm/mac/measure_k4s.py': 'c9d874b0362fff099dbe97d50605e693e9b0476ef54032b9d6744fa382a9a4c8',
    'reports/explore/k4s-confirm/mac/test_measure_k4s.py': 'edd6956bd96f0ab2dcffef874ddcedd41d4a0a926a10a6851c82c14beeda5da8',
    'reports/explore/k4s-confirm/sdefault.py': '0448db50afffb583c69d69a84218aed6f4413e514188ac086b7cd1631a67fa8e',
    'reports/explore/s1/anchor.py': '75a1b7d7fb7f144bfa62cdfcd3ddfdfe7cad7dc31e8e97dc4d4f4c7ede196888',
    'reports/explore/s1/cached_policy.py': '559ad75c0d9c971518fbcbab560c9d149f231045e79741da6394d49e403415fe',
    'reports/explore/s1/gc_window.py': '0c743f3d1e9c617a89625c694df216a93c4da15249b9c1398162ac1b73815146',
    'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/classify_failure.py': '9ab2f0383c0eec1a4998a0f48406f43b681109a176cef339a3d80f5d1663cc47',
    'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/corpus_contract.py': 'e62b6df5f4ad245a92f39a4546329dc13b183e881c9a58757f6c4a0f9ac6880c',
    'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/fleet_end.py': '76d5ce317915b2c6364310e1bd6a513d7906ce13521029b9737c80e31cbd2260',
    'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/fleet_pool.py': '572ad68272694d4974bef474fb27f2efa5ba809abe92730326f4ef5e7032a252',
    'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/fleet_profile.py': '5e482f0adc43ec1ffb56a7fc271fbf93e3258b9704a7d2e32c15594c0249fc8a',
    'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/fleet_reference.py': 'c767a6e063a3c50a171b370cb10868ed5e125b56b6289594cb4734363bcfa764',
    'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/fleet_validity.py': '0775b704905324d70f9a43bc580bcbba1548cb2d2a4835c84ff61a0d8b64ae0f',
    'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/measure_tiers.py': '6066228b89601d6cf29ff456e9dee4848fa59886f319ff38ebabd49e3c101f2e',
    'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/receipts.py': '839a43be635ca0de8db5f70f1a13459007a37f338e79ab6fef1fae43816460a6',
    'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/replay_load.py': '1d0e12cca4191c5f451619b667fe7c744de301f462ddf92ccad322304a019624',
    'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/spec-pins.json': '823d2e1de642e2c2621960f5aad85fc935b7f10947da3ed1b7acf6e5adb46c6f',
    'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/state_rows.py': '3899276bb99a8b29c6777cf8b476440bee1c1c493612a97539550d2e35bbf755',
    'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/telemetry.py': '808d6fab49304c12b98581e67a5150e87274db5eef137f6ce351346c31c7fd24',
    'reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3/tier_backend.py': '02e2139f9ddc6e795e8e102f278ccd5cc53363c55d8a90288b4715adb724ca1d',
}


class PreflightRefusal(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PreflightRefusal(message)


def iso(t=None):
    t = time.time() if t is None else t
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".%03dZ" % int((t % 1) * 1000)


def canonical(value):                                       # = k4s_logic.canonical (k4s_logic.py:106-107)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


# ---------------------------------------------------------------- pinned layers (stdlib bootstrap, then safe_input)

def read_pinned(path, sha256, cap=1 << 23):
    """Bootstrap read before safe_input exists: canonical path, O_NOFOLLOW, regular, st_nlink 1, cap, exact size,
    SHA-256 equal to the pin (same rule as k4s_end_host_tool.read_pinned)."""
    import stat
    require(path.startswith("/") and not path.startswith("//") and os.path.realpath(path) == path,
            "pinned file path is not canonical: " + path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        st = os.fstat(fd)
        require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size <= cap,
                "pinned file is not a single-link regular file within the cap: " + path)
        chunks, left = [], st.st_size
        while left:
            chunk = os.read(fd, min(left, 1 << 20))
            require(chunk, "pinned file shrank: " + path)
            chunks.append(chunk)
            left -= len(chunk)
        require(not os.read(fd, 1), "pinned file grew: " + path)
    finally:
        os.close(fd)
    data = b"".join(chunks)
    require(hashlib.sha256(data).hexdigest() == sha256, "pinned file SHA-256 mismatch: " + path)
    return data


def load_module(name, path, sha256):
    module = types.ModuleType(name)
    module.__file__ = path
    exec(compile(read_pinned(path, sha256), path, "exec"), module.__dict__)
    return module


def load_layers(directory=HERE):
    """(safe_input, k4s_end_host_tool), both SHA-pinned; the host tool reuses this safe_input module."""
    si = load_module("safe_input", os.path.join(directory, "safe_input.py"), SAFE_INPUT_SHA256)
    require(si.constants_fingerprint() == SAFE_INPUT_FINGERPRINT, "safe_input constants fingerprint differs")
    tool = load_module("k4s_end_host_tool", os.path.join(directory, "k4s_end_host_tool.py"), HOST_TOOL_SHA256)
    tool.check_safe_input(si)
    return si, tool


# ---------------------------------------------------------------- check ledger

class Checks:
    """Ordered check records; every check has UTC start/finish, a source citation and pass/error."""

    def __init__(self, clock=time.time):
        self.rows, self.clock = [], clock

    def begin(self, name, source):
        row = dict(name=name, source=source, started_utc=iso(self.clock()), passed=None)
        self.rows.append(row)
        return row

    def end(self, row, **detail):
        row.update(passed=True, finished_utc=iso(self.clock()), **detail)

    def skip(self, name, source, reason):
        self.rows.append(dict(name=name, source=source, started_utc=iso(self.clock()), passed=None,
                              skipped=True, reason=reason))

    def fail_open(self, error):
        for row in self.rows:
            if row["passed"] is None and not row.get("skipped"):
                row.update(passed=False, finished_utc=iso(self.clock()),
                           error="".join(traceback.format_exception_only(type(error), error)).strip())

    def __call__(self, name, source):
        checks = self

        class Scope:
            def __enter__(self):
                self.row = checks.begin(name, source)
                return self.row

            def __exit__(self, kind, error, tb):
                if kind is None:
                    checks.end(self.row)
                return False
        return Scope()

    def all_passed(self):
        return bool(self.rows) and all(r["passed"] is True or r.get("skipped") for r in self.rows)


# ---------------------------------------------------------------- pure argument / layout checks (no syscall)

def refusals(host, nice, sched_other, optimized, hold_seconds, min_samples, block_seconds, k4s_manifest_sha256):
    """Reasons to refuse before anything is opened, imported or written (empty list = proceed)."""
    out = []
    if host not in HOSTS:
        out.append("preflight runs only on 127x03/127x04")
    if nice != 10 or not sched_other:
        out.append("preflight must inherit the pinned nice 10 / SCHED_OTHER (fleet_profile.py:13)")
    if optimized:
        out.append("preflight refuses optimized Python (-O)")
    if host in MIN_HOLD_SECONDS and not hold_seconds >= MIN_HOLD_SECONDS[host]:
        out.append("hold below the minimum for " + host)
    if min_samples < MIN_SAMPLES:
        out.append("fewer than 60 guard samples requested")
    if not BLOCK_SECONDS_RANGE[0] <= block_seconds <= BLOCK_SECONDS_RANGE[1]:
        out.append("block seconds outside [1, 300]")
    if k4s_manifest_sha256 != K4S_MANIFEST_SHA256:
        out.append("--k4s-manifest-sha256 is not the K4S manifest of record 74314eda")
    return out


def under(path, root):
    return isinstance(path, str) and path.startswith(root + "/") and os.path.normpath(path) == path


def layout(a, host, base):
    """Every path argument equals the declared k4s-end-r1 layout (RC-6; Sol S5-F2). Pure: no syscall."""
    def bundle_dir(path, label):
        require(os.path.dirname(path) == base + "/bundles" and BUNDLE_NAME.fullmatch(os.path.basename(path)),
                label + " must be " + base + "/bundles/<name>")
        return path
    runtime = str(a.runtime_root)
    require(os.path.dirname(runtime) == base and RUNTIME_NAME.fullmatch(os.path.basename(runtime)),
            "--runtime-root must be " + base + "/runtime-<commit12>")
    bundle = bundle_dir(str(a.bundle), "--bundle")
    compare = bundle_dir(str(a.compare_bundle), "--compare-bundle") if a.compare_bundle else None
    require(compare != bundle, "--compare-bundle must be the attempt bundle, not the preflight bundle")
    require(str(a.repository) == base + "/repository", "--repository must be " + base + "/repository")
    require(str(a.attempt_parent) == base + "/attempts", "--attempt-parent must be " + base + "/attempts")
    out = str(a.out)
    job = os.path.dirname(out)
    name = os.path.basename(out)
    m = PREFLIGHT_NAME.fullmatch(name)
    require(m is not None and m.group(1) == host and os.path.basename(job) == name
            and os.path.dirname(job) == base + "/preflight", "--out must be " + base + "/preflight/<job>/<job>")
    require(str(a.corpus_inventory) == runtime + "/" + CORPUS_INVENTORY_REL,
            "--corpus-inventory must be the runtime's " + CORPUS_INVENTORY_REL)
    for label, path in (("--native", str(a.native)), ("--corpus", str(a.corpus))):
        require(under(path, base) and not any(under(path, base + "/" + d) or path == base + "/" + d
                                              for d in ("attempts", "preflight", "repository", "tools")),
                label + " must be a K4S-owned file under " + base + " (not attempts/preflight/repository/tools)")
    require(str(a.end_evidence).startswith(bundle + "/"), "--end-evidence must be inside the preflight bundle")
    for label in ("bundle_pins_sha256", "corpus_inventory_sha256", "end_evidence_sha256", "sd1_manifest_sha256"):
        require(isinstance(getattr(a, label), str) and re.fullmatch(r"[0-9a-f]{64}", getattr(a, label)),
                "--" + label.replace("_", "-") + " must be a SHA-256")
    require((a.compare_bundle is None) == (a.compare_bundle_pins_sha256 is None),
            "--compare-bundle and --compare-bundle-pins-sha256 go together")
    return dict(base=base, runtime_root=runtime, bundle=bundle, compare_bundle=compare, job=job, out=out, attempt=name)


def policy_for(si, host, base, paths, guard_job):
    """The one local Policy of a host run: every role exact (or a confined output pattern)."""
    R = si.Role
    roles = [
        R("runtime", paths["runtime_root"], "read", 64 << 20, exact=tuple(FROZEN_CLOSURE) + (MANIFEST_REL,
                                                                                          CORPUS_INVENTORY_REL)),
        R("bundle", paths["bundle"], "read", 64 << 20, exact=BUNDLE_FILES),
        R("guard-job", guard_job, "read", 64 << 20, exact=GUARD_SIDE_FILES + ("STOP", "STOP-" + host),
          grants=("guard-job",)),
        R("native", os.path.dirname(paths["native"]), "read", 4 << 30, exact=(os.path.basename(paths["native"]),)),
        R("corpus", os.path.dirname(paths["corpus"]), "read", 16 << 30, exact=(os.path.basename(paths["corpus"]),)),
        R("attempts", base + "/attempts", "read", 1, patterns=("*",)),          # names only, never read
        R("job", paths["job"], "write", 1, exact=(paths["attempt"],)),
        R("out", paths["out"], "write", 64 << 20, patterns=("*", "guard-sources/*")),
        R("out-read", paths["out"], "read", 1 << 30, patterns=("*", "guard-sources/*")),
    ]
    if paths["compare_bundle"]:
        roles.append(R("compare-bundle", paths["compare_bundle"], "read", 64 << 20, exact=BUNDLE_FILES))
    return si.Policy(host, roles)


# ---------------------------------------------------------------- the sealed store (safe_input writes)

class Store:
    """Exclusive files in one fresh directory, sealed even on failure (k4s_logic.K4SStore seal format,
    k4s_logic.py:1140-1167), written through si.Writer: O_CREAT|O_EXCL|O_NOFOLLOW, never truncated or replaced."""

    def __init__(self, si, policy, attempt):
        self.si, self.policy = si, policy
        with si.Writer(policy, "job") as job:
            job.mkdir_excl(attempt)
        self.writer = si.Writer(policy, "out")
        self.directory = Path(policy.role("out").root)

    def write(self, name, value):
        self.writer.create_excl(name, (canonical(dict(value, scope=SCOPE)) + "\n").encode())

    def mkdir(self, name):
        self.writer.mkdir_excl(name)

    def read_bytes(self, name, max_size=1 << 30):
        return self.si.read_bytes(self.policy, "out-read", name, max_size=max_size)

    def read_lines(self, name):
        """Complete JSON lines of a file the (stopped) frozen monitor wrote; an unterminated tail is skipped."""
        try:
            data = self.read_bytes(name)
        except self.si.Refusal as error:
            if error.code == "missing":
                return []
            raise
        return [self.si.loads_strict(s, name) for s in data.split(b"\n")[:-1] if s.strip()]

    def seal(self, status):
        walk = self.si.walk_tree(self.policy, "out-read")
        files = {f["rel"]: self.si.sha256_input(self.policy, "out-read", f["rel"])["sha256"] for f in walk["files"]}
        self.write("receipt-manifest.json", dict(status=status, files=files))
        digest = self.si.sha256_input(self.policy, "out-read", "receipt-manifest.json")["sha256"]
        self.writer.create_excl("receipt-manifest.sha256", (digest + "  receipt-manifest.json\n").encode())
        self.writer.close()


# ---------------------------------------------------------------- pre-import checks (stdlib + safe_input only)

def bundle_stamp(si, policy, role, pins_sha256):
    """tiers-pins.json read with its pinned SHA (and its .sha256 sidecar); the S4 test-only stamp and a non-production
    assembly receipt are refused before any guard/runtime work (S10-F4 carried into S5)."""
    manifest = si.read_json(policy, role, "tiers-pins.json", 64 << 20, expected_sha256=pins_sha256)
    sidecar = si.read_bytes(policy, role, "tiers-pins.sha256", max_size=4096)
    require(sidecar == (pins_sha256 + "  tiers-pins.json\n").encode(), role + ": tiers-pins.sha256 differs")
    receipt = si.read_json(policy, role, "assembly-receipt.json", 1 << 20)
    require(SYNTHETIC_KEY not in manifest, role + ": S4 SYNTHETIC-TEST-ONLY bundle refused")
    require(receipt.get("schema") == ASSEMBLY_SCHEMA and receipt.get("production_pins") is True
            and receipt.get("status") == "CANDIDATE" and receipt.get("manifest_sha256") == pins_sha256,
            role + ": assembly receipt is not a production receipt for this manifest")
    require(manifest.get("profile") == "fleet-reference", role + ": not a fleet-reference bundle")
    return manifest, receipt


def guard_job_of(si, manifest, host, preflight):
    guard = (manifest.get("reference_load_profile") or {}).get("guard") or {}
    job = guard.get("job")
    parent = si.Q4_GUARD_PARENTS[host]
    m = si.GUARD_JOB_NAME.fullmatch(os.path.basename(job or ""))
    require(isinstance(job, str) and os.path.dirname(job) == parent and m is not None,
            "Guard job must be " + parent + "/k4s-end-guard-r<N>-...")
    require(m.group(1).startswith("pf") == preflight,
            "Preflight bundles use a -pfNN guard job; attempt bundles a -rdRR-aNN guard job")
    return job


def pre_import_pins(si, policy):
    """S5-F1: the K4S manifest of record (fixed constant), and every file of its frozen closure, through safe_input
    with the pinned SHA-256, before any runtime module is imported or executed."""
    manifest = si.loads_strict(si.read_bytes(policy, "runtime", MANIFEST_REL, max_size=4 << 20,
                                             expected_sha256=K4S_MANIFEST_SHA256), MANIFEST_REL)
    require(manifest.get("schema") == "clasher.k4s.mac-manifest.v1" and manifest.get("frozen") is True
            and manifest.get("status") == "FROZEN", "K4S manifest is not the frozen manifest of record")
    derived = {}
    for key in ("k4s_files", "end_files", "reused_readonly"):
        for rel, pin in manifest[key].items():
            require(derived.get(rel, pin) == pin, "Conflicting manifest pins for " + rel)
            derived[rel] = pin
    for rel, pin in manifest["k4s_kernel"]["files"].items():
        require(derived.get(rel, pin) == pin, "Conflicting kernel pin for " + rel)
        derived[rel] = pin
    derived[manifest["sd1_manifest"]["path"]] = manifest["sd1_manifest"]["sha256"]
    require(derived == FROZEN_CLOSURE, "K4S manifest closure differs from the code constant table")
    require(manifest["corpus"]["inventory"] == CORPUS_INVENTORY_REL, "Corpus inventory path differs from the manifest")
    for rel, pin in sorted(FROZEN_CLOSURE.items()):
        si.read_bytes(policy, "runtime", rel, max_size=64 << 20, expected_sha256=pin)
    for rel in END_SOURCES:
        require(rel in FROZEN_CLOSURE, "END source outside the frozen closure: " + rel)
    return dict(k4s_manifest_sha256=K4S_MANIFEST_SHA256, closure_files=len(FROZEN_CLOSURE), all_sha256_verified=True)


def runtime_modules(runtime_root):
    """{rel: path} of every loaded module whose file lies inside the runtime (normalized, not resolved)."""
    out = {}
    prefix = str(runtime_root) + "/"
    for module in list(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if isinstance(path, str) and os.path.normpath(path).startswith(prefix):
            out[os.path.normpath(path)[len(prefix):]] = os.path.normpath(path)
    return out


def closure_only(runtime_root):
    """Right after the frozen imports: every module loaded from the runtime is a verified closure file."""
    loaded = runtime_modules(runtime_root)
    outside = sorted(rel for rel in loaded if rel not in FROZEN_CLOSURE)
    require(not outside, "A non-closure runtime module was imported: " + ",".join(outside))
    return sorted(loaded)


def loaded_modules_check(si, policy, host, runtime_root, runtime_files):
    """Every loaded runtime module is a closure file (already verified) or a bundle runtime_files member whose bytes,
    read through safe_input now, equal the bundle pin. Anything else refuses."""
    loaded = runtime_modules(runtime_root)
    extra = sorted(rel for rel in loaded if rel not in FROZEN_CLOSURE)
    for rel in extra:
        require(rel in runtime_files, "Loaded runtime module outside the closure and the bundle pins: " + rel)
    if extra:
        check = si.Policy(host, [si.Role("runtime-extra", str(runtime_root), "read", 64 << 20, exact=tuple(extra))])
        for rel in extra:
            si.read_bytes(check, "runtime-extra", rel, expected_sha256=runtime_files[rel])
    return dict(loaded_runtime_modules=len(loaded), outside_closure=extra)


# ---------------------------------------------------------------- health-only summaries

def quantiles(values):
    if not values:
        return None
    s = sorted(values)
    return dict(n=len(s), min=s[0], p50=s[(len(s) - 1) // 2], max=s[-1], mean=sum(s) / len(s))


def bus_series(rows):
    """(monotonic timestamp, cumulative bus ticks, phase) from the frozen guard's per-sample system_bus."""
    out = []
    for r in rows:
        bus = (r.get("reporting_guard") or {}).get("system_bus") or {}
        if "cpu_ticks" in bus and "timestamp" in r:
            out.append((r["timestamp"], bus["cpu_ticks"], r.get("phase")))
    return out


def window_max(series, hz, seconds):
    """Max bus % of one core over the shortest windows spanning >= seconds; flagged with the frozen integer rule
    ticks*100 > hz*elapsed (system_bus.py:30)."""
    best, flagged, count, i = None, 0, 0, -1
    for j in range(len(series)):
        while i + 1 < j and series[j][0] - series[i + 1][0] >= seconds:
            i += 1
        if i < 0 or series[j][0] - series[i][0] < seconds:
            continue
        dt, ticks = series[j][0] - series[i][0], series[j][1] - series[i][1]
        percent = 100. * ticks / hz / dt
        count += 1
        flagged += ticks * 100 > hz * dt
        best = percent if best is None else max(best, percent)
    return dict(window_seconds=seconds, windows=count, max_percent=best, flagged_over_1_percent=flagged)


def cumulative(series, hz):
    if len(series) < 2:
        return None
    dt, ticks = series[-1][0] - series[0][0], series[-1][1] - series[0][1]
    return dict(seconds=dt, cpu_ticks=ticks, percent=100. * ticks / hz / dt if dt > 0 else None)


def band(percent):
    """P2-3 band of the loaded cumulative bus %: proceed (<= ~0.3), coordinator-decision (between), stop (>= 0.7)."""
    if percent is None:
        return "unavailable"
    return "proceed" if percent <= BUS_PROCEED_MAX else "stop" if percent >= BUS_STOP_MIN else "coordinator-decision"


def bus_summary(rows, hz, loaded_phase=HOLD_PHASE):
    series = bus_series(rows)
    loaded = [s for s in series if s[2] == loaded_phase]
    last = ((rows[-1].get("reporting_guard") or {}).get("system_bus") or {}) if rows else {}
    total = cumulative(series, hz)
    hold = cumulative(loaded, hz)
    return dict(hz=hz, samples=len(series), loaded_samples=len(loaded),
                guard_cumulative_core_fraction_last=last.get("core_fraction"),
                guard_interfered_last=last.get("interfered"), guard_retired_last=last.get("retired"),
                cumulative_all=total, cumulative_loaded=hold,
                windows_all=[window_max(series, hz, w) for w in WINDOWS_SECONDS],
                windows_loaded=[window_max(loaded, hz, w) for w in WINDOWS_SECONDS],
                loaded_band=band(hold and hold["percent"]))


def block_summary(blocks):
    done = [b["reporting_guard"]["completed_block"] for b in blocks
            if b.get("event") == "end" and "completed_block" in (b.get("reporting_guard") or {})]
    bus = [100. * d["system_bus"]["core_fraction"] for d in done if "system_bus" in d]
    return dict(completed=len(done), seconds=quantiles([d["seconds"] for d in done]),
                bus_percent=quantiles(bus),
                flagged_bus=sum(bool(d.get("system_bus", {}).get("interfered")) for d in done),
                flagged_idle=sum(bool(d.get("idle_services", {}).get("interfered")) for d in done),
                flagged_ssh=sum(bool(d.get("ssh_family", {}).get("interfered")) for d in done))


def mhz_summary(rows, cpus, loaded_phase=HOLD_PHASE):
    loaded = [r for r in rows if r.get("phase") == loaded_phase and "cpu_clock_mhz_by_processor" in r]
    means, per_core = [], {str(c): [] for c in cpus}
    for r in loaded:
        clocks = r["cpu_clock_mhz_by_processor"]
        values = [clocks[str(c)] for c in cpus if str(c) in clocks]
        if len(values) == len(cpus):
            means.append(sum(values) / len(values))
        for c in cpus:
            if str(c) in clocks:
                per_core[str(c)].append(clocks[str(c)])
    return dict(occupied_cpus=len(cpus), loaded_samples=len(loaded), occupied_mean_mhz=quantiles(means),
                per_core={c: quantiles(v) for c, v in per_core.items()})


def sshd_summary(rows, loaded_phase=HOLD_PHASE):
    """sshd process count per 1 Hz census row (names only); a rise during the hold means a login."""
    counts = [(r.get("phase"), sum(p.get("name") == "sshd" for p in r.get("processes", []))) for r in rows]
    loaded = [c for phase, c in counts if phase == loaded_phase]
    return dict(all=quantiles([c for _, c in counts]), loaded=quantiles(loaded),
                loaded_first=loaded[0] if loaded else None,
                login_detected_during_hold=bool(loaded) and max(loaded) > loaded[0])


def guard_reasons(rows):
    return sorted({(r.get("reporting_guard") or {}).get("reason") for r in rows} - {None})


# ---------------------------------------------------------------- frozen modules (imported from the runtime)

class Frozen:
    """The frozen END modules from the runtime export, imported in end_reference.reference() order, only after
    pre_import_pins verified every closure file."""

    def __init__(self, runtime_root):
        runtime_root = str(runtime_root)
        here = runtime_root + "/" + STUDY_REL
        sys.path[:0] = [here + "/mac", here]
        import end_reference as ER                       # module import only: k4s_logic, end_pool, end_evidence
        require(os.path.normpath(ER.__file__) == here + "/end_reference.py", "end_reference not from the runtime")
        sys.path.insert(0, str(ER.ROOT / ER.L.E4V3_REL))  # end_reference.py:285-286
        import end_background as G                        # end_reference.py:288
        for module in (ER, G, ER.L, ER.P, ER.E):           # the very files pre_import_pins verified, not shadows/pycs
            require(os.path.normpath(module.__file__) in [runtime_root + "/" + rel for rel in END_SOURCES],
                    "Imported END module is not the verified runtime source: " + module.__name__)
        closure_only(runtime_root)
        self.ER, self.G, self.L, self.P, self.E = ER, G, ER.L, ER.P, ER.E

    def bundle_tools(self):                                # end_reference.py:292-293 (after frozen_helpers)
        from tier_backend import NATIVE_SHA, validate_bundle
        from fleet_validity import FleetTechnicalError
        return SimpleNamespace(NATIVE_SHA=NATIVE_SHA, validate_bundle=validate_bundle,
                               FleetTechnicalError=FleetTechnicalError)

    def guard_tools(self):                                 # end_reference.py:295-296 (after frozen_identity)
        from fleet_reference import reference_monitor
        from telemetry import cpu_counters, validate_physical_cpus, validate_topology
        return SimpleNamespace(reference_monitor=reference_monitor, cpu_counters=cpu_counters,
                               validate_physical_cpus=validate_physical_cpus, validate_topology=validate_topology)


def frozen_namespace(a, F):
    """The argparse namespace end_reference.main() would build, with the frozen defaults (end_reference.py:416-437)."""
    ER = F.ER
    return SimpleNamespace(
        bundle=Path(a.bundle), runtime_root=Path(a.runtime_root), native=Path(a.native), corpus=Path(a.corpus),
        corpus_sha256=ER.K4_CORPUS_SHA256, corpus_inventory=Path(a.corpus_inventory), kernel=ER.KERNEL_REL,
        scorer=ER.SCORER_REL, k4s_manifest=ER.HERE / "mac" / F.L.MANIFEST_NAME,
        k4s_manifest_sha256=a.k4s_manifest_sha256, sd1_manifest=ER.HERE / "SD1-MANIFEST.json",
        sd1_manifest_sha256=a.sd1_manifest_sha256, end_evidence=Path(a.end_evidence),
        end_evidence_sha256=a.end_evidence_sha256, repository=Path(a.repository), end_job_sha256=a.end_job_sha256,
        round=0, out=None)


def listings(si, tool, policy, host, repository):
    """Names-only: the attempt parent (must stay empty: preflights precede every claim, RC-9) and the claim
    registry (k4s_end_host_tool.registry_listing)."""
    return dict(attempt_parent=tool.names_only(si, policy, "attempts"),
                registry=tool.registry_listing(si, host, repository))


# ---------------------------------------------------------------- the preflight body

def preflight(a, store, checks, F, result, ctx, clock=time.monotonic, sleep=time.sleep):
    """Everything of end_reference.reference() except the claim and measure(); fills ``result``."""
    import multiprocessing as mp
    si, policy = ctx.si, ctx.policy
    r = frozen_namespace(a, F)
    state = SimpleNamespace(stop=mp.get_context("spawn").Event(), monitor=None, channel=None, monitor_channel=None,
                            backend=None)
    primary = None
    try:
        with checks("frozen_helpers", "end_reference.py:289-291; end_background.py:58-67; end_pool.py:204-217"):
            spec = F.G.evidence_spec(r.end_evidence, r.end_evidence_sha256, r.repository, r.k4s_manifest,
                                     r.k4s_manifest_sha256)
            _, (fleet_end, fleet_profile, fleet_validity) = F.G.frozen_helpers(spec, r.runtime_root)
        with checks("frozen_identity", "end_reference.py:96-110,292-294; tier_backend.py:450-469"):
            T = F.bundle_tools()
            manifest, pins, host_pins = F.ER.frozen_identity(r, T.validate_bundle, T.NATIVE_SHA)
            require(canonical(manifest) == canonical(ctx.manifest), "Frozen bundle manifest differs from the pinned one")
        W = F.guard_tools()
        profile = manifest["reference_load_profile"]
        if a.compare_bundle:
            with checks("bundle_parity", "RC-3; T1 END-A5 per-attempt bundles differ only in guard.job") as row:
                row.update(bundle_parity(manifest, ctx.compare_manifest))
        else:
            checks.skip("bundle_parity", "RC-3", "no --compare-bundle given")
        with checks("guard_job_fresh", "RC-3; fleet_validity.py:86,112-114") as row:
            for name in GUARD_SIDE_FILES + ("STOP", "STOP-" + ctx.host):
                si.check_absent(policy, "guard-job", name)
            row.update(guard_job=ctx.guard_job, fresh=True)
            result["guard_job"] = ctx.guard_job
        with checks("reporting_profile", "end_reference.py:297-301; end_background.py:70-87; "
                                         "fleet_profile.py:9-29; fleet_end.host_reporting") as row:
            host_identity = F.G.FrozenHooks().host()
            profile, plan, (search, background_masks, census_cpu), evidence, reporting = \
                F.G.k4s_reporting_profile(r.bundle, manifest, spec, host_identity, fleet_end, fleet_profile)
            host = host_identity["node"]
            require(host_pins["bundle_profile_host"] == host == ctx.host, "Bundle reference profile names a different host")
            row.update(host=host, nice=host_identity["nice"], search_cpus=search, background_slots=len(background_masks),
                       census_cpu=census_cpu, reporting_rows=len(reporting), end_evidence_sha256=evidence["sha256"])
            result["occupied_cpus"] = search + sum(background_masks, [])
            result["load"] = dict(slot_count=profile["slot_count"], background_slots_expected=len(background_masks),
                                  reference_slot_work=bool(a.reference_work))
        with checks("physical_cpus", "end_reference.py:302-304; telemetry.py:74-88"):
            W.validate_physical_cpus(search + sum(background_masks, []) + [census_cpu])
            os.sched_setaffinity(0, set(search))
            r.cores = search
        if a.end_job_sha256:
            with checks("end_job_read_only", "end_reference.py:305; end_evidence.py:415-432 (git reads only)"):
                F.E.end_job(r.repository, evidence, r.end_job_sha256, r.k4s_manifest_sha256)
        else:
            checks.skip("end_job_read_only", "end_reference.py:305", "RC-2 runs before the END-JOB is committed")
        # NEVER end_reference.py:307-311 (pool_context, producer_claim, K4SStore(REFERENCE_SCOPE)).
        with checks("backend_and_corpus", "end_reference.py:159-165,326-328") as row:
            be = state.backend = F.ER.backend(r)
            ids = F.L.check_corpus(r.corpus_sha256, r.corpus_sha256, ctx.corpus_inventory, None, list(be.k4s_rows))
            row.update(corpus_states=len(ids))
        context = mp.get_context("spawn")
        stop, phase = state.stop, context.Array("c", 64)
        owned = context.Array("i", [os.getpid()] + [0] * (len(background_masks) + 1))
        channel, monitor_channel = state.channel, state.monitor_channel = context.Pipe()
        with checks("topology", "end_reference.py:333; telemetry.py:60-71"):
            clusters = W.validate_topology(manifest["topology"], W.cpu_counters(), darwin=False)
        monitor = state.monitor = context.Process(target=W.reference_monitor, args=(
            stop, phase, owned, clusters, store.directory / "capacity.jsonl", census_cpu, r.bundle, manifest,
            monitor_channel))

        def check_monitor():                                  # end_reference.py:338-340
            if not monitor.is_alive():
                raise T.FleetTechnicalError("crash", "Reference telemetry/guard process stopped")

        def checkpoint(event, identity):                      # end_reference.py:342-353
            channel.send(dict(event=event, id=identity, phase=phase.value.decode()))
            limit = clock() + 60
            while not channel.poll(.1):
                check_monitor()
                if clock() > limit:
                    raise T.FleetTechnicalError("crash", "Reference guard checkpoint timed out")
            reply = channel.recv()
            if reply["event"] != event or reply["id"] != identity:
                raise T.FleetTechnicalError("crash", "Reference guard checkpoint identity mismatch")
            if reply["reason"]:
                raise T.FleetTechnicalError("validity_census", reply["reason"])

        class guarded:                                         # end_reference.py:355-359
            def __init__(self, identity):
                self.identity = identity

            def __enter__(self):
                checkpoint("begin", self.identity)

            def __exit__(self, kind, error, tb):
                if kind is None:
                    checkpoint("end", self.identity)
                return False

        def set_phase(name):                                   # end_reference.py:361-362
            phase.value = name.encode()
        with checks("guard_admission", "end_reference.py:363-365; fleet_reference.py:235-256; "
                                       "fleet_validity.py:53-203") as row:
            set_phase("reference-warmup")
            monitor.start(); owned[-1] = monitor.pid
            checkpoint("admit", "preflight-admission")
            admission = si.loads_strict(store.read_bytes("guard-admission.json", 16 << 20), "guard-admission.json")
            row.update(admission_utc=iso(admission["utc"]))
            result["admission_epoch"] = admission["utc"]
        ready = checks.begin("background_ready", "end_reference.py:366-374; end_background.py:132-157; "
                                                 "replay_load.py:131-145")
        load = F.G.K4SFleetBackground(r.bundle, r.runtime_root, r.native, background_masks, spec)
        load.check_external = check_monitor
        with load as background:
            for index, worker in enumerate(background.workers, 1):
                owned[index] = worker.pid
            slots = dict(reference_affinity=sorted(os.sched_getaffinity(0)),
                         reference_nice=os.getpriority(os.PRIO_PROCESS, 0),
                         background_affinity=[sorted(os.sched_getaffinity(w.pid)) for w in background.workers],
                         background_nice=[os.getpriority(os.PRIO_PROCESS, w.pid) for w in background.workers])
            result["slot_evidence"] = slots
            require(slots["reference_nice"] == 10 and set(slots["background_nice"]) == {10},
                    "Slot priority read back differs from nice 10")
            require(slots["background_affinity"] == [sorted(m) for m in background_masks],
                    "Background affinity read back differs from the pinned masks")
            result["load"]["background_slots_ready"] = len(background.workers)
            checks.end(ready, workers=len(background.workers))
            hold = checks.begin("loaded_hold", "end_reference.py:375-387 (warm-up loop; never measure())")
            set_phase(HOLD_PHASE)
            start = clock()
            until = start + a.hold_seconds
            result["hold_started_utc"] = iso()
            warmed, lap = 0, 0
            if a.reference_work:
                while clock() < until:                         # end_reference.py:377-387 verbatim
                    for offset in range(0, len(ids), F.P.BLOCK):
                        if clock() >= until:
                            break
                        with guarded(f"warm-{lap}-{offset}"):
                            for identity in ids[offset:offset + F.P.BLOCK]:
                                if clock() >= until:
                                    break
                                background.check(); check_monitor()
                                be.k4s_work(be.k4s_rows[identity]); warmed += 1
                    lap += 1
            else:
                while clock() < until:
                    with guarded(f"hold-{lap}"):
                        block_end = min(until, clock() + a.block_seconds)
                        while clock() < block_end:
                            background.check(); check_monitor()
                            sleep(max(0., min(1., block_end - clock())))
                    lap += 1
            result["load"]["reference_slot_states_worked"] = warmed
            checks.end(hold, seconds=clock() - start, reference_slot_work=warmed, laps=lap)
            result["hold_finished_utc"] = iso()
        with checks("monitor_stop", "end_reference.py:392-394"):
            stop.set(); monitor.join(10)
            if monitor.is_alive() or monitor.exitcode != 0:
                raise T.FleetTechnicalError("crash", "Reference census did not stop cleanly before sealing")
        with checks("guard_samples", "RC-2: >= 60 1 Hz guard rows after admission (read after the monitor stopped)") \
                as row:
            rows = store.read_lines("capacity.jsonl")
            admitted = [x for x in rows if x.get("utc", 0) >= result["admission_epoch"]]
            require(len(admitted) >= a.min_samples, "Fewer than the required 1 Hz guard samples after admission")
            row.update(samples_after_admission=len(admitted))
        with checks("frozen_guard_validators", "end_reference.py:395-399; fleet_validity.py:230-283"):
            census = F.P.read_lines(store.directory / "capacity.jsonl")
            fleet_validity.validate_census(census)
            fleet_validity.validate_admission(json.loads((store.directory / "guard-admission.json").read_text()))
            fleet_validity.validate_blocks(F.P.read_lines(store.directory / "guard-blocks.jsonl"),
                                           require_measurement=False)
        source = "end_reference.py:400-403; fleet_profile.py:48-68 (hold rows relabelled reference-speed)"
        with checks("mhz_comparison", source) as row:
            relabelled = [dict(x, phase="reference-speed") if x.get("phase") == HOLD_PHASE else x for x in census]
            clocks = fleet_profile.compare_mhz(reporting, relabelled, search + sum(background_masks, []),
                                               profile["slot_count"])
            row.update(gate=bool(a.reference_work), passes=clocks["passes"],
                       absolute_relative_difference=clocks["absolute_relative_difference"])
            result["mhz_comparison"] = clocks
            require(clocks["passes"] or not a.reference_work, "Preflight/reporting MHz differs by >5%")
        with checks("post_pins", "end_reference.py:404-406; S5-F1 loaded-module closure") as row:
            T.validate_bundle(r.bundle, r.runtime_root, dry_run=True, require_references=False)
            require(F.L.sha(r.native) == pins["native_sha256"], "Native changed during the preflight")
            F.ER.executing_sources(pins["measurement_files"])
            row.update(loaded_modules_check(si, policy, ctx.host, r.runtime_root, manifest["runtime_files"]))
    except BaseException as error:
        primary = error
        raise
    finally:
        cleanup = checks.begin("cleanup", "end_reference.py:252-279 (frozen cleanup_steps)")
        try:
            F.ER.cleanup_steps(state)
            checks.end(cleanup)
        except BaseException as error:                        # a primary failure is never replaced by cleanup
            cleanup.update(passed=False, finished_utc=iso(), error=traceback.format_exc()[-2000:])
            if primary is None:
                raise
    return result


def bundle_parity(preflight_manifest, attempt_manifest):
    """Per-attempt bundles differ only in reference_load_profile.guard.job (T1 A5 pattern; RC-3)."""
    def strip(m):
        m = json.loads(json.dumps(m))
        job = m["reference_load_profile"]["guard"].pop("job")
        return m, job
    a, job_a = strip(preflight_manifest)
    b, job_b = strip(attempt_manifest)
    require(a == b, "Preflight bundle differs from the attempt bundle beyond guard.job")
    require(job_a != job_b, "Preflight must use its own guard job, not the attempt's")
    return dict(identical_except_guard_job=True, preflight_guard_job=job_a, attempt_guard_job=job_b)


def summaries(store, result, hz):
    rows = store.read_lines("capacity.jsonl")
    blocks = store.read_lines("guard-blocks.jsonl")
    cpus = result.get("occupied_cpus") or []
    return dict(samples=len(rows), bus=bus_summary(rows, hz), blocks=block_summary(blocks),
                mhz=mhz_summary(rows, cpus), sshd=sshd_summary(rows), guard_reasons=guard_reasons(rows + blocks))


def copy_guard_sources(si, policy, store):
    """Raw health-only guard outputs of the preflight's own guard job (fleet_reference.py:217-226), copied through
    the descriptor gate into guard-sources/ (exclusive)."""
    copied = []
    for name in GUARD_SIDE_FILES:
        try:
            item = si.open_input(policy, "guard-job", name)
        except si.Refusal as error:
            if error.code == "missing":
                continue
            raise
        if not copied:
            store.mkdir("guard-sources")
        item.copy_to(store.writer, "guard-sources/" + name)
        copied.append(name)
    return copied


def verdict(checks, result, host):
    """pass = every check passed, attempt parent empty and registry unchanged, guard sources copied through the
    descriptor gate, on 04 no login during the hold.
    mode/qualifying (P2-3): BINDING needs reference-slot work, every background slot ready and the measured loaded
    span >= MIN_LOADED_SECONDS; anything else is a NON-QUALIFYING diagnostic. bus_gate: the loaded band (04)."""
    before, after = result.get("before"), result.get("after")
    unchanged = before is not None and before == after
    empty = unchanged and before["attempt_parent"] == []
    no_login = result.get("summaries", {}).get("sshd", {}).get("login_detected_during_hold") is False
    copied = result.get("guard_sources") is not None              # a refused guard-source copy fails the run
    ok = checks.all_passed() and unchanged and empty and copied and (host != "127x04" or no_login)
    load = result.get("load") or {}
    loaded = ((result.get("summaries") or {}).get("bus") or {}).get("cumulative_loaded") or {}
    measured = loaded.get("seconds")
    duration = dict(hold_seconds_requested=result["hold_seconds"], loaded_seconds_measured=measured,
                    loaded_seconds_required=MIN_LOADED_SECONDS.get(host))
    binding = (result["mode_requested"] == "binding" and load.get("reference_slot_work") is True
               and (load.get("reference_slot_states_worked") or 0) > 0
               and load.get("background_slots_ready") == load.get("background_slots_expected")
               == (load.get("slot_count") or 0) - 1
               and measured is not None and measured >= MIN_LOADED_SECONDS.get(host, float("inf")))
    bus_band = ((result.get("summaries") or {}).get("bus") or {}).get("loaded_band", "unavailable")
    return dict(passed=bool(ok), registry_and_attempt_parent_unchanged=unchanged, attempt_parent_empty=empty,
                mode="binding" if binding else "diagnostic", qualifying=bool(ok and binding), duration=duration,
                bus_band=bus_band, bus_gate=bus_band if host == "127x04" else "not-gated-on-" + str(host))


def run(a, frozen_factory=Frozen, hostinfo=None, layers=None):
    si, tool = layers or load_layers()
    hostinfo = hostinfo or dict(host=si.hostname_checked().split(".")[0], nice=os.getpriority(os.PRIO_PROCESS, 0),
                                sched_other=os.sched_getscheduler(0) == os.SCHED_OTHER,
                                optimized=bool(sys.flags.optimize))
    host = hostinfo["host"]
    reasons = refusals(host, hostinfo["nice"], hostinfo["sched_other"], hostinfo["optimized"], a.hold_seconds,
                       a.min_samples, a.block_seconds, a.k4s_manifest_sha256)
    if reasons:
        raise PreflightRefusal("; ".join(reasons))
    base = si.END_BASES[host]
    paths = layout(a, host, base)
    paths.update(native=str(a.native), corpus=str(a.corpus))
    # The guard job is not yet known: a first, read-only policy pins the bundle; the run policy adds the guard job.
    pre = si.Policy(host, [si.Role("bundle", paths["bundle"], "read", 64 << 20, exact=BUNDLE_FILES)])
    manifest, _ = bundle_stamp(si, pre, "bundle", a.bundle_pins_sha256)
    guard_job = guard_job_of(si, manifest, host, preflight=True)
    policy = policy_for(si, host, base, paths, guard_job)
    store = Store(si, policy, paths["attempt"])
    checks = Checks()
    result = dict(schema=SCHEMA, scope=SCOPE, host=host, started_utc=iso(), claim=False, measure_called=False,
                  timing=False, outcome_access=False, live_actions=False, games=False,
                  mode_requested="binding" if a.reference_work else "diagnostic",
                  reference_work=bool(a.reference_work), hold_seconds=a.hold_seconds, block_seconds=a.block_seconds,
                  min_samples=a.min_samples, python=sys.version.split()[0], nice=hostinfo["nice"],
                  safe_input_sha256=SAFE_INPUT_SHA256, host_tool_sha256=HOST_TOOL_SHA256,
                  inputs=dict(bundle=paths["bundle"], bundle_pins_sha256=a.bundle_pins_sha256,
                              runtime_root=paths["runtime_root"], native=str(a.native), corpus=str(a.corpus),
                              corpus_inventory=str(a.corpus_inventory),
                              corpus_inventory_sha256=a.corpus_inventory_sha256, end_evidence=str(a.end_evidence),
                              end_evidence_sha256=a.end_evidence_sha256, k4s_manifest_sha256=a.k4s_manifest_sha256,
                              sd1_manifest_sha256=a.sd1_manifest_sha256, repository=str(a.repository),
                              attempt_parent=str(a.attempt_parent), compare_bundle=paths["compare_bundle"],
                              compare_bundle_pins_sha256=a.compare_bundle_pins_sha256,
                              end_job_sha256=a.end_job_sha256, guard_job=guard_job))
    ctx = SimpleNamespace(si=si, tool=tool, policy=policy, host=host, manifest=manifest, guard_job=guard_job,
                          compare_manifest=None, corpus_inventory=None)
    error = None
    try:
        with checks("listings_before", "RC-2: never write under the attempt parent or the registry") as row:
            result["before"] = listings(si, tool, policy, host, str(a.repository))
            row.update(result["before"])
        with checks("bundle_stamp", "Sol PKG2 S5-F2/S10-F4: pinned bundle manifest, no S4 test-only stamp") as row:
            if a.compare_bundle:
                ctx.compare_manifest, _ = bundle_stamp(si, policy, "compare-bundle", a.compare_bundle_pins_sha256)
                guard_job_of(si, ctx.compare_manifest, host, preflight=False)
            require(manifest["reference_load_profile"].get("host") == host, "Bundle profile names another host")
            require(str(a.end_evidence) == paths["bundle"] + "/" + manifest["reference_load_profile"]["end_evidence"],
                    "--end-evidence is not the bundle-pinned END evidence")
            row.update(guard_job=guard_job, synthetic_stamp=False)
        with checks("input_locations", "Sol PKG2 S5-F2: native/corpus pass the read-location gates (not read here)"):
            for role in ("native", "corpus"):
                si.open_input(policy, role, os.path.basename(paths[role])).close()
        with checks("guard_repo", "frozen-reader ruling 21:28Z; coordinator 15:41Z Q3; parent_source_seed.py:62-69") \
                as row:
            row.update(tool.verify_clone(si, host, guard_job + "/repo", grants=("guard-job",)))
            row.update(commits=tool.seed_commits(si, guard_job + "/repo", SEED_COMMITS))
        with checks("repository_clone", "frozen-reader ruling 21:28Z (frozen evidence/END-JOB git reads)") as row:
            row.update(tool.verify_clone(si, host, str(a.repository)))
        with checks("frozen_git_env", "frozen-reader ruling 21:28Z; P2-4 environment for frozen git") as row:
            inherited = dict(os.environ)
            checked = tool.check_global_git_config(si, inherited)
            os.environ.clear()
            os.environ.update(tool.frozen_git_env(si, inherited))
            row.update(global_config_checked=checked,
                       git_keys=sorted(k for k in os.environ if k.startswith("GIT_")))
        with checks("pre_import_pins", "Sol PKG2 S5-F1: fixed 74314eda + closure via safe_input before import") as row:
            row.update(pre_import_pins(si, policy))
            ctx.corpus_inventory = si.read_json(policy, "runtime", CORPUS_INVENTORY_REL, 64 << 20,
                                                expected_sha256=a.corpus_inventory_sha256)
        with checks("frozen_import", "end_reference.py:56-61,285-288 (module imports only)"):
            F = frozen_factory(a.runtime_root)
        preflight(a, store, checks, F, result, ctx)
    except BaseException as caught:                     # recorded; the seal is "failed"
        error = caught
        checks.fail_open(caught)
        result["error"] = traceback.format_exc()
    try:
        result["after"] = listings(si, tool, policy, host, str(a.repository))
    except Exception:
        result["after"] = None
        result["listings_after_error"] = traceback.format_exc()[-2000:]
    result["checks"] = checks.rows
    try:
        result["summaries"] = summaries(store, result, os.sysconf("SC_CLK_TCK"))
    except Exception:                                    # health summaries never prevent the sealed result
        result["summaries"] = {}
        result["summaries_error"] = traceback.format_exc()[-2000:]
    try:
        result["guard_sources"] = copy_guard_sources(si, policy, store)
    except Exception:
        result["guard_sources"] = None
        result["guard_sources_error"] = traceback.format_exc()[-2000:]
    result.update(verdict(checks, result, host))
    result["finished_utc"] = iso()
    result.pop("admission_epoch", None)
    store.write("preflight-result.json", result)
    store.seal("passed" if result["passed"] else "failed")
    if error is not None and not isinstance(error, Exception):
        raise error
    return 0 if result["passed"] else 1


# ---------------------------------------------------------------- 05: received preflight check (safe_input reads)

def verify_received(si, root, host_policy=None):
    """Seal, transfer and no-claim checks of one pushed preflight, all through safe_input on 05; returns the
    verified summary (schema VERIFIED_SCHEMA) that S7 consumes for RC-9."""
    root = str(root)
    host, attempt = os.path.basename(os.path.dirname(root)), os.path.basename(root)
    m = PREFLIGHT_NAME.fullmatch(attempt)
    require(os.path.dirname(os.path.dirname(root)) == RECEIVE_BASE and host in HOSTS and m and m.group(1) == host,
            "Wrong preflight receive namespace")
    sealed_rel = ("preflight/receipt-manifest.json", "preflight/receipt-manifest.sha256")
    P = si.Policy("127x05", [si.Role("recv", root, "read", 64 << 20, exact=RECEIVE_NAMES + ("PUSH-FAILED.json",)
                                     + sealed_rel)])
    si.check_absent(P, "recv", "PUSH-FAILED.json")
    for name in RECEIVE_NAMES:
        si.sha256_input(P, "recv", name)                   # descriptor gate: regular, single link, no symlink
    exit_ = si.read_json(P, "recv", "exit.json", 1 << 16)
    marker = si.read_json(P, "recv", "TRANSFER-DONE.json", 1 << 16)
    require(marker.get("transfer_complete") is True and marker.get("host") == exit_.get("host") == host
            and marker.get("attempt") == exit_.get("attempt") == attempt, "Transfer/exit mismatch")
    require(type(exit_.get("exit_code")) is int and marker.get("measurement_exit_code") == exit_["exit_code"],
            "Transfer/exit code mismatch")
    require(exit_.get("measurement_exists") is True, "No preflight directory")
    seal_bytes = si.read_bytes(P, "recv", "preflight/receipt-manifest.json", max_size=64 << 20)
    seal_sha = hashlib.sha256(seal_bytes).hexdigest()
    require(si.read_bytes(P, "recv", "preflight/receipt-manifest.sha256", max_size=4096)
            == (seal_sha + "  receipt-manifest.json\n").encode(), "Seal SHA mismatch")
    manifest = si.loads_strict(seal_bytes, "receipt-manifest.json")
    require(manifest.get("scope") == SCOPE and manifest.get("status") in ("passed", "failed"), "Unexpected seal")
    files = manifest.get("files")
    require(isinstance(files, dict) and "preflight-result.json" in files, "Seal lacks preflight-result.json")
    names = tuple(files) + SEAL_FILES
    S = si.Policy("127x05", [si.Role("sealed", root + "/preflight", "read", 1 << 30, exact=names),
                             si.Role("out", root, "write", 1 << 20, exact=("PREFLIGHT-VERIFIED.json",))])
    walked = {f["rel"] for f in si.walk_tree(S, "sealed")["files"]}      # undeclared/aliased/outcome names refuse
    require(walked == set(names), "Extra/missing files in the sealed preflight")
    for name, digest in files.items():
        require(si.sha256_input(S, "sealed", name)["sha256"] == digest, "File SHA mismatch: " + name)
    result = si.loads_strict(si.read_bytes(S, "sealed", "preflight-result.json", expected_sha256=files[
        "preflight-result.json"]), "preflight-result.json")
    require(result.get("schema") == SCHEMA and result.get("scope") == SCOPE and result.get("host") == host,
            "Preflight result identity mismatch")
    require((exit_["exit_code"] == 0) == (manifest["status"] == "passed") == (result.get("passed") is True),
            "Exit/status/result mismatch")
    require(result.get("claim") is False and result.get("measure_called") is False, "Preflight claimed or measured")
    bus = (result.get("summaries") or {}).get("bus") or {}
    return dict(schema=VERIFIED_SCHEMA, scope=SCOPE, verified_utc=iso(), host=host, attempt=attempt, receive=root,
                status=manifest["status"], passed=result["passed"], mode=result.get("mode"),
                qualifying=result.get("qualifying") is True, load=result.get("load"), duration=result.get("duration"),
                bus_cumulative_loaded=bus.get("cumulative_loaded"), bus_band=result.get("bus_band"),
                bus_gate=result.get("bus_gate"),
                login_detected_during_hold=((result.get("summaries") or {}).get("sshd") or {}).get(
                    "login_detected_during_hold"),
                registry_and_attempt_parent_unchanged=result.get("registry_and_attempt_parent_unchanged"),
                attempt_parent_empty=result.get("attempt_parent_empty"), inputs=result.get("inputs"),
                safe_input_sha256=result.get("safe_input_sha256"), receipt_manifest_sha256=seal_sha,
                preflight_result_sha256=files["preflight-result.json"],
                failed_checks=[c["name"] for c in result.get("checks", []) if c.get("passed") is False],
                skipped_checks=[c["name"] for c in result.get("checks", []) if c.get("skipped")]), S


def parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 allow_abbrev=False)
    sub = ap.add_subparsers(dest="command", required=True)
    run_ = sub.add_parser("run", allow_abbrev=False)
    for name in ("--bundle", "--runtime-root", "--native", "--corpus", "--corpus-inventory", "--end-evidence",
                 "--repository", "--attempt-parent", "--out"):
        run_.add_argument(name, required=True)
    for name in ("--k4s-manifest-sha256", "--sd1-manifest-sha256", "--end-evidence-sha256", "--bundle-pins-sha256",
                 "--corpus-inventory-sha256"):
        run_.add_argument(name, required=True)
    run_.add_argument("--compare-bundle", help="the attempt bundle (parity except guard.job)")
    run_.add_argument("--compare-bundle-pins-sha256")
    run_.add_argument("--end-job-sha256", help="only once the END-JOB is committed (read-only end_job check)")
    run_.add_argument("--hold-seconds", type=float, required=True)
    run_.add_argument("--block-seconds", type=float, default=30.)
    run_.add_argument("--min-samples", type=int, default=MIN_SAMPLES)
    run_.add_argument("--no-reference-work", dest="reference_work", action="store_false",
                      help="background-only: a NON-QUALIFYING diagnostic (P2-3)")
    check = sub.add_parser("verify-received", allow_abbrev=False)
    check.add_argument("--receive", required=True)
    return ap


def main(argv=None, layers=None):
    a = parser().parse_args(argv)
    if a.command == "verify-received":
        require(not sys.flags.optimize, "verify-received refuses -O")
        si, _ = layers or load_layers()
        require(si.hostname_checked().split(".")[0] == "127x05", "verify-received runs on 127x05")
        summary, S = verify_received(si, a.receive)
        with si.Writer(S, "out") as writer:
            writer.write_json_once("PREFLIGHT-VERIFIED.json", summary)
        print(json.dumps(summary, sort_keys=True))
        return 0 if summary["passed"] else 2
    return run(a, layers=layers)


if __name__ == "__main__":
    raise SystemExit(main())
