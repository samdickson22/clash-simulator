"""K4S END launch & prelaunch gate, 05 side (S7 candidate r4). Review required before any use. Never reads outcomes.

r4 (INTEGRATION-AUDIT-r1 U5, U6, L1, U12):
``build-argv``: writes RUNNER/end-launch/<host>/<attempt>/launch-argv.json exclusively from verified inputs only (the
  pinned RC-6 declaration, the S4 bundle receipts on 05, the END-JOB blob at commit X of the 05 full clone, the
  launching host's pinned PREFLIGHT-VERIFIED identity, the gate constants incl. the U4 host python); the composed argv
  must pass validate_argv first; prints the NUL-joined SHA-256 for ``launch --argv-sha256``.
``prepare-preflight-receive``: creates the EMPTY RUNNER/preflight-received/<host>/<attempt>/ (0700) the preflight push
  wrapper targets and ``launch`` requires.
validate_argv pins the host python, the SD1 / END-evidence SHAs, the bundle's evidence path and the corpus-inventory
SHA (every single-field change refuses). The host program (L1) also confirms the staged runtime (canonical dir,
end_reference.py pin), the native/corpus files, and that HEAD of --repository holds the pinned END-JOB.
BUS-DECISION / REPEAT-RULING validators are factored (check_bus_decision / check_repeat_ruling; templates/).

r2 (safe_input adoption; Sol PKG2 S7-F1..F3, RC-6/7/9, P2-3, C-d): every local read, hash, write and subprocess goes
through the pinned safe_input layer, and every input is at a FIXED role path (no free path arguments):

  RUNNER/end-launch/ROOTS-DECLARATION.json                    RC-6 roots declaration (pinned --roots-sha256)
  RUNNER/end-launch/<host>/<attempt>/launch-argv.json          the pinned launch argv (--argv-sha256 of NUL-joined)
  RUNNER/end-launch/<host>/<attempt>/PREPARE-PROOF.json        END: committed copy of the verifier --prepare proof
  RUNNER/end-launch/<host>/<attempt>/REPEAT-RULING.json   only for a host's second claim in a round
  RUNNER/end-launch/127x04/BUS-DECISION-<preflight>.json       only for an intermediate 04 preflight bus band
  RUNNER/end-launch/127x03/<03 attempt>/ADMISSION.json          04 END: 03's RC-7 close-before-admission record
  RUNNER/preflight-received/<host>/<preflight>/PREFLIGHT-VERIFIED.json  RC-9 (both hosts, schema + provenance)
  RUNNER/end-received/127x03/<03 attempt>/DURABLE-ACK.json      04 END: 03 SEALED complete, C-d satisfied
  RUNNER/end-launch/<host>/<attempt>/LAUNCH-RECEIPT.json        output (exclusive)

``launch``: validates the argv against the RC-6 declaration, the 05 receive directory and the RC-9 prerequisites,
checks that no local ControlMaster is open (``ssh -O check``, rc-checked), then opens exactly ONE ssh session
(si.SSH_OPTIONS: ControlMaster=no, ControlPath=none, BatchMode, StrictHostKeyChecking) running the composed host
program (k4s_end_launch_remote.py with safe_input and k4s_end_host_tool shipped and SHA-checked on the host). It
records the session open/close UTC (05 clock) and writes one launch receipt. It makes no other SSH call.
``admission``: after the verifier ACK (C-d), the sealed guard-admission.json UTC (read with its seal SHA) against the
recorded session close (RC-7); writes ADMISSION.json (exclusive); exit 0 only if closed before admission.
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import re
import sys
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SAFE_INPUT_SHA256 = "806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00"
SAFE_INPUT_FINGERPRINT = "33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592"
HOST_TOOL_SHA256 = "22c441b1db0fb7e1cf31cd259a5e838f375a7a935b3c78f5f5f5891869508647"
QUIET_V3_SHA256 = "a293207e601498d8e7b374a610eddba6f7223e64af34dae00ce52defa30f7c9c"
DETACH_SHA256 = "1648dfdcf85097a54c00b488a5d5570f7c4d0820052a31f89553501084c5b3bb"
WRAPPER_SHA256 = {"end": "65625fc0eac95079c83f2664c5a3244dbe19941cb91075eca5b2093f135679af",        # exit_push r2
                  "preflight": "c9779cfb339b335bb62d09995e6a14e0202a835af337d641a19b25fffe85c580"}  # preflight_push
PREFLIGHT_SHA256 = "c779345116c1bf6c0ab28af8751a36489642c5b9c870326f516361f54bf115f5"
REMOTE_SHA256 = "f5c18122370302f3945b7ae5a96e1d3be8d06a65d38ef09d1211bbf78efeb47d"
K4S_MANIFEST_SHA256 = "74314eda04a7100d7ce10141394282b646723d29d0e7bb3883355d1ef1db6357"
SEED_COMMITS = ("b2f9e25e1002d43cc910a4bb476716cc4cd32623", "ce042b9775f80cb495c327b14a4712730ae95c85")
GUARD_SIDE_FILES = ("allowlist-occurrences.jsonl", "op2-confirmations.jsonl", "ssh-family-occurrences.jsonl",
                    "parent-source-seed-admission.json")
HELPER_PIDS = {"127x03": 2368, "127x04": 2296}                              # r4 quiet-read baseline
END_HOSTS = ("127x03", "127x04")
MIN_PREFLIGHT_HOLD = {"127x03": 120, "127x04": 900}                         # = k4s_end_preflight.MIN_HOLD_SECONDS
MIN_LOADED_SECONDS = {"127x03": 60, "127x04": 900}                          # P2-3 binding duration (measured)
C_D_SECONDS = 1300
RUNNER = "/mpac/sdicks02/k4s-runner/run-r1"
LAUNCH_BASE = RUNNER + "/end-launch"
RECEIVE = {"end": RUNNER + "/end-received", "preflight": RUNNER + "/preflight-received"}
SUPERVISOR_CPU = "61"                                                       # plan.json compute.hosts.*.supervisor_cpu
QUIET_GAP_SECONDS = 30                                                      # two quiet reads 30 s apart
POSTEXEC_SECONDS = 10                                                       # bounded read-back; session closes after
REMOTE_COMMAND = "/usr/bin/python3 -I -B -"
SSH_BINARY = "/usr/bin/ssh"
HOST_PATH = "/usr/bin:/bin"
HOST_BIN = {"bash": "/bin/bash", "systemctl": "/usr/bin/systemctl", "who": "/usr/bin/who", "ps": "/usr/bin/ps",
            "hostname": "/usr/bin/hostname", "env": "/usr/bin/env"}
STAMPS = {"release_upgrade_available": ("/var/lib/ubuntu-release-upgrader", "release-upgrade-available"),
          "updates_available": ("/var/lib/update-notifier", "updates-available"), "apt_lists": ("/var/lib/apt", "lists")}
ENV_REQUIRED = {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
ENV_OPTIONAL = ("PYTHONPATH",)
FORBIDDEN_TOKENS = {"nice", "taskset", "chrt", "ionice", "setsid", "sudo", "renice", "-O", "-OO", "-I"}
END_REQUIRED = ("--bundle", "--runtime-root", "--native", "--corpus", "--corpus-inventory", "--k4s-manifest-sha256",
                "--sd1-manifest-sha256", "--end-evidence", "--end-evidence-sha256", "--repository",
                "--end-job-sha256", "--round", "--out")
PREFLIGHT_REQUIRED = ("--bundle", "--bundle-pins-sha256", "--runtime-root", "--native", "--corpus",
                      "--corpus-inventory", "--corpus-inventory-sha256", "--k4s-manifest-sha256",
                      "--sd1-manifest-sha256", "--end-evidence", "--end-evidence-sha256", "--repository",
                      "--attempt-parent", "--out", "--hold-seconds", "--compare-bundle",
                      "--compare-bundle-pins-sha256")
PREFLIGHT_OPTIONAL = ("--end-job-sha256", "--block-seconds", "--min-samples")
PREFLIGHT_FLAGS = ("--no-reference-work",)
ATTEMPT = {"end": re.compile(r"end-(127x0[34])-r([0-9]{2})-l([0-9]{2})"),
           "preflight": re.compile(r"preflight-(127x0[34])-l([0-9]{2})")}
TOOLS = {"end": "k4s_end_exit_push.sh", "preflight": "k4s_preflight_push.sh"}
ROOTS_SCHEMA = "clasher.k4s.end-roots-declaration.v1"
VERIFIED_SCHEMA = "clasher.k4s.end-preflight-verified.v3"
ACK_SCHEMA = "clasher.k4s.end-durable-ack.v2"
RECEIPT_SCHEMA = "clasher.k4s.end-launch-receipt.v2"
ADMISSION_SCHEMA = "clasher.k4s.end-launch-admission.v2"
SHA = re.compile(r"[0-9a-f]{64}")
CORPUS_INVENTORY_REL = "reports/explore/t1/corpora/corpus-03-a51ea64c/corpora.json"   # K4S manifest corpus.inventory
NATIVE_SHA256 = "44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2"            # = k4s_end_preflight
CORPUS_SHA256 = "a97b1fbf6cbc33a7b65aa5fc91eb0acdd07c922aaf0737620a849163aaadbfe8"            # = k4s_end_preflight
CORPUS_INVENTORY_SHA256 = "3501e2acf444c2f23a5ed9f9471ebcabfc66216b412847c033759c3f4b2cde13"  # = k4s_end_preflight
BUS_PROCEED_MAX, BUS_STOP_MIN = 0.3, 0.7                    # P2-3, = k4s_end_preflight.BUS_PROCEED_MAX/BUS_STOP_MIN
# r4 (INTEGRATION-AUDIT-r1 U5/L1): the END argv values S7 now pins itself, so every single-field change refuses.
# r5 (U4 ruling, COORDINATOR 2026-10-13 10:33Z): the interpreter P' runtime.sh actually executes, run with -B
# (`exec /mpac/sdicks02/repos/clasher/.venv/bin/python -B "$@"`, RUNTIME_SH_REL at P'); NOT the bare uv binary.
HOST_PYTHON = "/mpac/sdicks02/repos/clasher/.venv/bin/python"
RUNTIME_SH_REL = "reports/explore/k4s-confirm/runtime.sh"                 # the frozen launcher HOST_PYTHON is taken from
SD1_MANIFEST_SHA256 = "b8ce7b4c088e275894b9654a85923aacf428656e71433f60ec32bed1ae63ef76"   # = k4s_end_preflight FROZEN_CLOSURE SD1
END_EVIDENCE_SHA256 = "2ab14a3e3f15d41ff80bef31a0a529eddc78a05e61f42bce1e4bfbc4de50a3fd"  # end-evidence.json at P' 98566c03 (plan v2 A6)
END_EVIDENCE_REL = "k4s-end-evidence/end-evidence.json"                   # S4 EVIDENCE_NAME (bundle-relative)
END_REFERENCE_REL = "reports/explore/k4s-confirm/end_reference.py"
END_REFERENCE_SHA256 = "5cb4751e97436dc1208d5a6d6ab7e46c31a31b4ce53ab1d0d289fc4815f96fa9"  # = FROZEN_CLOSURE end_reference.py
END_JOB_REL = "reports/explore/k4s-confirm/end/END-JOB.json"               # frozen end_evidence.END_JOB_PATH
END_JOB_SCHEMA = "clasher.k4s.end-job.v1"
END_GRANTS = ("end-json-exact", "end-claim-exact")
REPO_FULL = RUNNER + "/end-prep/repo-full"                                 # S9 REPO_FULL (05 full clone; read only)
STAGING_BUNDLES = RUNNER + "/end-staging/bundles"                         # S4 outputs on 05 (A2-GO-REQUEST)
ASSEMBLY_SCHEMA = "clasher.k4s.end-fleet-reference-assembly.v2"           # = k4s_end_preflight.ASSEMBLY_SCHEMA
BUNDLE_FILES = ("tiers-pins.json", "tiers-pins.sha256", "assembly-receipt.json")
BUS_DECISION_SCHEMA = "clasher.k4s.end-bus-decision.v1"
REPEAT_RULING_SCHEMA = "clasher.k4s.end-second-attempt-ruling.v1"


class GateRefusal(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise GateRefusal(message)


def optimized():
    return bool(sys.flags.optimize)


def iso(t=None):
    return datetime.datetime.fromtimestamp(time.time() if t is None else t, datetime.timezone.utc) \
        .strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_ms(t):
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def argv_nul(argv):
    return b"".join(x.encode() + b"\0" for x in argv)


# ---------------------------------------------------------------- pinned layers
# r3 (END-FULL-F1): safe_input and the host tool are read ONLY through the canonical bootstrap r1 below
# (bootstrap-r1/k4s_bootstrap_r1.py, verbatim between its BEGIN/END lines; pins outside).
SAFE_INPUT_SIZE = 133606
HOST_TOOL_SIZE = 34444

# ==== BEGIN K4S CANONICAL BOOTSTRAP r1 (bootstrap-r1/k4s_bootstrap_r1.py; paste verbatim, byte for byte) ====
# END-FULL-F1. The only way a K4S END component may read a pinned stdlib-loaded file (its vendored safe_input layer,
# or a host tool) before the shared layer exists. Stdlib only, Python 3.8+, Linux, no assert (holds under -O), no
# single-quote character (so the same text can sit inside a single-quoted shell word). Contract, in order:
#   1. the path is absolute and already normalized (normpath(p) == p; no empty, "." or ".." component, no trailing
#      slash, no control or backslash character). Nothing is canonicalized: realpath is never called;
#   2. every component (ancestors and leaf) passes the safe_input r3 OUTCOME name families (casefolded fullmatch,
#      the same regex literals; conformance-tested against si.outcome_family);
#   3. a component-wise walk from "/": each ancestor is opened O_DIRECTORY|O_NOFOLLOW relative to its parent fd and
#      fstat must say directory (a symlink, a non-directory or a missing ancestor refuses);
#   4. the leaf is fstatat-ed without following (regular, st_nlink == 1, exactly the pinned size) BEFORE it is opened,
#      then opened O_NOFOLLOW|O_NONBLOCK relative to the parent fd and fstat-ed again (same dev/ino, regular,
#      st_nlink == 1, pinned size) BEFORE any byte is read;
#   5. exactly the pinned size is read from THAT descriptor, EOF is confirmed, the SHA-256 must equal the pin, and
#      exactly those bytes are compiled and executed in a fresh module registered under the caller-given name. The
#      code object is compiled under a "<k4s-bootstrap ...>" filename (linecache is given the verified lines) so no
#      traceback, import or inspect call ever re-opens the path after hashing;
#   6. every refusal is `raise refusal(message)`, the caller-chosen refusal convention (an exception class, or a
#      callable returning the exception to raise).
K4S_BOOTSTRAP_RELEASE = "k4s-bootstrap-r1"
K4S_BOOTSTRAP_OUTCOME_FAMILIES = (                      # == safe_input r3 OUTCOME_FAMILIES (literal copy, tested)
    ("games", r"(?:.*[^a-z])?" + r"games" + r"(?:[^a-z].*)?"),
    ("hub-blocks", r"(?:.*[^a-z])?" + r"hub[-_.]?blocks?" + r"(?:[^a-z].*)?"),
    ("complete-json", r".*complete.*\.json.*"),
    ("interference-json", r".*interference.*\.json.*"),
    ("hub-ack-json", r".*hub[-_.]?ack.*\.json.*"),
    ("end-raw-json", r".*end[-_.]?raw.*\.json.*"),
)
K4S_BOOTSTRAP_MAX_SIZE = 1 << 24


def k4s_bootstrap_name_family(component):
    """The OUTCOME family label of one path component (casefolded fullmatch), or None."""
    import re
    folded = component.casefold()
    for label, rx in K4S_BOOTSTRAP_OUTCOME_FAMILIES:
        if re.fullmatch(rx, folded, re.S):
            return label
    return None


def k4s_bootstrap_default_path(module_file, leaf):
    """The sibling `leaf` of `module_file`, made absolute without resolving or normalizing anything: an alias or a
    non-normalized __file__ stays visible, so the walk refuses it."""
    import os
    directory = os.path.dirname(module_file)
    if not directory.startswith("/"):
        directory = os.getcwd() + ("/" + directory if directory else "")
    return directory + "/" + leaf


def k4s_bootstrap_read_verified(path, sha256, size, refusal):
    """Steps 1-5 up to the hash: return exactly the pinned bytes, or raise refusal(message) having read nothing that
    fails a name, walk or descriptor gate."""
    import hashlib
    import os
    import stat

    def refused(reason):
        return refusal("k4s bootstrap refused: " + reason + ": " + repr(path))

    if not isinstance(sha256, str) or len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
        raise refused("the SHA-256 pin is not 64 lowercase hex digits")
    if type(size) is not int or not 0 < size <= K4S_BOOTSTRAP_MAX_SIZE:
        raise refused("the size pin is not an int in 1..%d" % K4S_BOOTSTRAP_MAX_SIZE)
    if (not isinstance(path, str) or not path.startswith("/") or path.startswith("//") or path.endswith("/")
            or os.path.normpath(path) != path):
        raise refused("not an absolute normalized path")
    if "\\" in path or any(ord(c) < 32 or ord(c) == 127 for c in path):
        raise refused("control or backslash character in the path")
    parts = path[1:].split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise refused("empty, . or .. component")
    for p in parts:
        family = k4s_bootstrap_name_family(p)
        if family is not None:
            raise refused("outcome name family " + family + " in component " + repr(p))
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise refused("/ is not a directory")
        for name in parts[:-1]:
            try:
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            except OSError as error:
                raise refused("ancestor " + repr(name) + " is a symlink, not a directory or missing ("
                              + os.strerror(error.errno) + ")")
            previous, fd = fd, child
            os.close(previous)
            if not stat.S_ISDIR(os.fstat(fd).st_mode):
                raise refused("ancestor " + repr(name) + " is not a directory")
        leaf = parts[-1]
        try:
            before = os.stat(leaf, dir_fd=fd, follow_symlinks=False)
        except OSError as error:
            raise refused("leaf cannot be inspected (" + os.strerror(error.errno) + ")")
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != size:
            raise refused("leaf is not a single-link regular file of the pinned size %d" % size)
        try:
            leaf_fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY | os.O_CLOEXEC,
                              dir_fd=fd)
        except OSError as error:
            raise refused("leaf cannot be opened without following (" + os.strerror(error.errno) + ")")
        try:
            info = os.fstat(leaf_fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size != size
                    or (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino)):
                raise refused("opened leaf is not the inspected single-link regular file of the pinned size")
            chunks, left = [], size
            while left > 0:
                chunk = os.read(leaf_fd, left)
                if not chunk:
                    raise refused("leaf shrank while read")
                chunks.append(chunk)
                left -= len(chunk)
            if os.read(leaf_fd, 1) != b"":
                raise refused("leaf grew while read")
        finally:
            os.close(leaf_fd)
    finally:
        os.close(fd)
    data = b"".join(chunks)
    if len(data) != size or hashlib.sha256(data).hexdigest() != sha256:
        raise refused("bytes are not the pinned SHA-256 " + sha256)
    return data


def k4s_bootstrap_exec(data, path, sha256, module_name):
    """Step 5 tail: compile and execute exactly `data` (already verified) in a fresh module named `module_name`."""
    import linecache
    import sys
    import types
    filename = "<k4s-bootstrap sha256=" + sha256 + " " + path + ">"
    linecache.cache[filename] = (len(data), None, data.decode("utf-8", "replace").splitlines(True), filename)
    code = compile(data, filename, "exec", dont_inherit=True)
    module = types.ModuleType(module_name)
    module.__file__ = path
    module.__k4s_bootstrap__ = (K4S_BOOTSTRAP_RELEASE, path, sha256, len(data))
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        exec(code, module.__dict__)
    except BaseException:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise
    return module


def k4s_bootstrap_load(path, sha256, size, module_name, refusal):
    """Read `path` through the full contract and execute exactly the verified bytes as module `module_name`."""
    data = k4s_bootstrap_read_verified(path, sha256, size, refusal)
    return k4s_bootstrap_exec(data, path, sha256, module_name)
# ==== END K4S CANONICAL BOOTSTRAP r1 ====


def load_layers(directory=None):
    """(safe_input, k4s_end_host_tool) through the canonical bootstrap; `directory` (tests) replaces the default
    sibling location (an absolute normalized directory)."""
    def path(leaf):
        return k4s_bootstrap_default_path(__file__, leaf) if directory is None else str(directory) + "/" + leaf
    si = k4s_bootstrap_load(path("safe_input.py"), SAFE_INPUT_SHA256, SAFE_INPUT_SIZE, "safe_input", GateRefusal)
    require(si.constants_fingerprint() == SAFE_INPUT_FINGERPRINT, "safe_input fingerprint differs from the pin")
    tool = k4s_bootstrap_load(path("k4s_end_host_tool.py"), HOST_TOOL_SHA256, HOST_TOOL_SIZE, "k4s_end_host_tool",
                              GateRefusal)
    tool.check_safe_input(si)
    return si, tool


# ---------------------------------------------------------------- RC-6 roots declaration

def validate_roots(si, doc):
    """RC-6: per host the k4s-end-r1 base (si.END_BASES), runtime-<commit12>, bundles (path, tiers-pins SHA, guard
    job under the separate Q4 guard parent), repository, attempts, preflight, tools; exact keys, both hosts."""
    require(isinstance(doc, dict) and set(doc) == {"schema", "commit", "hosts"} and doc["schema"] == ROOTS_SCHEMA
            and re.fullmatch(r"[0-9a-f]{40}", str(doc["commit"])), "RC-6 declaration malformed")
    hosts = doc["hosts"]
    require(isinstance(hosts, dict) and sorted(hosts) == list(END_HOSTS), "RC-6 declaration must name 127x03/127x04")
    for host, d in hosts.items():
        base = si.END_BASES[host]
        require(isinstance(d, dict) and set(d) == {"base", "runtime", "bundles", "repository", "attempts", "preflight",
                                                   "tools", "guard_parent"}, "RC-6 %s: keys" % host)
        require(d["base"] == base and d["repository"] == base + "/repository" and d["attempts"] == base + "/attempts"
                and d["preflight"] == base + "/preflight" and d["tools"] == base + "/tools"
                and d["guard_parent"] == si.Q4_GUARD_PARENTS[host], "RC-6 %s: roots differ from k4s-end-r1/Q4" % host)
        require(os.path.dirname(d["runtime"]) == base
                and re.fullmatch(r"runtime-[0-9a-f]{12}", os.path.basename(d["runtime"])), "RC-6 %s: runtime" % host)
        require(isinstance(d["bundles"], dict) and d["bundles"], "RC-6 %s: bundles" % host)
        for name, b in d["bundles"].items():
            require(isinstance(b, dict) and set(b) == {"path", "tiers_pins_sha256", "guard_job"}
                    and b["path"] == base + "/bundles/" + name and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name)
                    and SHA.fullmatch(str(b["tiers_pins_sha256"]))
                    and os.path.dirname(b["guard_job"]) == d["guard_parent"]
                    and si.GUARD_JOB_NAME.fullmatch(os.path.basename(b["guard_job"])),
                    "RC-6 %s: bundle %s" % (host, name))
        jobs = [b["guard_job"] for b in d["bundles"].values()]
        require(len(set(jobs)) == len(jobs), "RC-6 %s: a guard job is shared by two bundles" % host)
    return hosts


def bundle_by_path(roots, host, path):
    for b in roots[host]["bundles"].values():
        if b["path"] == path:
            return b
    raise GateRefusal("Not a declared RC-6 bundle for %s: %s" % (host, path))


# ---------------------------------------------------------------- argv structure

def options(tokens, values, flags):
    """--name value pairs (and value-less flags) exactly once each; no abbreviation, no =-form."""
    out, i = {}, 0
    while i < len(tokens):
        name = tokens[i]
        require(name.startswith("--") and "=" not in name, "Unexpected argv token: " + name)
        require(name not in out, "Repeated option: " + name)
        if name in flags:
            out[name] = True
            i += 1
            continue
        require(name in values and i + 1 < len(tokens), "Unknown or valueless option: " + name)
        value = tokens[i + 1]
        require(not value.startswith("--"), "Option value looks like an option: " + name)
        out[name] = value
        i += 2
    return out


def validate_argv(si, argv, kind, host, attempt, roots, diagnostic=False):
    """Structure of the pinned launch argv against the RC-6 declaration; returns what the host gate needs."""
    require(kind in ATTEMPT and host in END_HOSTS, "Unknown kind/host")
    require(isinstance(argv, list) and all(isinstance(x, str) and x and "\0" not in x for x in argv),
            "argv must be a list of non-empty strings")
    d = roots[host]
    m = ATTEMPT[kind].fullmatch(attempt)
    require(m is not None and m.group(1) == host, "Attempt name is not a %s name for %s" % (kind, host))
    require(len(argv) > 20, "argv too short")
    require(argv[:6] == ["nice", "-n", "10", "taskset", "-c", SUPERVISOR_CPU],
            "argv must start with the frozen inner nice -n 10 taskset -c 61 (no outer prefix)")
    parent = d["attempts"] if kind == "end" else d["preflight"]
    job = parent + "/" + attempt
    require(argv[6:13] == ["bash", d["tools"] + "/detach.sh", job + "/detach.log", job + "/detach.json", "bash",
                           d["tools"] + "/" + TOOLS[kind], job],
            "argv must be: bash <tools>/detach.sh <job>/detach.log <job>/detach.json bash <tools>/<wrapper> <job>")
    m_argv = argv[13:]
    require(m_argv[0] == "env", "Measurement argv must start with env")
    i, env = 1, {}
    while i < len(m_argv) and "=" in m_argv[i] and not m_argv[i].startswith("/"):
        key, value = m_argv[i].split("=", 1)
        require(key not in env, "Repeated env assignment")
        env[key] = value
        i += 1
    require(all(env.get(k) == v for k, v in ENV_REQUIRED.items()) and set(env) <= set(ENV_REQUIRED) | set(ENV_OPTIONAL),
            "Environment must be exactly the single-thread pins (+ optional PYTHONPATH)")
    require(not FORBIDDEN_TOKENS & set(m_argv), "Measurement argv carries a priority/scheduler/optimizer prefix")
    python, flag, script = m_argv[i:i + 3]
    require(os.path.isabs(python) and os.path.basename(python).startswith("python") and flag == "-B",
            "Interpreter must be an absolute python run with exactly -B")
    require(python == HOST_PYTHON, "Interpreter must be the declared host python " + HOST_PYTHON + " (U4)")
    if kind == "end":
        opts = options(m_argv[i + 3:], END_REQUIRED, ())
        require(set(opts) == set(END_REQUIRED), "END argv must give exactly the required options")
        require(opts["--runtime-root"] == d["runtime"]
                and script == d["runtime"] + "/reports/explore/k4s-confirm/end_reference.py",
                "END script must be the declared runtime's end_reference.py")
        require(re.fullmatch(r"0|[1-9][0-9]?", opts["--round"]) and int(opts["--round"]) == int(m.group(2)),
                "--round must match the attempt name")
        require(opts["--k4s-manifest-sha256"] == K4S_MANIFEST_SHA256, "--k4s-manifest-sha256 is not 74314eda")
        bundle = bundle_by_path(roots, host, opts["--bundle"])
        g = si.GUARD_JOB_NAME.fullmatch(os.path.basename(bundle["guard_job"]))
        require(g.group(1).startswith("rd%02d-a" % int(opts["--round"])),
                "END bundle must use a -rdRR-aNN guard job of this round")
        pins = {d["tools"] + "/detach.sh": DETACH_SHA256, d["tools"] + "/" + TOOLS[kind]: WRAPPER_SHA256["end"]}
        marker, round_index = "end_reference.py", int(opts["--round"])
    else:
        require(script == d["tools"] + "/k4s_end_preflight.py" and m_argv[i + 3:i + 4] == ["run"],
                "Preflight must run the staged k4s_end_preflight.py run")
        opts = options(m_argv[i + 4:], PREFLIGHT_REQUIRED + PREFLIGHT_OPTIONAL, PREFLIGHT_FLAGS)
        require(set(PREFLIGHT_REQUIRED) <= set(opts), "Preflight argv lacks a required option")
        require(opts["--runtime-root"] == d["runtime"], "--runtime-root must be the declared runtime")
        require(opts["--attempt-parent"] == d["attempts"], "--attempt-parent must be the declared parent")
        require(opts["--k4s-manifest-sha256"] == K4S_MANIFEST_SHA256, "--k4s-manifest-sha256 is not 74314eda")
        hold = float(opts["--hold-seconds"])
        require(hold >= MIN_PREFLIGHT_HOLD[host], "Preflight hold below the minimum (P2-3/RC-2)")
        require(int(opts.get("--min-samples", "60")) >= 60, "--min-samples below 60")
        require("--no-reference-work" not in opts or diagnostic,
                "--no-reference-work is a NON-QUALIFYING diagnostic: requires --diagnostic-preflight (P2-3)")
        bundle = bundle_by_path(roots, host, opts["--bundle"])
        compare = bundle_by_path(roots, host, opts["--compare-bundle"])
        require(opts["--bundle-pins-sha256"] == bundle["tiers_pins_sha256"]
                and opts["--compare-bundle-pins-sha256"] == compare["tiers_pins_sha256"],
                "Preflight bundle pins differ from the RC-6 declaration")
        require(si.GUARD_JOB_NAME.fullmatch(os.path.basename(bundle["guard_job"])).group(1).startswith("pf")
                and si.GUARD_JOB_NAME.fullmatch(os.path.basename(compare["guard_job"])).group(1).startswith("rd"),
                "Preflight bundle needs a -pfNN guard job and its compare bundle a -rdRR-aNN one")
        pins = {d["tools"] + "/detach.sh": DETACH_SHA256, d["tools"] + "/" + TOOLS[kind]: WRAPPER_SHA256["preflight"],
                d["tools"] + "/k4s_end_preflight.py": PREFLIGHT_SHA256}
        marker, round_index = "k4s_end_preflight.py", None
    require(opts["--out"] == job + "/" + attempt, "--out must be <job>/<attempt>")
    require(opts["--corpus-inventory"] == d["runtime"] + "/" + CORPUS_INVENTORY_REL,
            "--corpus-inventory must be the declared runtime's " + CORPUS_INVENTORY_REL)
    require(opts["--end-evidence"].startswith(opts["--bundle"] + "/") and ".." not in opts["--end-evidence"].split("/"),
            "--end-evidence must be inside the declared bundle")
    require(opts["--end-evidence"] == opts["--bundle"] + "/" + END_EVIDENCE_REL,
            "--end-evidence must be the bundle's " + END_EVIDENCE_REL + " (S4 evidence copy)")
    require(opts["--end-evidence-sha256"] == END_EVIDENCE_SHA256,
            "--end-evidence-sha256 is not the END evidence of record (P' end-evidence.json)")
    require(opts["--sd1-manifest-sha256"] == SD1_MANIFEST_SHA256, "--sd1-manifest-sha256 is not the frozen SD1 pin")
    require(kind == "end" or opts["--corpus-inventory-sha256"] == CORPUS_INVENTORY_SHA256,
            "--corpus-inventory-sha256 is not the K4S corpus inventory")
    job_sha = opts.get("--end-job-sha256")
    require(job_sha is None or SHA.fullmatch(job_sha), "--end-job-sha256 must be a SHA-256")
    for label in ("--native", "--corpus"):
        path = opts[label]
        require(path.startswith(d["base"] + "/") and os.path.normpath(path) == path and not any(
            path.startswith(d[k] + "/") for k in ("attempts", "preflight", "repository", "tools")),
            label + " must be a K4S-owned file under the declared base")
    require(opts["--repository"] == d["repository"], "--repository must be the declared clone")
    pins.update({d["tools"] + "/safe_input.py": SAFE_INPUT_SHA256, d["tools"] + "/k4s_end_host_tool.py": HOST_TOOL_SHA256})
    return dict(job=job, attempt=attempt, attempt_parent=parent, measurement_argv=m_argv, python_marker=marker,
                file_pins=pins, wrapper=d["tools"] + "/" + TOOLS[kind], options=opts, round=round_index,
                bundle=bundle, mode="diagnostic" if "--no-reference-work" in opts else "binding", end_job_sha256=job_sha)


# ---------------------------------------------------------------- local inputs (fixed role paths)

def local_policy(si, a, extra_read=()):
    """The one 05 Policy of a launch: tools (this package), launch inputs, receive dirs; all exact names."""
    host, attempt = a.host, a.attempt
    mine = "%s/%s/" % (host, attempt)
    launch_names = ["ROOTS-DECLARATION.json", mine + "launch-argv.json", mine + "PREPARE-PROOF.json",
                    mine + "REPEAT-RULING.json"] + [n for n in extra_read if not n.startswith("/")]
    R = si.Role
    pf = tuple(n[len("/pf/"):] for n in extra_read if n.startswith("/pf/"))
    return si.Policy("127x05", ([R("pf-recv", RECEIVE["preflight"], "read", 64 << 20, exact=pf)] if pf else []) + [
        R("tools", HERE, "read", 1 << 23, exact=("k4s_end_launch_remote.py", "quiet-read-v3.cmd", "safe_input.py",
                                                 "k4s_end_host_tool.py", "k4s_end_launch_gate.py")),
        R("launch", LAUNCH_BASE, "read", 64 << 20, exact=tuple(launch_names)),
        R("launch-out", LAUNCH_BASE, "write", 64 << 20, exact=(mine + "LAUNCH-RECEIPT.json",)),
        R("end-recv", RECEIVE["end"], "read", 64 << 20,
          exact=(mine + "PREPARED.json",) + tuple(n[len("/end/"):] for n in extra_read if n.startswith("/end/"))),
        R("receive-dir", RECEIVE[a.kind] + "/" + host + "/" + attempt, "read", 1, patterns=("*",))])


def pinned_json(si, P, role, rel, sha, label):
    require(isinstance(sha, str) and SHA.fullmatch(sha), label + ": a SHA-256 pin is required")
    return si.read_json(P, role, rel, 64 << 20, expected_sha256=sha)


def check_receive(si, tool, P, a):
    """05 receive directory: preflight -> empty; END -> only PREPARED.json, equal to the committed prepare proof."""
    names = tool.names_only(si, P, "receive-dir")
    if a.kind == "preflight":
        require(names == [], "Preflight receive directory must be empty")
        return dict(receive=RECEIVE[a.kind] + "/" + a.host + "/" + a.attempt, empty=True)
    require(names == ["PREPARED.json"], "END receive directory must hold only PREPARED.json")
    mine = "%s/%s/" % (a.host, a.attempt)
    proof = pinned_json(si, P, "launch", mine + "PREPARE-PROOF.json", a.prepare_proof_sha256, "Prepare proof")
    require(si.read_json(P, "end-recv", mine + "PREPARED.json", 1 << 16) == proof,
            "Prepare proof differs from PREPARED.json")
    root = RECEIVE["end"] + "/" + a.host + "/" + a.attempt
    require(proof.get("receive") == root and proof.get("created_empty") is True and proof.get("utc", "~") < iso(),
            "Prepare proof does not name this receive directory or postdates now")
    return dict(receive=root, prepare_proof_sha256=a.prepare_proof_sha256, prepared_utc=proof["utc"])


def parse_pf(specs):
    out = {}
    for spec in specs or []:
        host, _, rest = spec.partition("=")
        attempt, _, digest = rest.partition(":")
        require(host in END_HOSTS and host not in out and ATTEMPT["preflight"].fullmatch(attempt)
                and ATTEMPT["preflight"].fullmatch(attempt).group(1) == host and SHA.fullmatch(digest),
                "--preflight-verified HOST=preflight-HOST-lNN:SHA256")
        out[host] = (attempt, digest)
    return out


def extra_reads(a):
    """Exact names of the RC-9 inputs this launch will read (built before the Policy)."""
    names = []
    for host, (attempt, _) in parse_pf(a.preflight_verified).items():
        names += ["/pf/%s/%s/PREFLIGHT-VERIFIED.json" % (host, attempt),
                  "/pf/%s/%s/preflight/receipt-manifest.json" % (host, attempt),
                  "/pf/%s/%s/preflight/preflight-result.json" % (host, attempt)]
        names.append("127x04/BUS-DECISION-%s.json" % attempt)
    if a.prior_03:
        attempt = a.prior_03.split(":")[0]
        names += ["/end/127x03/%s/DURABLE-ACK.json" % attempt,
                  "/end/127x03/%s/durable-measurement/receipt-manifest.json" % attempt,
                  "127x03/%s/ADMISSION.json" % attempt, "127x03/%s/LAUNCH-RECEIPT.json" % attempt]
    return names


def preflight_ok(si, P, host, attempt, digest, roots, shape, a):
    """RC-9 / P2-3: the specific verified receipt under its declared role path, schema and provenance checked."""
    base = "%s/%s/" % (host, attempt)
    v = pinned_json(si, P, "pf-recv", base + "PREFLIGHT-VERIFIED.json", digest, "Preflight verification " + host)
    d = roots[host]
    require(v.get("schema") == VERIFIED_SCHEMA and v.get("scope") == "K4S-END-PREFLIGHT" and v.get("host") == host
            and v.get("attempt") == attempt and v.get("receive") == RECEIVE["preflight"] + "/" + host + "/" + attempt,
            "Preflight %s: not a verified K4S-END-PREFLIGHT receipt for this host/attempt" % host)
    require(si.sha256_input(P, "pf-recv", base + "preflight/receipt-manifest.json")["sha256"]
            == v.get("receipt_manifest_sha256")
            and si.sha256_input(P, "pf-recv", base + "preflight/preflight-result.json")["sha256"]
            == v.get("preflight_result_sha256"), "Preflight %s: sealed receipt differs from its verification" % host)
    require(v.get("passed") is True and v.get("status") == "passed" and v.get("failed_checks") == []
            and v.get("registry_and_attempt_parent_unchanged") is True and v.get("attempt_parent_empty") is True,
            "Preflight %s did not pass" % host)
    require(v.get("mode") == "binding" and v.get("qualifying") is True,
            "Preflight %s is not a BINDING qualifying run (background-only = diagnostic, P2-3)" % host)
    load, duration = v.get("load") or {}, v.get("duration") or {}
    require(load.get("reference_slot_work") is True and (load.get("reference_slot_states_worked") or 0) > 0
            and load.get("background_slots_ready") == load.get("background_slots_expected")
            == (load.get("slot_count") or 0) - 1, "Preflight %s: not the agreed full reference load" % host)
    require((duration.get("loaded_seconds_measured") or 0) >= MIN_LOADED_SECONDS[host],
            "Preflight %s: loaded duration below the agreed minimum" % host)
    require(host != "127x04" or v.get("login_detected_during_hold") is False, "Preflight 04: login during the hold")
    inputs = v.get("inputs") or {}
    require(inputs.get("runtime_root") == d["runtime"] and inputs.get("repository") == d["repository"]
            and inputs.get("k4s_manifest_sha256") == K4S_MANIFEST_SHA256 and v.get("safe_input_sha256") ==
            SAFE_INPUT_SHA256, "Preflight %s: runtime/repository/manifest/layer binding differs" % host)
    b = bundle_by_path(roots, host, inputs.get("bundle"))
    c = bundle_by_path(roots, host, inputs.get("compare_bundle"))
    require(inputs.get("bundle_pins_sha256") == b["tiers_pins_sha256"] and inputs.get("guard_job") == b["guard_job"]
            and inputs.get("compare_bundle_pins_sha256") == c["tiers_pins_sha256"],
            "Preflight %s: bundle/guard binding differs from RC-6" % host)
    identity = launch_identity(v, d, host)
    binding = None
    if host == a.host and a.kind == "end":
        o = shape["options"]
        require(inputs.get("end_evidence_sha256") == o["--end-evidence-sha256"]
                and inputs.get("sd1_manifest_sha256") == o["--sd1-manifest-sha256"],
                "Preflight %s: evidence/SD1 binding differs from this END argv" % host)
        require(inputs.get("native") == identity["native"] == o["--native"]
                and inputs.get("corpus") == identity["corpus"] == o["--corpus"]
                and inputs.get("corpus_inventory") == identity["corpus_inventory"] == o["--corpus-inventory"],
                "Preflight %s: native/corpus/corpus-inventory differ from this END argv (F5)" % host)
        binding = bundle_binding(v, inputs, shape["bundle"], host)
    bus = bus_evidence(v, host, duration)
    if host == "127x04":
        if v.get("bus_band") == "coordinator-decision":
            rel = "127x04/BUS-DECISION-%s.json" % attempt
            decision = check_bus_decision(pinned_json(si, P, "launch", rel, a.bus_decision_sha256, "Bus decision"),
                                          attempt, v.get("receipt_manifest_sha256"))
            bus["coordinator_decision"] = dict(sha256=a.bus_decision_sha256, ref=decision["coordinator_ref"])
        else:
            require(v.get("bus_band") == "proceed",
                    "04 loaded bus band %r: STOP before any claim (P2-3)" % v.get("bus_band"))
    return dict(attempt=attempt, sha256=digest, receipt_manifest_sha256=v["receipt_manifest_sha256"], bus=bus,
                loaded_seconds=duration.get("loaded_seconds_measured"), identity=identity, bundle_binding=binding)


def check_bus_decision(decision, attempt, receipt_manifest_sha256):
    """U12: BUS-DECISION-<preflight>.json (templates/BUS-DECISION.template.json): a coordinator 'proceed' ruling for
    exactly this 04 preflight, bound to its sealed receipt manifest."""
    require(isinstance(decision, dict) and decision.get("schema") == BUS_DECISION_SCHEMA
            and decision.get("decision") == "proceed" and decision.get("preflight_attempt") == attempt
            and decision.get("receipt_manifest_sha256") == receipt_manifest_sha256
            and isinstance(decision.get("coordinator_ref"), str) and decision["coordinator_ref"].strip(),
            "Bus decision is not a coordinator 'proceed' ruling for this 04 preflight")
    return decision


def check_repeat_ruling(ruling, host, attempt):
    """U12: REPEAT-RULING.json (templates/REPEAT-RULING.template.json): the coordinator ruling that admits a host's
    second claim in a round, for exactly this host and attempt."""
    require(isinstance(ruling, dict) and ruling.get("schema") == REPEAT_RULING_SCHEMA and ruling.get("host") == host
            and ruling.get("attempt") == attempt and isinstance(ruling.get("coordinator_ref"), str)
            and ruling["coordinator_ref"].strip(), "Second-attempt ruling is not for this host/attempt")
    return ruling


def launch_identity(v, d, host):
    """F5(a): the identities the qualifying preflight verified (frozen_identity) are the K4S END identities, and its
    native/corpus/corpus-inventory paths are the ones it actually used (inputs) under this host's declared roots."""
    inputs, ident = v.get("inputs") or {}, v.get("identity")
    require(isinstance(ident, dict) and ident.get("native_sha256") == NATIVE_SHA256
            and ident.get("corpus_sha256") == CORPUS_SHA256
            and ident.get("corpus_inventory_sha256") == inputs.get("corpus_inventory_sha256") == CORPUS_INVENTORY_SHA256,
            "Preflight %s: native/corpus/corpus-inventory identity is missing or not the K4S END identity" % host)
    require(ident.get("native") == inputs.get("native") and ident.get("corpus") == inputs.get("corpus")
            and ident.get("corpus_inventory") == inputs.get("corpus_inventory") == d["runtime"] + "/" + CORPUS_INVENTORY_REL
            and all(isinstance(ident.get(k), str) and ident[k].startswith(d["base"] + "/") for k in ("native", "corpus")),
            "Preflight %s: identity paths differ from its inputs / declared roots" % host)
    return dict(native=ident["native"], native_sha256=ident["native_sha256"], corpus=ident["corpus"],
                corpus_sha256=ident["corpus_sha256"], corpus_inventory=ident["corpus_inventory"],
                corpus_inventory_sha256=ident["corpus_inventory_sha256"])


def bundle_binding(v, inputs, bundle, host):
    """F5(b): the END attempt bundle IS the preflight's compare bundle (exact: path and RC-6 tiers-pins SHA), or a
    later attempt bundle of the same lineage whose ONLY admissible difference is its fresh guard job. The preflight's
    own and compare bundles carry one guard-job-free manifest digest (S5 bundle_parity); the host program recomputes
    that digest from the attempt bundle's pinned tiers-pins.json and refuses on any difference (equivalence verified
    from bytes on the host, not assumed on 05). Returns the binding the host must verify."""
    ids = v.get("bundle_identity") or {}
    digest = ids.get("bundle_sans_guard_sha256")
    require(isinstance(digest, str) and SHA.fullmatch(digest) and ids.get("compare_bundle_sans_guard_sha256") == digest,
            "Preflight %s: bundle identity missing, or its compare bundle differs beyond guard.job" % host)
    exact = (bundle["path"] == inputs.get("compare_bundle")
             and bundle["tiers_pins_sha256"] == inputs.get("compare_bundle_pins_sha256"))
    if not exact:
        require(bundle["path"] != inputs.get("bundle") and bundle["guard_job"] != inputs.get("guard_job"),
                "Preflight %s: the END bundle may not be the preflight's own bundle/guard job" % host)
    return dict(mode="exact" if exact else "guard-job-equivalent", bundle=bundle["path"],
                tiers_pins_sha256=bundle["tiers_pins_sha256"], guard_job=bundle["guard_job"],
                preflight_compare_bundle=inputs.get("compare_bundle"), bundle_sans_guard_sha256=digest,
                verified_on_host=True)


def bus_band(percent):
    """P2-3 band (= k4s_end_preflight.band)."""
    return "proceed" if percent <= BUS_PROCEED_MAX else "stop" if percent >= BUS_STOP_MIN else "coordinator-decision"


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def bus_evidence(v, host, duration):
    """F5(d): the numeric loaded-bus evidence exists, is finite, is internally consistent (percent = 100 ticks / hz /
    seconds over the measured loaded span) and yields exactly the recorded band; the gate field matches the host."""
    loaded = v.get("bus_cumulative_loaded")
    require(isinstance(loaded, dict), "Preflight %s: loaded-bus evidence missing" % host)
    pct, secs, ticks, hz = (loaded.get(k) for k in ("percent", "seconds", "cpu_ticks", "hz"))
    require(finite(pct) and pct >= 0 and finite(secs) and secs > 0 and finite(ticks) and ticks >= 0
            and type(hz) is int and hz > 0, "Preflight %s: loaded-bus evidence missing or not finite" % host)
    require(abs(pct - 100. * ticks / hz / secs) <= 1e-9 * max(1., abs(pct))
            and secs == duration.get("loaded_seconds_measured"),
            "Preflight %s: loaded-bus percent inconsistent with its ticks/hz/span" % host)
    require(v.get("bus_band") == bus_band(pct),
            "Preflight %s: recorded bus band %r is not the P2-3 band of %.4f %%" % (host, v.get("bus_band"), pct))
    require(v.get("bus_gate") == (v["bus_band"] if host == "127x04" else "not-gated-on-" + host),
            "Preflight %s: bus gate/band mismatch" % host)
    return dict(band=v["bus_band"], gate=v["bus_gate"], cumulative_loaded=loaded, percent=pct)


def prerequisites(si, P, a, roots, shape):
    """RC-9: both host preflights verified binding/qualifying (bus gate on 04) before any claim; the 04 END only
    after 03's SEALED complete ACK verified at >= exit + 1300 s (C-d) and its RC-7 admission record."""
    if a.kind != "end":
        return {}
    pf = parse_pf(a.preflight_verified)
    require(sorted(pf) == list(END_HOSTS), "Both host preflights must be given (RC-9)")
    out = dict(preflights={h: preflight_ok(si, P, h, att, dig, roots, shape, a) for h, (att, dig) in pf.items()})
    if a.host == "127x04":
        require(a.prior_03, "04 END requires 03's verified complete seal (RC-9)")
        attempt, ack_sha, admission_sha = (a.prior_03.split(":") + ["", ""])[:3]
        require(ATTEMPT["end"].fullmatch(attempt) and ATTEMPT["end"].fullmatch(attempt).group(1) == "127x03",
                "--prior-03 ATTEMPT:ACK_SHA:ADMISSION_SHA")
        ack = pinned_json(si, P, "end-recv", "127x03/%s/DURABLE-ACK.json" % attempt, ack_sha, "03 DURABLE-ACK")
        require(ack.get("schema") == ACK_SCHEMA and ack.get("host") == "127x03" and ack.get("attempt") == attempt
                and ack.get("classification") == "SEALED" and ack.get("status") == "complete"
                and ack.get("ack_allowed") is True, "03 seal is not SEALED complete + ACKed")
        require(ack.get("c_d_satisfied") is True and isinstance(ack.get("verified_epoch"), (int, float))
                and isinstance(ack.get("exit_epoch"), (int, float))
                and ack["verified_epoch"] >= ack["exit_epoch"] + C_D_SECONDS, "03 ACK was not verified at >= C-d")
        require(si.sha256_input(P, "end-recv", "127x03/%s/durable-measurement/receipt-manifest.json" % attempt)[
            "sha256"] == ack.get("receipt_manifest_sha256"), "03 sealed receipt differs from its ACK")
        adm = pinned_json(si, P, "launch", "127x03/%s/ADMISSION.json" % attempt, admission_sha, "03 admission")
        require(adm.get("schema") == ADMISSION_SCHEMA and adm.get("host") == "127x03" and adm.get("attempt") == attempt
                and adm.get("closed_before_admission") is True, "03 launch session did not close before admission")
        out["prior_03"] = dict(attempt=attempt, ack_sha256=ack_sha, admission_sha256=admission_sha,
                               verified_epoch=ack["verified_epoch"], exit_epoch=ack["exit_epoch"],
                               **lineage_03(si, P, a, shape, pf, attempt, ack, ack_sha, adm))
    return out


def lineage_03(si, P, a, shape, pf, attempt, ack, ack_sha, adm):
    """F5(c): 03's completion belongs to THIS round and THIS launch lineage: its attempt name names the round being
    launched; the RC-7 admission record was made from this ACK and 03's launch receipt; that launch receipt (read with
    the SHA the ACK binds) is a launched 03 END attempt of this round, issued under the same RC-6 declaration and on
    the same two qualifying preflight receipts as this 04 launch."""
    round_index = shape["round"]
    require(int(ATTEMPT["end"].fullmatch(attempt).group(2)) == round_index,
            "03 attempt %s is not of round %02d being launched" % (attempt, round_index))
    receipt_sha = ack.get("launch_receipt_sha256")
    require(isinstance(receipt_sha, str) and SHA.fullmatch(receipt_sha) and adm.get("kind") == "end"
            and adm.get("verified_sha256") == ack_sha and adm.get("launch_receipt_sha256") == receipt_sha,
            "03 admission record was not made from this ACK and its launch receipt")
    launch_ = pinned_json(si, P, "launch", "127x03/%s/LAUNCH-RECEIPT.json" % attempt, receipt_sha, "03 launch receipt")
    argv = launch_.get("measurement_argv") or []
    rounds = [argv[i + 1] for i in range(len(argv) - 1) if argv[i] == "--round"]
    require(launch_.get("schema") == RECEIPT_SCHEMA and launch_.get("kind") == "end" and launch_.get("host") == "127x03"
            and launch_.get("attempt") == attempt and launch_.get("launched") is True
            and rounds == [str(round_index)], "03 launch receipt is not a launched 03 END attempt of this round")
    require(launch_.get("roots_sha256") == a.roots_sha256,
            "03 was launched under a different RC-6 roots declaration")
    used = (launch_.get("prerequisites") or {}).get("preflights") or {}
    require(sorted(used) == list(END_HOSTS) and all(
        isinstance(used[h], dict) and used[h].get("attempt") == pf[h][0] and used[h].get("sha256") == pf[h][1]
        for h in END_HOSTS), "03 was launched on different qualifying preflights than this 04 launch")
    return dict(round=round_index, launch_receipt_sha256=receipt_sha, roots_sha256=a.roots_sha256, lineage=True)


def local_controlmaster(si, host):
    """No multiplexing master to the host on 05 (ssh -O check talks only to a local control socket); rc-checked:
    only rc 255 (no master) proceeds."""
    try:
        r = si.run_checked([SSH_BINARY, "-O", "check", host], 30, 4096, env={"LC_ALL": "C"},
                           env_allow=("HOME", "USER"), ok_rcs=(255,))
    except si.Refusal as error:
        raise GateRefusal("A ControlMaster to %s may be open on 05 (ssh -O check: %s); close it first" % (host, error))
    return dict(ssh_O_check_rc=r.rc, stderr=r.stderr.decode("utf-8", "replace").strip()[-200:])


PRELUDE = '''import base64, hashlib, json, sys, types
def _shipped(name, b64, sha):
    data = base64.b64decode(b64)
    if hashlib.sha256(data).hexdigest() != sha:
        print("__K4S_GATE_RESULT__ " + json.dumps(dict(launched=False, exit_code=3, failures=["shipped " + name +
              " SHA-256 differs from its pin"])), flush=True)
        raise SystemExit(3)
    module = types.ModuleType(name)
    module.__file__ = "<shipped " + name + ">"
    exec(compile(data, module.__file__, "exec"), module.__dict__)
    sys.modules[name] = module
    return module
si = _shipped("safe_input", %r, %r)
tool = _shipped("k4s_end_host_tool", %r, %r)
tool.check_safe_input(si)
'''


def compose(si, P, config):
    import base64
    body = si.read_bytes(P, "tools", "k4s_end_launch_remote.py", expected_sha256=REMOTE_SHA256)
    layer = si.read_bytes(P, "tools", "safe_input.py", expected_sha256=SAFE_INPUT_SHA256)
    helper = si.read_bytes(P, "tools", "k4s_end_host_tool.py", expected_sha256=HOST_TOOL_SHA256)
    prelude = PRELUDE % (base64.b64encode(layer).decode(), SAFE_INPUT_SHA256,
                         base64.b64encode(helper).decode(), HOST_TOOL_SHA256)
    return (prelude + "CONFIG = json.loads(%r)\n" % json.dumps(config, sort_keys=True)).encode() + body


def launch(a, layers=None):
    require(not optimized(), "The gate refuses -O")
    si, tool = layers or load_layers()
    require(si.hostname_checked().split(".")[0] == "127x05", "The gate runs on 127x05")
    P = local_policy(si, a, extra_reads(a))
    mine = "%s/%s/" % (a.host, a.attempt)
    si.check_absent(P, "launch-out", mine + "LAUNCH-RECEIPT.json")
    declaration = pinned_json(si, P, "launch", "ROOTS-DECLARATION.json", a.roots_sha256, "RC-6")
    roots = validate_roots(si, declaration)
    argv_bytes = si.read_bytes(P, "launch", mine + "launch-argv.json", max_size=1 << 20)
    argv = si.loads_strict(argv_bytes, "launch-argv.json")
    require(sha_bytes(argv_nul(argv)) == a.argv_sha256, "Launch argv differs from its pin")
    shape = validate_argv(si, argv, a.kind, a.host, a.attempt, roots, a.diagnostic_preflight)
    quiet_cmd = si.read_bytes(P, "tools", "quiet-read-v3.cmd", expected_sha256=QUIET_V3_SHA256)
    require(a.clearance_seconds >= 7200 and a.window_seconds >= 3600, "Clearance < 2 h or window < 1 h")
    allow = {}
    for item in a.allow_timer or []:
        unit, _, reason = item.partition("=")
        require(unit.endswith(".timer") and reason.strip() and unit not in allow,
                "--allow-timer needs UNIT.timer=justification (once per unit)")
        allow[unit] = reason
    ruling = None
    if a.second_attempt_ruling_sha256:
        ruling = check_repeat_ruling(pinned_json(si, P, "launch", mine + "REPEAT-RULING.json",
                                                 a.second_attempt_ruling_sha256, "Second-attempt ruling"),
                                     a.host, a.attempt)
    d = roots[a.host]
    record = dict(schema=RECEIPT_SCHEMA, kind=a.kind, host=a.host, job=shape["job"], attempt=a.attempt,
                  mode=shape["mode"], qualifying_preflight=a.kind == "preflight" and shape["mode"] == "binding",
                  roots_sha256=a.roots_sha256, roots_commit=declaration["commit"],
                  gate_sha256=si.sha256_input(P, "tools", "k4s_end_launch_gate.py")["sha256"], remote_sha256=REMOTE_SHA256,
                  safe_input_sha256=SAFE_INPUT_SHA256, host_tool_sha256=HOST_TOOL_SHA256,
                  argv_json_sha256=sha_bytes(argv_bytes), argv_nul_sha256=a.argv_sha256, launch_command=argv,
                  measurement_argv=shape["measurement_argv"], wrapper_sha256=WRAPPER_SHA256[a.kind],
                  quiet_read_v3_sha256=QUIET_V3_SHA256, allow_timers=allow, outcomes_sealed=True,
                  scientific_games=False, C5_no_further_SSH=True, launched=False,
                  second_attempt_ruling=dict(sha256=a.second_attempt_ruling_sha256, ref=ruling["coordinator_ref"])
                  if ruling else None)
    record["receive"] = check_receive(si, tool, P, a)
    record["prerequisites"] = prerequisites(si, P, a, roots, shape)
    record["local_controlmaster"] = local_controlmaster(si, a.host)
    config = dict(host=a.host, kind=a.kind, quiet_cmd=quiet_cmd.decode(), quiet_gap_seconds=QUIET_GAP_SECONDS,
                  helper_pid=HELPER_PIDS[a.host], clearance_seconds=a.clearance_seconds, allow_timers=allow,
                  window_seconds=a.window_seconds, stamps=STAMPS, launch_argv=argv, argv_sha256=a.argv_sha256,
                  supervisor_cpu=SUPERVISOR_CPU, job=shape["job"], attempt=a.attempt,
                  attempt_parent=shape["attempt_parent"], base=d["base"], tools=d["tools"],
                  repository=d["repository"], file_pins=shape["file_pins"], round=shape["round"],
                  bundle=shape["bundle"]["path"], bundle_pins_sha256=shape["bundle"]["tiers_pins_sha256"],
                  guard_job=shape["bundle"]["guard_job"], guard_side_files=list(GUARD_SIDE_FILES),
                  seed_commits=list(SEED_COMMITS), second_attempt_ruling=bool(ruling),
                  python_marker=shape["python_marker"], postexec_seconds=POSTEXEC_SECONDS, path=HOST_PATH,
                  bin=HOST_BIN, safe_input_sha256=SAFE_INPUT_SHA256, host_tool_sha256=HOST_TOOL_SHA256,
                  bundle_sans_guard_sha256=((record["prerequisites"].get("preflights") or {}).get(a.host) or {}).get(
                      "bundle_binding", {}).get("bundle_sans_guard_sha256") if a.kind == "end" else None,
                  runtime=d["runtime"], end_reference_rel=END_REFERENCE_REL, end_reference_sha256=END_REFERENCE_SHA256,
                  inputs=[shape["options"]["--native"], shape["options"]["--corpus"]], end_job_rel=END_JOB_REL,
                  end_job_sha256=shape["end_job_sha256"], end_job_schema=END_JOB_SCHEMA,
                  end_evidence_sha256=shape["options"]["--end-evidence-sha256"],
                  k4s_manifest_sha256=K4S_MANIFEST_SHA256, end_grants=list(END_GRANTS))
    program = compose(si, P, config)
    record["composed_program_sha256"] = sha_bytes(program)
    ssh = [SSH_BINARY] + list(si.SSH_OPTIONS) + [a.host, REMOTE_COMMAND]
    record["launch_SSH_argv"] = ssh
    if a.dry_run:
        sys.stdout.write(program.decode())
        return 0
    opened = time.time()
    record["session_open_utc"] = iso_ms(opened)
    try:
        done = si.run_checked(ssh, 900, 64 << 20, env={"LC_ALL": "C"}, env_allow=("HOME", "USER", "SSH_AUTH_SOCK"),
                              stdin_bytes=program, ok_rcs=(0, 3, 4))
        stdout, stderr, rc = done.stdout.decode("utf-8", "replace"), done.stderr.decode("utf-8", "replace"), done.rc
    except si.Refusal as error:                      # ssh failure, timeout or unexpected rc: host state unknown
        stdout, stderr, rc = "", str(error), None
    closed = time.time()
    record.update(session_close_utc=iso_ms(closed), session_close_epoch=closed, session_open_epoch=opened)
    record.update(launch_SSH_exit_code=rc, launch_SSH_stderr=stderr[-2000:])
    lines = [x for x in stdout.splitlines() if x.startswith("__K4S_GATE_RESULT__ ")]
    host_result = json.loads(lines[-1][len("__K4S_GATE_RESULT__ "):]) if len(lines) == 1 else None
    record["host_gate"] = host_result
    if host_result is not None:
        record["launched"] = host_result.get("launched") is True
        record["utc"] = host_result.get("utc")
        record["C5_preexec_gate"] = host_result.get("C5_preexec_gate")
        record["postexec"] = host_result.get("postexec")
    with si.Writer(P, "launch-out") as writer:
        out = writer.create_excl(mine + "LAUNCH-RECEIPT.json",
                                 (json.dumps(record, indent=1, sort_keys=True) + "\n").encode())
    print(json.dumps(dict(receipt=LAUNCH_BASE + "/" + mine + "LAUNCH-RECEIPT.json", receipt_sha256=out["sha256"],
                          launched=record["launched"], failures=(host_result or {}).get("failures"), ssh_rc=rc),
                     sort_keys=True))
    if host_result is None:
        return 5                                    # unknown host state: STOP, do not relaunch
    if record["launched"]:
        return 0 if rc == 0 else 6                  # launched; a nonzero SSH status is recorded for review
    return 4 if host_result.get("job_created_utc") else 3


def admission(a, layers=None):
    """RC-7: session close (05 clock) vs. guard admission (host clock) from the sealed, verified receipt."""
    require(not optimized(), "Runs not under -O")
    si, _ = layers or load_layers()
    require(si.hostname_checked().split(".")[0] == "127x05", "Runs on 127x05")
    m = ATTEMPT[a.kind].fullmatch(a.attempt)
    require(m is not None and m.group(1) == a.host, "Attempt name does not match host/kind")
    mine = "%s/%s/" % (a.host, a.attempt)
    sub = "durable-measurement" if a.kind == "end" else "preflight"
    verified = "DURABLE-ACK.json" if a.kind == "end" else "PREFLIGHT-VERIFIED.json"
    P = si.Policy("127x05", [
        si.Role("launch", LAUNCH_BASE, "read", 64 << 20, exact=(mine + "LAUNCH-RECEIPT.json",)),
        si.Role("out", LAUNCH_BASE, "write", 1 << 20, exact=(mine + "ADMISSION.json",)),
        si.Role("recv", RECEIVE[a.kind] + "/" + a.host + "/" + a.attempt, "read", 64 << 20,
                exact=(verified, sub + "/receipt-manifest.json", sub + "/guard-admission.json"))])
    launch_ = pinned_json(si, P, "launch", mine + "LAUNCH-RECEIPT.json", a.launch_receipt_sha256, "Launch receipt")
    require(launch_.get("schema") == RECEIPT_SCHEMA and launch_.get("host") == a.host
            and launch_.get("attempt") == a.attempt and launch_.get("kind") == a.kind and launch_.get("launched"),
            "Launch receipt is not this launched attempt")
    v = pinned_json(si, P, "recv", verified, a.verified_sha256, verified)
    require(v.get("receipt_manifest_sha256") and (v.get("ack_allowed") is True if a.kind == "end" else True),
            "Run the approved verifier first (C-d)")
    seal = si.read_bytes(P, "recv", sub + "/receipt-manifest.json", expected_sha256=v["receipt_manifest_sha256"])
    files = si.loads_strict(seal, "receipt-manifest.json")["files"]
    admitted = si.read_json(P, "recv", sub + "/guard-admission.json", 16 << 20,
                            expected_sha256=files.get("guard-admission.json"))["utc"]
    closed = launch_["session_close_epoch"]
    out = dict(schema=ADMISSION_SCHEMA, host=a.host, attempt=a.attempt, kind=a.kind,
               launch_receipt_sha256=a.launch_receipt_sha256, verified_sha256=a.verified_sha256,
               session_close_utc=launch_["session_close_utc"], guard_admission_utc=iso_ms(admitted),
               seconds_close_to_admission=admitted - closed, closed_before_admission=closed + 1 < admitted,
               note="05 clock (close) vs host clock (admission); skew not corrected; 1 s margin required")
    with si.Writer(P, "out") as writer:
        writer.create_excl(mine + "ADMISSION.json", (json.dumps(out, indent=1, sort_keys=True) + "\n").encode())
    print(json.dumps(out, sort_keys=True))
    return 0 if out["closed_before_admission"] else 2


# ---------------------------------------------------------------- r4: launch-input producers (05 only, before any session)

BUNDLE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def ensure_dir(si, P, read_role, write_role, leaf, mode=0o755):
    """The leaf directory under a canonical parent: created exclusively if absent, else it must already be a canonical
    directory (no symlink, no file). Returns True if this call created it."""
    try:
        si.check_absent(P, read_role, leaf)
    except si.Refusal as error:
        require(error.code == "exists", str(error))
        si.check_dir(P, read_role, leaf)
        return False
    with si.Writer(P, write_role) as writer:
        writer.mkdir_excl(leaf, mode=mode)
    return True


def launch_dir_roles(si, host, attempt, out_names):
    """Roles that make RUNNER/end-launch/<host>/<attempt>/ (each level exact) and write exactly `out_names` in it."""
    R = si.Role
    return [R("lb-read", LAUNCH_BASE, "read", 1, exact=(host,)), R("lb-write", LAUNCH_BASE, "write", 1, exact=(host,)),
            R("lh-read", LAUNCH_BASE + "/" + host, "read", 1, exact=(attempt,)),
            R("lh-write", LAUNCH_BASE + "/" + host, "write", 1, exact=(attempt,)),
            R("la-read", LAUNCH_BASE + "/" + host + "/" + attempt, "read", 1, exact=tuple(out_names)),
            R("la-write", LAUNCH_BASE + "/" + host + "/" + attempt, "write", 1 << 20, exact=tuple(out_names))]


def make_launch_dir(si, P, host, attempt):
    si.check_dir(P, "launch")                                   # RUNNER/end-launch: canonical, never created here
    return dict(host_created=ensure_dir(si, P, "lb-read", "lb-write", host),
                attempt_created=ensure_dir(si, P, "lh-read", "lh-write", attempt))


def staged_bundle(si, P, name, declared, host):
    """S4 bundle receipts on 05 (RUNNER/end-staging/bundles/<name>/): tiers-pins.json read with the RC-6 SHA, its
    sidecar, and a production CANDIDATE assembly receipt for this host / manifest / guard job; the bundle carries the
    END evidence of record at END_EVIDENCE_REL."""
    manifest = si.read_json(P, "staging", name + "/tiers-pins.json", 64 << 20,
                            expected_sha256=declared["tiers_pins_sha256"])
    require(si.read_bytes(P, "staging", name + "/tiers-pins.sha256", max_size=4096)
            == (declared["tiers_pins_sha256"] + "  tiers-pins.json\n").encode(), name + ": tiers-pins.sha256 differs")
    receipt = si.read_json(P, "staging", name + "/assembly-receipt.json", 1 << 20)
    require(receipt.get("schema") == ASSEMBLY_SCHEMA and receipt.get("production_pins") is True
            and receipt.get("status") == "CANDIDATE" and receipt.get("manifest_sha256") == declared["tiers_pins_sha256"]
            and receipt.get("host") == host and receipt.get("guard_job") == declared["guard_job"],
            name + ": assembly receipt is not a production receipt for this host/manifest/guard job")
    profile = manifest.get("reference_load_profile") or {}
    require("k4s_s4_synthetic" not in manifest and manifest.get("profile") == "fleet-reference"
            and profile.get("host") == host and (profile.get("guard") or {}).get("job") == declared["guard_job"]
            and profile.get("end_evidence") == END_EVIDENCE_REL
            and (manifest.get("files") or {}).get(END_EVIDENCE_REL) == END_EVIDENCE_SHA256,
            name + ": bundle manifest is not the declared fleet-reference bundle with the END evidence of record")
    return dict(name=name, tiers_pins_sha256=declared["tiers_pins_sha256"],
                assembly_receipt_sha256=si.sha256_input(P, "staging", name + "/assembly-receipt.json")["sha256"])


def end_job_at(si, commit):
    """The committed END-JOB at commit X of the 05 full clone (read only, through the gated git reader): its SHA-256
    is the --end-job-sha256 of every END argv; it must bind the END evidence of record and the K4S manifest."""
    require(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit), "--end-job-commit must be 40 hex")
    P = si.Policy("127x05", [si.Role("repo", REPO_FULL, "read", 1 << 16, exact=(END_JOB_REL,), grants=END_GRANTS)])
    data = si.git_show_file(P, "repo", si.GitRepo(work_tree=REPO_FULL), commit, END_JOB_REL, max_size=1 << 16)
    job = si.loads_strict(data, END_JOB_REL)
    require(isinstance(job, dict) and job.get("schema") == END_JOB_SCHEMA and job.get("study") == "PREREG-K4S"
            and job.get("end_evidence_sha256") == END_EVIDENCE_SHA256
            and job.get("k4s_manifest_sha256") == K4S_MANIFEST_SHA256,
            "END-JOB at %s does not bind the END evidence of record / K4S manifest" % commit[:12])
    return dict(commit=commit, sha256=sha_bytes(data))


def compose_argv(kind, host, attempt, d, bundle, native, corpus, end_job_sha256=None, compare=None, hold=None,
                 diagnostic=False):
    """The one argv layout validate_argv accepts (END: exactly the 13 frozen options, in END_REQUIRED order)."""
    m = ATTEMPT[kind].fullmatch(attempt)
    parent = d["attempts"] if kind == "end" else d["preflight"]
    job = parent + "/" + attempt
    argv = ["nice", "-n", "10", "taskset", "-c", SUPERVISOR_CPU, "bash", d["tools"] + "/detach.sh",
            job + "/detach.log", job + "/detach.json", "bash", d["tools"] + "/" + TOOLS[kind], job, "env"]
    argv += ["%s=%s" % (k, v) for k, v in ENV_REQUIRED.items()] + [HOST_PYTHON, "-B"]
    common = {"--bundle": bundle["path"], "--runtime-root": d["runtime"], "--native": native, "--corpus": corpus,
              "--corpus-inventory": d["runtime"] + "/" + CORPUS_INVENTORY_REL,
              "--k4s-manifest-sha256": K4S_MANIFEST_SHA256, "--sd1-manifest-sha256": SD1_MANIFEST_SHA256,
              "--end-evidence": bundle["path"] + "/" + END_EVIDENCE_REL, "--end-evidence-sha256": END_EVIDENCE_SHA256,
              "--repository": d["repository"], "--out": job + "/" + attempt}
    if kind == "end":
        argv.append(d["runtime"] + "/" + END_REFERENCE_REL)
        values = dict(common, **{"--end-job-sha256": end_job_sha256, "--round": str(int(m.group(2)))})
        names = END_REQUIRED
    else:
        argv += [d["tools"] + "/k4s_end_preflight.py", "run"]
        values = dict(common, **{"--bundle-pins-sha256": bundle["tiers_pins_sha256"],
                                 "--corpus-inventory-sha256": CORPUS_INVENTORY_SHA256, "--attempt-parent": d["attempts"],
                                 "--hold-seconds": hold, "--compare-bundle": compare["path"],
                                 "--compare-bundle-pins-sha256": compare["tiers_pins_sha256"]})
        names = PREFLIGHT_REQUIRED + (("--end-job-sha256",) if end_job_sha256 else ())
        if end_job_sha256:
            values["--end-job-sha256"] = end_job_sha256
    for name in names:
        argv += [name, values[name]]
    if diagnostic:
        argv.append("--no-reference-work")
    return argv


def build_argv(a, layers=None):
    """U5 (r4): write RUNNER/end-launch/<host>/<attempt>/launch-argv.json, the exact argv `launch` later validates,
    from verified inputs only: the pinned RC-6 declaration (roots, bundle paths, tiers-pins SHAs, guard jobs), the S4
    bundle receipts on 05, the END-JOB at the given commit of the 05 full clone (its SHA), the launching host's
    pinned PREFLIGHT-VERIFIED identity (END: native/corpus) and the gate's own constants. The composed argv must pass
    validate_argv before anything is written; the file is created exclusively (O_EXCL, no-follow); its NUL-joined
    SHA-256 is printed for `launch --argv-sha256`."""
    require(not optimized(), "The gate refuses -O")
    si, tool = layers or load_layers()
    require(si.hostname_checked().split(".")[0] == "127x05", "build-argv runs on 127x05")
    m = ATTEMPT[a.kind].fullmatch(a.attempt)
    require(m is not None and m.group(1) == a.host, "Attempt name is not a %s name for %s" % (a.kind, a.host))
    names = [a.bundle] + ([a.compare_bundle] if a.kind == "preflight" else [])
    require(all(isinstance(n, str) and BUNDLE_NAME.fullmatch(n) for n in names), "Bundle names required")
    pf = parse_pf(a.preflight_verified)
    if a.kind == "end":
        require(a.end_job_commit and sorted(pf) == [a.host] and a.native is None and a.corpus is None
                and a.compare_bundle is None and a.hold_seconds is None and not a.diagnostic_preflight,
                "END: --end-job-commit and this host's --preflight-verified only (native/corpus come from it)")
    else:
        require(a.native and a.corpus and a.compare_bundle and a.hold_seconds is not None and not pf,
                "preflight: --compare-bundle, --native, --corpus and --hold-seconds are required")
    R = si.Role
    pf_names = ["%s/%s/PREFLIGHT-VERIFIED.json" % (h, att) for h, (att, _) in pf.items()]
    P = si.Policy("127x05", [R("launch", LAUNCH_BASE, "read", 64 << 20, exact=("ROOTS-DECLARATION.json",)),
                             R("staging", STAGING_BUNDLES, "read", 64 << 20,
                               exact=tuple(n + "/" + f for n in names for f in BUNDLE_FILES))]
                  + ([R("pf-recv", RECEIVE["preflight"], "read", 64 << 20, exact=tuple(pf_names))] if pf else [])
                  + launch_dir_roles(si, a.host, a.attempt, ("launch-argv.json",)))
    declaration = pinned_json(si, P, "launch", "ROOTS-DECLARATION.json", a.roots_sha256, "RC-6")
    roots = validate_roots(si, declaration)
    d = roots[a.host]
    declared = {}
    for n in names:
        require(n in d["bundles"], "Not a declared RC-6 bundle for %s: %s" % (a.host, n))
        declared[n] = d["bundles"][n]
    receipts = [staged_bundle(si, P, n, declared[n], a.host) for n in names]
    job = end_job_at(si, a.end_job_commit) if a.end_job_commit else None
    if a.kind == "end":
        attempt_, digest = pf[a.host]
        v = pinned_json(si, P, "pf-recv", pf_names[0], digest, "Preflight verification " + a.host)
        require(v.get("schema") == VERIFIED_SCHEMA and v.get("host") == a.host and v.get("attempt") == attempt_,
                "--preflight-verified is not this host's verified preflight")
        identity = launch_identity(v, d, a.host)
        native, corpus = identity["native"], identity["corpus"]
        hold = None
    else:
        native, corpus = a.native, a.corpus
        hold = "%d" % a.hold_seconds
    argv = compose_argv(a.kind, a.host, a.attempt, d, declared[a.bundle], native, corpus,
                        job["sha256"] if job else None, declared.get(a.compare_bundle), hold, a.diagnostic_preflight)
    shape = validate_argv(si, argv, a.kind, a.host, a.attempt, roots, a.diagnostic_preflight)
    data = (json.dumps(argv, indent=1) + "\n").encode()
    require(si.loads_strict(data, "launch-argv.json") == argv, "launch-argv.json does not round-trip")
    made = make_launch_dir(si, P, a.host, a.attempt)
    with si.Writer(P, "la-write") as writer:
        out = writer.create_excl("launch-argv.json", data)
    result = dict(schema="clasher.k4s.end-launch-argv-build.v1", kind=a.kind, host=a.host, attempt=a.attempt,
                  launch_argv=LAUNCH_BASE + "/%s/%s/launch-argv.json" % (a.host, a.attempt),
                  argv_sha256=sha_bytes(argv_nul(argv)), argv_json_sha256=out["sha256"], roots_sha256=a.roots_sha256,
                  bundles=receipts, end_job=job, preflight_verified=pf.get(a.host), mode=shape["mode"],
                  host_python=HOST_PYTHON, created=made)
    print(json.dumps(result, sort_keys=True))
    return result


def prepare_preflight_receive(a, layers=None):
    """U6 (r4): create RUNNER/preflight-received/<host>/<attempt>/ exclusively (mode 0700; the base and host levels
    are created if absent, else must be canonical directories), exactly where k4s_preflight_push.sh pushes
    ("127x05:$receive_base/$host/$attempt/") and where `launch` (check_receive) and S5 verify-received read; then
    prove it is EMPTY with the gate's own names-only listing."""
    require(not optimized(), "The gate refuses -O")
    si, tool = layers or load_layers()
    require(si.hostname_checked().split(".")[0] == "127x05", "prepare-preflight-receive runs on 127x05")
    m = ATTEMPT["preflight"].fullmatch(a.attempt)
    require(m is not None and m.group(1) == a.host, "Attempt name is not a preflight name for " + a.host)
    base = RECEIVE["preflight"]
    runner, leaf = base.rsplit("/", 1)
    R = si.Role
    host_dir = base + "/" + a.host
    P = si.Policy("127x05", [R("runner-read", runner, "read", 1, exact=(leaf,)),
                             R("runner-write", runner, "write", 1, exact=(leaf,)),
                             R("recv-read", base, "read", 1, exact=(a.host,)),
                             R("recv-write", base, "write", 1, exact=(a.host,)),
                             R("host-read", host_dir, "read", 1, exact=(a.attempt,)),
                             R("host-write", host_dir, "write", 1, exact=(a.attempt,))])
    created = dict(base=ensure_dir(si, P, "runner-read", "runner-write", leaf),
                   host=ensure_dir(si, P, "recv-read", "recv-write", a.host))
    si.check_absent(P, "host-read", a.attempt)                 # a used receive dir is never reused
    with si.Writer(P, "host-write") as writer:
        writer.mkdir_excl(a.attempt, mode=0o700)
    root = host_dir + "/" + a.attempt
    Q = si.Policy("127x05", [R("receive-dir", root, "read", 1, patterns=("*",))])
    require(tool.names_only(si, Q, "receive-dir") == [], "Preflight receive directory is not empty")
    identity = si.check_dir(Q, "receive-dir")
    result = dict(schema="clasher.k4s.end-preflight-receive-prepared.v1", receive=root, host=a.host,
                  attempt=a.attempt, created_empty=True, mode="%o" % (identity["mode"] & 0o7777),
                  dev=identity["dev"], ino=identity["ino"], created=created, utc=iso())
    print(json.dumps(result, sort_keys=True))
    return result


def parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 allow_abbrev=False)
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("launch", allow_abbrev=False)
    p.add_argument("--host", choices=END_HOSTS, required=True)
    p.add_argument("--kind", choices=("end", "preflight"), required=True)
    p.add_argument("--attempt", required=True)
    p.add_argument("--argv-sha256", required=True, help="sha256 of the NUL-joined argv")
    p.add_argument("--roots-sha256", required=True, help="RC-6 ROOTS-DECLARATION.json SHA-256")
    p.add_argument("--prepare-proof-sha256")
    p.add_argument("--allow-timer", action="append", metavar="UNIT.timer=JUSTIFICATION")
    p.add_argument("--clearance-seconds", type=int, default=7200)
    p.add_argument("--window-seconds", type=int, default=7200)
    p.add_argument("--second-attempt-ruling-sha256")
    p.add_argument("--preflight-verified", action="append", metavar="HOST=ATTEMPT:SHA256")
    p.add_argument("--prior-03", metavar="ATTEMPT:ACK_SHA256:ADMISSION_SHA256")
    p.add_argument("--bus-decision-sha256")
    p.add_argument("--diagnostic-preflight", action="store_true",
                   help="allow a background-only (--no-reference-work) NON-QUALIFYING preflight")
    p.add_argument("--dry-run", action="store_true")
    b = sub.add_parser("build-argv", allow_abbrev=False, help="r4 U5: write launch-argv.json from verified inputs")
    b.add_argument("--host", choices=END_HOSTS, required=True)
    b.add_argument("--kind", choices=("end", "preflight"), required=True)
    b.add_argument("--attempt", required=True)
    b.add_argument("--roots-sha256", required=True, help="RC-6 ROOTS-DECLARATION.json SHA-256")
    b.add_argument("--bundle", required=True, help="declared RC-6 bundle NAME (END: the attempt bundle)")
    b.add_argument("--compare-bundle", help="preflight: the declared attempt bundle NAME")
    b.add_argument("--end-job-commit", help="END (optional for preflight): END-JOB commit X in the 05 full clone")
    b.add_argument("--preflight-verified", action="append", metavar="HOST=ATTEMPT:SHA256",
                   help="END: this host's verified preflight (source of --native/--corpus)")
    b.add_argument("--native", help="preflight: staged native under the declared base")
    b.add_argument("--corpus", help="preflight: staged K4 corpus under the declared base")
    b.add_argument("--hold-seconds", type=int, help="preflight hold (>= the host minimum)")
    b.add_argument("--diagnostic-preflight", action="store_true", help="preflight: add --no-reference-work")
    r = sub.add_parser("prepare-preflight-receive", allow_abbrev=False, help="r4 U6: empty preflight receive dir")
    r.add_argument("--host", choices=END_HOSTS, required=True)
    r.add_argument("--attempt", required=True)
    q = sub.add_parser("admission", allow_abbrev=False)
    q.add_argument("--host", choices=END_HOSTS, required=True)
    q.add_argument("--kind", choices=("end", "preflight"), required=True)
    q.add_argument("--attempt", required=True)
    q.add_argument("--launch-receipt-sha256", required=True)
    q.add_argument("--verified-sha256", required=True, help="DURABLE-ACK.json / PREFLIGHT-VERIFIED.json SHA-256")
    return ap


def main(argv=None, layers=None):
    a = parser().parse_args(argv)
    if a.command == "build-argv":
        build_argv(a, layers)
        return 0
    if a.command == "prepare-preflight-receive":
        prepare_preflight_receive(a, layers)
        return 0
    return launch(a, layers) if a.command == "launch" else admission(a, layers)


if __name__ == "__main__":
    raise SystemExit(main())
