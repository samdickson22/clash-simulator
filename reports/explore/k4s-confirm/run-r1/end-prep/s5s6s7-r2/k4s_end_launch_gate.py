"""K4S END launch & prelaunch gate, 05 side (S7 candidate r2). Review required before any use. Never reads outcomes.

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
import os
import re
import sys
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SAFE_INPUT_SHA256 = "806e5ebb882bc7fae8fc10598599d03276bea4c655bba46328dd80af44947f00"
SAFE_INPUT_FINGERPRINT = "33f594ed75c3b3b6416ec8b4804490b82a85521533056b57c1d582529207f592"
HOST_TOOL_SHA256 = "cf19269071d57f0d1fe9b7ce5f865b4641ecda62c88e418cd73b711a57a5d6f3"
QUIET_V3_SHA256 = "a293207e601498d8e7b374a610eddba6f7223e64af34dae00ce52defa30f7c9c"
DETACH_SHA256 = "1648dfdcf85097a54c00b488a5d5570f7c4d0820052a31f89553501084c5b3bb"
WRAPPER_SHA256 = {"end": "48d02ae266ab19a358b1feee1fd6423587613a3440b32ce8877f755cf76c86ef",        # exit_push r2
                  "preflight": "0204fd2bd74f89573dbd851661c0e8710ecde1e6c96e150c7c3c940488f4eaea"}  # preflight_push
PREFLIGHT_SHA256 = "43ca0057fa921fd89c858797d7d8604e92b52320549b74f9f40c36753b152dba"
REMOTE_SHA256 = "7abe5fc1a764c9a74eb97ef6b898814cc280cb65799a5e61d936d4b1fe529dd0"
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
VERIFIED_SCHEMA = "clasher.k4s.end-preflight-verified.v2"
ACK_SCHEMA = "clasher.k4s.end-durable-ack.v2"
RECEIPT_SCHEMA = "clasher.k4s.end-launch-receipt.v2"
ADMISSION_SCHEMA = "clasher.k4s.end-launch-admission.v2"
SHA = re.compile(r"[0-9a-f]{64}")
CORPUS_INVENTORY_REL = "reports/explore/t1/corpora/corpus-03-a51ea64c/corpora.json"   # K4S manifest corpus.inventory


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

def read_pinned(path, sha256, cap=1 << 23):
    """Bootstrap read before safe_input exists (O_NOFOLLOW, regular, st_nlink 1, exact size, SHA-256)."""
    import stat
    require(os.path.realpath(path) == path, "pinned file path is not canonical: " + path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        st = os.fstat(fd)
        require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size <= cap, "pinned file not plain: " + path)
        data = b""
        while len(data) < st.st_size:
            chunk = os.read(fd, st.st_size - len(data))
            require(chunk, "pinned file shrank: " + path)
            data += chunk
        require(not os.read(fd, 1), "pinned file grew: " + path)
    finally:
        os.close(fd)
    require(sha_bytes(data) == sha256, "pinned file SHA-256 mismatch: " + path)
    return data


def load_layers(directory=HERE):
    out = []
    for name, sha in (("safe_input", SAFE_INPUT_SHA256), ("k4s_end_host_tool", HOST_TOOL_SHA256)):
        path = os.path.join(directory, name + ".py")
        module = types.ModuleType(name)
        module.__file__ = path
        exec(compile(read_pinned(path, sha), path, "exec"), module.__dict__)
        out.append(module)
    si, tool = out
    require(si.constants_fingerprint() == SAFE_INPUT_FINGERPRINT, "safe_input fingerprint differs from the pin")
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
    for label in ("--native", "--corpus"):
        path = opts[label]
        require(path.startswith(d["base"] + "/") and os.path.normpath(path) == path and not any(
            path.startswith(d[k] + "/") for k in ("attempts", "preflight", "repository", "tools")),
            label + " must be a K4S-owned file under the declared base")
    require(opts["--repository"] == d["repository"], "--repository must be the declared clone")
    pins.update({d["tools"] + "/safe_input.py": SAFE_INPUT_SHA256, d["tools"] + "/k4s_end_host_tool.py": HOST_TOOL_SHA256})
    return dict(job=job, attempt=attempt, attempt_parent=parent, measurement_argv=m_argv, python_marker=marker,
                file_pins=pins, wrapper=d["tools"] + "/" + TOOLS[kind], options=opts, round=round_index,
                bundle=bundle, mode="diagnostic" if "--no-reference-work" in opts else "binding")


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
                  "127x03/%s/ADMISSION.json" % attempt]
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
    if host == a.host and a.kind == "end":
        o = shape["options"]
        require(inputs.get("end_evidence_sha256") == o["--end-evidence-sha256"]
                and inputs.get("sd1_manifest_sha256") == o["--sd1-manifest-sha256"],
                "Preflight %s: evidence/SD1 binding differs from this END argv" % host)
    bus = dict(band=v.get("bus_band"), gate=v.get("bus_gate"), cumulative_loaded=v.get("bus_cumulative_loaded"))
    if host == "127x04":
        require(v.get("bus_gate") == v.get("bus_band"), "Preflight 04: bus gate/band mismatch")
        if v.get("bus_band") == "coordinator-decision":
            rel = "127x04/BUS-DECISION-%s.json" % attempt
            decision = pinned_json(si, P, "launch", rel, a.bus_decision_sha256, "Bus decision")
            require(decision.get("schema") == "clasher.k4s.end-bus-decision.v1" and decision.get("decision") ==
                    "proceed" and decision.get("preflight_attempt") == attempt
                    and decision.get("receipt_manifest_sha256") == v.get("receipt_manifest_sha256")
                    and isinstance(decision.get("coordinator_ref"), str) and decision["coordinator_ref"].strip(),
                    "Bus decision is not a coordinator 'proceed' ruling for this 04 preflight")
            bus["coordinator_decision"] = dict(sha256=a.bus_decision_sha256, ref=decision["coordinator_ref"])
        else:
            require(v.get("bus_band") == "proceed",
                    "04 loaded bus band %r: STOP before any claim (P2-3)" % v.get("bus_band"))
    return dict(attempt=attempt, sha256=digest, receipt_manifest_sha256=v["receipt_manifest_sha256"], bus=bus,
                loaded_seconds=duration.get("loaded_seconds_measured"))


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
                               verified_epoch=ack["verified_epoch"], exit_epoch=ack["exit_epoch"])
    return out


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
        ruling = pinned_json(si, P, "launch", mine + "REPEAT-RULING.json", a.second_attempt_ruling_sha256,
                             "Second-attempt ruling")
        require(ruling.get("schema") == "clasher.k4s.end-second-attempt-ruling.v1" and ruling.get("host") == a.host
                and ruling.get("attempt") == a.attempt and isinstance(ruling.get("coordinator_ref"), str)
                and ruling["coordinator_ref"].strip(), "Second-attempt ruling is not for this host/attempt")
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
                  bin=HOST_BIN, safe_input_sha256=SAFE_INPUT_SHA256, host_tool_sha256=HOST_TOOL_SHA256)
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
    q = sub.add_parser("admission", allow_abbrev=False)
    q.add_argument("--host", choices=END_HOSTS, required=True)
    q.add_argument("--kind", choices=("end", "preflight"), required=True)
    q.add_argument("--attempt", required=True)
    q.add_argument("--launch-receipt-sha256", required=True)
    q.add_argument("--verified-sha256", required=True, help="DURABLE-ACK.json / PREFLIGHT-VERIFIED.json SHA-256")
    return ap


def main(argv=None, layers=None):
    a = parser().parse_args(argv)
    return launch(a, layers) if a.command == "launch" else admission(a, layers)


if __name__ == "__main__":
    raise SystemExit(main())
