"""K4S END launch & prelaunch gate, 05 side (S7 candidate). Review required before any use. Never reads outcomes.

``launch``: validates the pinned launch argv (END or preflight) on 05, the 05 receive directory and the RC-9
prerequisites, checks that no local ControlMaster to the host is open, then opens exactly ONE
``ssh -o ControlMaster=no -o ControlPath=none -o BatchMode=yes HOST /usr/bin/python3 -I -B -`` session that runs
k4s_end_launch_remote.py (quiet-read v3 #1 and #2 verbatim 30 s apart, unfiltered timers, stamps, who, other sshd
sessions, staged-file SHAs, registry names, C5 pre-exec gate, the detach, priority read-back). It records the
session open/close UTC (05 clock) and writes one launch receipt (exclusive create). It makes no other SSH call.
``admission``: after the 05 verifier ran (>= exit + 1300 s), reads only the sealed guard-admission.json UTC and
records whether the launch session closed before guard admission (RC-7).

Quiet read #1 is in the same session by default (no extra login on 04). A separate earlier read is possible with
the unchanged approved command (``ssh -o ControlMaster=no -o ControlPath=none HOST "$(cat quiet-read-v3.cmd)"``)
but is not required by this gate.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOST_BASES = {"127x03": "/mpac/sdicks02/jobs/clasher/k4s-end-r1",
              "127x04": "/mpac/sdicks02/jobs-k4s/k4s-end-r1"}      # = k4s_end_exit_push.sh
HELPER_PIDS = {"127x03": 2368, "127x04": 2296}                              # r4 quiet-read baseline
MIN_PREFLIGHT_HOLD = {"127x03": 60, "127x04": 900}
RUNNER = Path("/mpac/sdicks02/k4s-runner/run-r1")
RECEIVE = {"end": RUNNER / "end-received", "preflight": RUNNER / "preflight-received"}
QUIET_V3_SHA256 = "a293207e601498d8e7b374a610eddba6f7223e64af34dae00ce52defa30f7c9c"
DETACH_SHA256 = "1648dfdcf85097a54c00b488a5d5570f7c4d0820052a31f89553501084c5b3bb"
WRAPPER_SHA256 = {"end": "62cdda778f05c3538d6356235aab00fc259d738dceaa83707b674e476d15666c",  # k4s_end_exit_push.sh
                  "preflight": "e3f1da6f65927cfcb3fafef1b72470a478199fd5dfc52e652188d250b0657cd1"}  # k4s_preflight_push.sh
PREFLIGHT_SHA256 = "65d37c75a82a531c94dc71e7cb6d80fba48dfb1bc73fc9a5fa8a00c37b27e5e4"
REMOTE_SHA256 = "cde4644a4b419aef141662a268c3835570a2ff5c8a957d023f47e809fb0dca74"
SUPERVISOR_CPU = "61"                                                       # plan.json compute.hosts.*.supervisor_cpu
QUIET_GAP_SECONDS = 30                                                      # two quiet reads 30 s apart
POSTEXEC_SECONDS = 10                                                       # bounded read-back; session closes after
REMOTE_COMMAND = "/usr/bin/python3 -I -B -"
SSH_OPTIONS = ("-o", "ControlMaster=no", "-o", "ControlPath=none", "-o", "BatchMode=yes")
ENV_REQUIRED = {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
ENV_OPTIONAL = ("PYTHONPATH",)
FORBIDDEN_TOKENS = {"nice", "taskset", "chrt", "ionice", "setsid", "sudo", "renice", "-O", "-OO", "-I"}
END_REQUIRED = ("--bundle", "--runtime-root", "--native", "--corpus", "--corpus-inventory", "--k4s-manifest-sha256",
                "--sd1-manifest-sha256", "--end-evidence", "--end-evidence-sha256", "--repository",
                "--end-job-sha256", "--round", "--out")
PREFLIGHT_REQUIRED = ("--bundle", "--runtime-root", "--native", "--corpus", "--corpus-inventory",
                      "--k4s-manifest-sha256", "--sd1-manifest-sha256", "--end-evidence", "--end-evidence-sha256",
                      "--repository", "--attempt-parent", "--out", "--hold-seconds")
PREFLIGHT_OPTIONAL = ("--compare-bundle", "--end-job-sha256", "--block-seconds", "--min-samples")
PREFLIGHT_FLAGS = ("--no-reference-work",)
ATTEMPT = {"end": re.compile(r"end-(127x0[34])-r([0-9]{2})-l([0-9]{2})"),
           "preflight": re.compile(r"preflight-(127x0[34])-l([0-9]{2})")}
STAMPS = {"release_upgrade_available": "/var/lib/ubuntu-release-upgrader/release-upgrade-available",
          "updates_available": "/var/lib/update-notifier/updates-available", "apt_lists": "/var/lib/apt/lists"}


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


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    return sha_bytes(Path(path).read_bytes())


def argv_nul(argv):
    return b"".join(x.encode() + b"\0" for x in argv)


def under(path, base):
    p = Path(path)
    return p.is_absolute() and os.path.normpath(path) == path and ".." not in p.parts and base in [
        str(x) for x in p.parents]


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


def validate_argv(argv, kind, host):
    """Structure of the pinned launch argv; returns what the host gate needs."""
    require(kind in ATTEMPT and host in HOST_BASES, "Unknown kind/host")
    require(isinstance(argv, list) and all(isinstance(x, str) and x and "\0" not in x for x in argv),
            "argv must be a list of non-empty strings")
    base = HOST_BASES[host]
    require(len(argv) > 20, "argv too short")
    require(argv[:6] == ["nice", "-n", "10", "taskset", "-c", SUPERVISOR_CPU],
            "argv must start with the frozen inner nice -n 10 taskset -c 61 (no outer prefix)")
    require(argv[6] == "bash" and argv[10] == "bash", "Detach/wrapper must run under bash")
    detach, log, receipt, wrapper, job = argv[7], argv[8], argv[9], argv[11], argv[12]
    parent = base + ("/attempts" if kind == "end" else "/preflight")
    attempt = os.path.basename(job)
    m = ATTEMPT[kind].fullmatch(attempt)
    require(os.path.dirname(job) == parent and under(job, parent) and m and m.group(1) == host,
            "Job must be <declared parent>/<attempt name for this host>")
    require(log == job + "/detach.log" and receipt == job + "/detach.json", "Detach log/receipt must be in the job")
    for path in (detach, wrapper):
        require(under(path, base) and path.endswith(".sh") and not path.startswith(job + "/"),
                "Detach/wrapper must be staged under the host base")
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
    repository = base + "/repository"
    if kind == "end":
        opts = options(m_argv[i + 3:], END_REQUIRED, ())
        require(set(opts) == set(END_REQUIRED), "END argv must give exactly the required options")
        runtime = opts["--runtime-root"]
        require(under(runtime, base) and script == runtime + "/reports/explore/k4s-confirm/end_reference.py",
                "END script must be the runtime's end_reference.py")
        require(re.fullmatch(r"0|[1-9][0-9]?", opts["--round"]) and int(opts["--round"]) == int(m.group(2)),
                "--round must match the attempt name")
        marker, pins = "end_reference.py", {detach: DETACH_SHA256, wrapper: WRAPPER_SHA256["end"]}
        registry = "%s/reports/explore/k4s-confirm/end/registry/round-%02d/%s" % (repository, int(opts["--round"]), host)
    else:
        require(m_argv[i + 3:i + 4] == ["run"], "Preflight must use the run subcommand")
        opts = options(m_argv[i + 4:], PREFLIGHT_REQUIRED + PREFLIGHT_OPTIONAL, PREFLIGHT_FLAGS)
        require(set(PREFLIGHT_REQUIRED) <= set(opts), "Preflight argv lacks a required option")
        require(under(script, base) and os.path.basename(script) == "k4s_end_preflight.py",
                "Preflight script must be the staged k4s_end_preflight.py")
        require(opts["--attempt-parent"] == base + "/attempts", "--attempt-parent must be the declared parent")
        require(float(opts["--hold-seconds"]) >= MIN_PREFLIGHT_HOLD[host], "Preflight hold below the RC-2 minimum")
        marker = "k4s_end_preflight.py"
        pins = {detach: DETACH_SHA256, wrapper: WRAPPER_SHA256["preflight"], script: PREFLIGHT_SHA256}
        registry = None
    require(opts["--out"] == job + "/" + attempt, "--out must be <job>/<attempt>")
    require(opts["--repository"] == repository, "--repository must be the declared clone")
    require(len(pins) == len(set(pins)), "Staged files must be distinct")
    return dict(job=job, attempt=attempt, attempt_parent=parent, measurement_argv=m_argv, python_marker=marker,
                file_pins=pins, registry_dir=registry, wrapper=wrapper)


def check_receive(kind, host, attempt, proof_path, proof_sha256):
    root = RECEIVE[kind] / host / attempt
    require(root.is_dir() and not root.is_symlink(), "05 receive directory was not prepared")
    names = sorted(p.name for p in root.iterdir())
    if kind == "preflight":
        require(names == [], "Preflight receive directory must be empty")
        return dict(receive=str(root), empty=True)
    require(names == ["PREPARED.json"], "END receive directory must hold only PREPARED.json")
    require(proof_path and sha_file(proof_path) == proof_sha256, "Prepare proof SHA mismatch")
    proof = json.loads(Path(proof_path).read_text())
    require(json.loads((root / "PREPARED.json").read_text()) == proof, "Prepare proof differs from PREPARED.json")
    require(proof["receive"] == str(root) and proof["created_empty"] is True and proof["utc"] < iso(),
            "Prepare proof does not name this receive directory or postdates now")
    return dict(receive=str(root), prepare_proof_sha256=proof_sha256, prepared_utc=proof["utc"])


def pinned_json(spec, label):
    path, _, digest = spec.rpartition(":")
    require(path and sha_file(path) == digest, label + " SHA mismatch")
    return json.loads(Path(path).read_text()), digest


def prerequisites(a):
    """RC-9: both preflights verified passed before any claim; 04 END only after 03's complete, ACKed seal."""
    out = {}
    if a.kind != "end":
        return out
    passed = {}
    for spec in a.preflight_verified or []:
        doc, digest = pinned_json(spec, "Preflight verification")
        require(doc.get("passed") is True and doc.get("registry_and_attempt_parent_unchanged") is True,
                "Preflight did not pass: " + str(doc.get("host")))
        passed[doc["host"]] = digest
    require(set(passed) == set(HOST_BASES), "Both host preflights must be verified passed (RC-9)")
    out["preflights"] = passed
    if a.host == "127x04":
        require(a.prior_03_ack, "04 END requires 03's verified complete seal (RC-9)")
        ack, digest = pinned_json(a.prior_03_ack, "03 DURABLE-ACK")
        require(ack.get("host") == "127x03" and ack.get("classification") == "SEALED" and
                ack.get("status") == "complete" and ack.get("ack_allowed") is True, "03 seal is not complete+ACKed")
        out["prior_03_ack_sha256"] = digest
    return out


def local_controlmaster(host):
    """No multiplexing master to the host on 05 (ssh -O check talks only to a local control socket)."""
    check = subprocess.run(["ssh", "-O", "check", host], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                           timeout=30)
    require(check.returncode != 0, "A ControlMaster to %s is open on 05; close it (ssh -O exit) first" % host)
    return dict(ssh_O_check_rc=check.returncode, stderr=check.stderr.strip()[-200:])


def compose(config):
    body = (HERE / "k4s_end_launch_remote.py").read_bytes()
    require(sha_bytes(body) == REMOTE_SHA256, "Host gate program differs from its pin")
    return ("import json\nCONFIG = json.loads(%r)\n" % json.dumps(config, sort_keys=True)).encode() + body


def launch(a):
    require(socket.gethostname() == "127x05" and not optimized(), "The gate runs on 127x05, not under -O")
    receipt_out = Path(a.receipt_out)
    require(not receipt_out.exists(), "Receipt already exists")
    argv_bytes = Path(a.argv_json).read_bytes()
    argv = json.loads(argv_bytes)
    require(sha_bytes(argv_nul(argv)) == a.argv_sha256, "Launch argv differs from its pin")
    shape = validate_argv(argv, a.kind, a.host)
    quiet_cmd = Path(a.quiet_cmd).read_bytes()
    require(sha_bytes(quiet_cmd) == QUIET_V3_SHA256, "Quiet read is not the approved v3 command")
    require(a.clearance_seconds >= 7200 and a.window_seconds >= 3600, "Clearance < 2 h or window < 1 h")
    allow = {}
    for item in a.allow_timer or []:
        unit, _, reason = item.partition("=")
        require(unit.endswith(".timer") and reason.strip(), "--allow-timer needs UNIT.timer=justification")
        allow[unit] = reason
    record = dict(schema="clasher.k4s.end-launch-receipt.v1", kind=a.kind, host=a.host, job=shape["job"],
                  attempt=shape["attempt"], gate_sha256=sha_file(__file__), remote_sha256=REMOTE_SHA256,
                  argv_json_sha256=sha_bytes(argv_bytes), argv_nul_sha256=a.argv_sha256, launch_command=argv,
                  measurement_argv=shape["measurement_argv"], wrapper_sha256=WRAPPER_SHA256[a.kind],
                  quiet_read_v3_sha256=QUIET_V3_SHA256, allow_timers=allow, outcomes_sealed=True,
                  scientific_games=False, C5_no_further_SSH=True, launched=False)
    record["receive"] = check_receive(a.kind, a.host, shape["attempt"], a.prepare_proof, a.prepare_proof_sha256)
    record["prerequisites"] = prerequisites(a)
    record["second_attempt_ruling"] = a.second_attempt_ruling
    record["local_controlmaster"] = local_controlmaster(a.host)
    config = dict(host=a.host, kind=a.kind, quiet_cmd=quiet_cmd.decode(), quiet_gap_seconds=QUIET_GAP_SECONDS,
                  helper_pid=HELPER_PIDS[a.host], clearance_seconds=a.clearance_seconds, allow_timers=allow,
                  window_seconds=a.window_seconds, stamps=STAMPS, launch_argv=argv, argv_sha256=a.argv_sha256,
                  supervisor_cpu=SUPERVISOR_CPU, job=shape["job"], attempt_parent=shape["attempt_parent"],
                  file_pins=shape["file_pins"], registry_dir=shape["registry_dir"],
                  second_attempt_ruling=a.second_attempt_ruling, python_marker=shape["python_marker"],
                  postexec_seconds=POSTEXEC_SECONDS)
    program = compose(config)
    record["composed_program_sha256"] = sha_bytes(program)
    ssh = ["ssh", *SSH_OPTIONS, a.host, REMOTE_COMMAND]
    record["launch_SSH_argv"] = ssh
    if a.dry_run:
        sys.stdout.write(program.decode())
        return 0
    record["session_open_utc"] = iso()
    try:
        done = subprocess.run(ssh, input=program, capture_output=True, timeout=600)
        stdout, stderr, rc = done.stdout.decode(errors="replace"), done.stderr.decode(errors="replace"), done.returncode
    except subprocess.TimeoutExpired as error:
        stdout, stderr, rc = (error.stdout or b"").decode(errors="replace"), "local timeout", None
    record["session_close_utc"] = iso()
    record.update(launch_SSH_exit_code=rc, launch_SSH_stderr=stderr[-2000:])
    lines = [x for x in stdout.splitlines() if x.startswith("__K4S_GATE_RESULT__ ")]
    host_result = json.loads(lines[-1][len("__K4S_GATE_RESULT__ "):]) if len(lines) == 1 else None
    record["host_gate"] = host_result
    if host_result is not None:
        record["launched"] = host_result["launched"] is True
        record["utc"] = host_result.get("utc")
        record["C5_preexec_gate"] = host_result.get("C5_preexec_gate")
        record["postexec"] = host_result.get("postexec")
    with receipt_out.open("x") as stream:
        stream.write(json.dumps(record, indent=1, sort_keys=True) + "\n")
    print(json.dumps(dict(receipt=str(receipt_out), receipt_sha256=sha_file(receipt_out), launched=record["launched"],
                          failures=(host_result or {}).get("failures"), ssh_rc=rc), sort_keys=True))
    if host_result is None:
        return 5                                    # unknown host state: STOP, do not relaunch
    if record["launched"]:
        return 0 if rc == 0 else 6                  # launched; a nonzero SSH status is recorded for review
    return 4 if host_result.get("job_created_utc") else 3


def admission(a):
    """Session close (05 clock) vs. guard admission (host clock) from the sealed, ACKed receipt (RC-7)."""
    require(socket.gethostname() == "127x05" and not optimized(), "Runs on 127x05, not under -O")
    require(sha_file(a.launch_receipt) == a.launch_receipt_sha256, "Launch receipt SHA mismatch")
    launch_ = json.loads(Path(a.launch_receipt).read_text())
    root = RECEIVE[launch_["kind"]] / launch_["host"] / launch_["attempt"]
    sub = "durable-measurement" if launch_["kind"] == "end" else "preflight"
    if launch_["kind"] == "end":
        require((root / "DURABLE-ACK.json").is_file(), "Run the approved verifier first (C-d)")
    seal = root / sub / "receipt-manifest.json"
    require((root / sub / "receipt-manifest.sha256").read_text().split() == [sha_file(seal), "receipt-manifest.json"],
            "Seal SHA mismatch")
    files = json.loads(seal.read_text())["files"]
    target = root / sub / "guard-admission.json"
    require(files.get("guard-admission.json") == sha_file(target), "guard-admission.json not sealed")
    admitted = json.loads(target.read_text())["utc"]
    closed = datetime.datetime.strptime(launch_["session_close_utc"], "%Y-%m-%dT%H:%M:%SZ") \
        .replace(tzinfo=datetime.timezone.utc).timestamp()
    out = dict(schema="clasher.k4s.end-launch-admission.v1", host=launch_["host"], attempt=launch_["attempt"],
               launch_receipt_sha256=a.launch_receipt_sha256, session_close_utc=launch_["session_close_utc"],
               guard_admission_utc=iso(admitted), seconds_close_to_admission=admitted - closed,
               closed_before_admission=closed + 1 < admitted,
               note="05 clock (close, 1 s resolution) vs host clock (admission); skew not corrected")
    with Path(a.out).open("x") as stream:
        stream.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps(out, sort_keys=True))
    return 0 if out["closed_before_admission"] else 2


def parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 allow_abbrev=False)
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("launch", allow_abbrev=False)
    p.add_argument("--host", choices=sorted(HOST_BASES), required=True)
    p.add_argument("--kind", choices=("end", "preflight"), required=True)
    p.add_argument("--argv-json", type=Path, required=True)
    p.add_argument("--argv-sha256", required=True, help="sha256 of the NUL-joined argv")
    p.add_argument("--quiet-cmd", type=Path, required=True)
    p.add_argument("--receipt-out", type=Path, required=True)
    p.add_argument("--prepare-proof", type=Path)
    p.add_argument("--prepare-proof-sha256")
    p.add_argument("--allow-timer", action="append", metavar="UNIT.timer=JUSTIFICATION")
    p.add_argument("--clearance-seconds", type=int, default=7200)
    p.add_argument("--window-seconds", type=int, default=7200)
    p.add_argument("--second-attempt-ruling", help="coordinator ruling reference for a host's second attempt")
    p.add_argument("--preflight-verified", action="append", metavar="PATH:SHA256")
    p.add_argument("--prior-03-ack", metavar="PATH:SHA256")
    p.add_argument("--dry-run", action="store_true")
    q = sub.add_parser("admission", allow_abbrev=False)
    q.add_argument("--launch-receipt", type=Path, required=True)
    q.add_argument("--launch-receipt-sha256", required=True)
    q.add_argument("--out", type=Path, required=True)
    return ap


def main(argv=None):
    a = parser().parse_args(argv)
    return launch(a) if a.command == "launch" else admission(a)


if __name__ == "__main__":
    raise SystemExit(main())
