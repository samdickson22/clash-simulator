#!/usr/bin/env python3
"""S1b (PREREG-K4S END, Q2/E3): exact-path reader for the guard admissions. r2: safe_input adoption. A delta beside S1.

CANDIDATE: requires Sol review and a coordinator GO before any live run. Runs FROM 127x05 and reads 127x03 and
127x04 read-only over ssh. Never run inside an END timing window or a preflight (RC-2) measurement on any host.

What it reads: exactly the files the frozen K4S code wrote into each host's latest K4S job (Q2: replacement-r4,
cross-checked against the committed run-r1/rounds/history.json, pinned 94ee52e0):
    127x03  /mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r4/system-bus-admission.json
            /mpac/sdicks02/jobs/clasher/k4s-confirm-replacement-r4/idle-services.json
    127x04  /mpac/sdicks02/jobs-k4s/k4s-confirm-replacement-r4/system-bus-admission.json
plus one absence probe per host: <root>/k4s-confirm-replacement-r5 (r4 must still be the latest job).

Remote reads (S1b-F1): ONE login per host (2 in total), each `si.remote_check`: the pinned safe_input reader program
(sha256 = end_prep_common.REMOTE_PROGRAM_SHA256) is shipped on ssh stdin to `nice -n 19 /usr/bin/python3 -I -S -`
with the request as one hex word. The host program name-gates every item first, checks the node name, walks every
component from / with O_DIRECTORY|O_NOFOLLOW, and for each leaf requires a regular file with st_nlink == 1 within
1 MiB (fstatat before open, fstat after) BEFORE any byte of ANY item is read; a hard-linked, symlinked, special or
oversize admission refuses with zero content reads. Locally `si.parse_remote_response` re-checks the exact request,
host, nlink == 1, sizes and SHA-256 of every returned byte. The read role is exact-name only (grant
reporting-job-exact): nothing else can be named, listed or globbed.

Output (E3): <dest>/end-guard-admissions/<host>-<name> (0444; the exact committed layout
reports/explore/k4s-confirm/end-guard-admissions/<host>-<name>.json) + <dest>/s1b-admissions-manifest.json. <dest> is
created FIRST (exclusively, canonical parent, permitted root) so every later refusal leaves a write-once
S1B-REFUSAL-*.json receipt there. --dry-run prints the planned requests and ssh argv; no ssh, no writes.
"""
import argparse
import json
import os
import shlex
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if sys.path[:1] != [_HERE]:
    sys.path.insert(0, _HERE)
import end_prep_common as C                                           # noqa: E402

if os.path.dirname(os.path.abspath(C.__file__)) != _HERE:
    raise SystemExit("end_prep_common imported from outside " + _HERE)

si = C.si
require = C.require
SCHEMA = "clasher.k4s.end-admissions-copy.v2"
STUDY = "reports/explore/k4s-confirm"
HISTORY = STUDY + "/run-r1/rounds/history.json"
HISTORY_SHA256 = "94ee52e0755e56dd103989cef00fcd4d130768cc3c266415b71b68e7d3451487"   # origin/main 27b54d9d (b5bc0c86)
HOSTS = ("127x03", "127x04")
NAMESPACE = "k4s-confirm-replacement-r4"
NEXT_NAMESPACE = "k4s-confirm-replacement-r5"
JOB_ROOTS = dict(si.Q4_GUARD_PARENTS)      # the K4S job roots: 03 /mpac/sdicks02/jobs/clasher, 04 /mpac/sdicks02/jobs-k4s
BUS_NAME, IDLE_NAME = "system-bus-admission.json", "idle-services.json"
NAMES = {"127x03": (BUS_NAME, IDLE_NAME), "127x04": (BUS_NAME,)}
MAX_BYTES = 1024 * 1024
E3_DIR = si.E3_ADMISSIONS_DIR                                   # reports/explore/k4s-confirm/end-guard-admissions
E3_LOCAL = "end-guard-admissions"                               # the same leaf directory in <dest>
DEFAULT_REPOSITORY = "/mpac/sdicks02/repos/clasher"
SSH_BINARY = si.SSH_BINARY                                      # /usr/bin/ssh (tests substitute a fake host)
# t1/system_bus.py:5 KEYS; identities from the committed r4 host admissions (14:04Z), process rows uid 103 (E3 pins).
BUS_KEYS = ("pid", "start_ticks", "exe", "cmdline_sha256", "uid")
DBUS_CMDLINE_SHA = "f481db6887b1454cde723322eee10a57f08a0789ab8db6f16d41ac2ad3329749"
BUS_IDENTITY = {
    "127x03": dict(pid=2049, start_ticks=1273, exe="/usr/bin/dbus-daemon", cmdline_sha256=DBUS_CMDLINE_SHA, uid=103),
    "127x04": dict(pid=2005, start_ticks=1032, exe="/usr/bin/dbus-daemon", cmdline_sha256=DBUS_CMDLINE_SHA, uid=103),
}
# idle_services.py:7 identity keys; perception v4 validation-cache service on 03 (round.sh finalize check).
IDLE_KEYS = ("pid", "ppid", "pgid", "start_ticks", "cmdline_sha256", "uid")
IDLE_IDENTITY = dict(pid=2180947, ppid=2180946, pgid=2180934, start_ticks=139691386,
                     cmdline_sha256="16152ceb7942621141a2d8d91189affdeacde28ad1a9059ffbadde5e9bde799a", uid=3822945)
IDLE_SERVICE_NAME = "v4-validation-cache-renewed-20261010-03r1"
STALE = " (stale identity: STOP; a re-pin needs a coordinator ruling from fresh outcome-blind copies, E3)"


def e3_name(host, name):
    return "%s-%s" % (host, name)


# ---------------------------------------------------------------- admission content (shared with S3)

def check_admission(host, name, data):
    """Structural + pinned-identity check of one admission's bytes (strict JSON). Returns an identity summary."""
    require(host in HOSTS and name in NAMES.get(host, ()), "check", "%s is not an END guard admission for %s"
            % (name, host))
    require(isinstance(data, bytes) and 0 < len(data) <= MAX_BYTES, "size", "%s/%s: size outside (0, 1 MiB]"
            % (host, name))
    doc = si.loads_strict(data, "%s/%s" % (host, name))
    require(isinstance(doc, dict) and doc.get("host") == host, "check", "%s/%s: host field is %r"
            % (host, name, doc.get("host") if isinstance(doc, dict) else None))
    if name == BUS_NAME:
        identity = doc.get("identity")
        require(isinstance(identity, dict) and sorted(identity) == sorted(BUS_KEYS), "check",
                "%s/%s: identity keys differ from system_bus.KEYS" % (host, name))
        require(identity == BUS_IDENTITY[host], "check", "%s/%s: dbus identity %s != pinned %s%s"
                % (host, name, identity, BUS_IDENTITY[host], STALE))
        return dict(name=name, pid=identity["pid"], start_ticks=identity["start_ticks"], utc=doc.get("utc"))
    services = doc.get("services")
    require(isinstance(services, list) and len(services) == 1 and isinstance(services[0], dict), "check",
            "%s/%s: exactly one idle service expected" % (host, name))
    service = services[0]
    identity = service.get("service")
    require(isinstance(identity, dict) and sorted(identity) == sorted(IDLE_KEYS), "check",
            "%s/%s: service identity keys differ from idle_services.identity" % (host, name))
    require(identity == IDLE_IDENTITY and service.get("name") == IDLE_SERVICE_NAME, "check",
            "%s/%s: idle service identity/name differs from PID 2180947 of record%s" % (host, name, STALE))
    require(isinstance(service.get("wrapper_trio"), list) and len(service["wrapper_trio"]) == 3, "check",
            "%s/%s: wrapper_trio must hold 3 identities" % (host, name))
    return dict(name=name, pid=identity["pid"], start_ticks=identity["start_ticks"], utc=doc.get("utc"))


# ---------------------------------------------------------------- remote requests (safe_input reader)

def remote_policy(host):
    require(host in HOSTS, "policy", "unknown END host %r" % (host,))
    exact = tuple("%s/%s" % (NAMESPACE, n) for n in NAMES[host]) + (NEXT_NAMESPACE,)
    return si.Policy(host, [si.Role("job", JOB_ROOTS[host], "read", MAX_BYTES, exact=exact,
                                    grants=("reporting-job-exact",))], remote=True)


def remote_items(host):
    items = [{"role": "job", "rel": NEXT_NAMESPACE, "kind": "absent"}]
    items += [{"role": "job", "rel": "%s/%s" % (NAMESPACE, n), "kind": "file", "content": True} for n in NAMES[host]]
    return items


def max_content(host):
    return MAX_BYTES * len(NAMES[host])


def remote_paths(host):
    return ["%s/%s/%s" % (JOB_ROOTS[host], NAMESPACE, n) for n in NAMES[host]]


def repo_role(repository):
    return si.Role("repo", C.input_dir(repository, "--repository"), "read", 16 << 20, exact=(HISTORY,))


def committed_latest(policy, repository, commit):
    """The committed rounds/history.json (pinned bytes) must end at the replacement-r4 namespace (Q2)."""
    require(isinstance(commit, str) and si._OID.fullmatch(commit) is not None and len(commit) == 40, "policy",
            "--commit must be a full 40-hex commit")
    raw = si.git_show_file(policy, "repo", si.GitRepo(work_tree=repository), commit, HISTORY, 16 << 20,
                           expected_sha256=HISTORY_SHA256)
    history = si.loads_strict(raw, HISTORY)
    require(isinstance(history, list) and history and isinstance(history[-1], dict)
            and history[-1].get("namespace") == NAMESPACE
            and sum(isinstance(r, dict) and r.get("namespace") == NAMESPACE for r in history) == 1, "check",
            "committed history does not end at " + NAMESPACE)
    return C.sha_bytes(raw)


def read_host(host, log=print):
    """One login: the pinned reader over the exact items. Returns [{name, remote_path, size, sha256, nlink, data}]."""
    records = si.remote_check(remote_policy(host), remote_items(host), max_content(host), ssh_binary=SSH_BINARY,
                              timeout=300)
    rows = []
    for record in records:
        if record["kind"] != "file":
            continue
        require(record["nlink"] == 1 and "content" in record, "nlink", "remote %s: not a single-link read" % record["rel"])
        name = record["rel"].split("/", 1)[1]
        rows.append(dict(name=name, remote_path="%s/%s" % (record["root"], record["rel"]), size=record["size"],
                         sha256=record["sha256"], nlink=record["nlink"], data=record["content"]))
    require([r["name"] for r in rows] == list(NAMES[host]), "remote", "%s: reply names differ" % host)
    return rows


# ---------------------------------------------------------------- run

def plan_text(a):
    out = dict(mode="dry-run", logins=len(HOSTS), reader_program_sha256=si.remote_program_sha256(),
               files={h: remote_paths(h) for h in HOSTS},
               next_probe={h: "%s/%s" % (JOB_ROOTS[h], NEXT_NAMESPACE) for h in HOSTS},
               expected_identities=dict(bus=BUS_IDENTITY, idle_127x03=IDLE_IDENTITY))
    lines = [json.dumps(out, indent=1, sort_keys=True)]
    for host in HOSTS:
        request = si.build_remote_request(remote_policy(host), remote_items(host), max_content(host))
        lines.append("# login %s; request %s" % (host, request.decode()))
        lines.append(shlex.join(si.remote_ssh_argv(host, request, SSH_BINARY)))
    return lines


def dest_policy(repository, parent, leaf):
    names = tuple("%s/%s" % (E3_LOCAL, e3_name(h, n)) for h in HOSTS for n in NAMES[h])
    return si.Policy(C.local_host(), [
        repo_role(repository), C.code_role(),
        si.Role("dest-parent", parent, "write", 1 << 20, exact=(leaf,)),
        si.Role("dest", parent + "/" + leaf, "write", 16 << 20,
                exact=names + ("s1b-admissions-manifest.json",), patterns=("S1B-REFUSAL-*.json",)),
        si.Role("dest-read", parent + "/" + leaf, "read", 16 << 20,
                exact=names + ("s1b-admissions-manifest.json",))])


def run(a, log=print):
    started = C.utc()
    if a.dry_run:
        policy = si.Policy(C.local_host(), [repo_role(a.repository)])
        committed_latest(policy, a.repository, a.commit)
        for line in plan_text(a):
            log(line)
        return None
    parent, leaf = C.output_path(a.dest, "--dest")
    policy = dest_policy(a.repository, parent, leaf)
    with si.Writer(policy, "dest-parent") as top:
        top.mkdir_excl(leaf)                                          # first: every later refusal leaves a receipt
    writer = si.Writer(policy, "dest")
    logins = []
    try:
        require(bool(a.outside_end_window), "policy",
                "live run requires --outside-end-window '<coordinator GO / window reference>'")
        history_sha = committed_latest(policy, a.repository, a.commit)
        results = {}
        for host in HOSTS:                                            # every check on both hosts before any write
            request = si.build_remote_request(remote_policy(host), remote_items(host), max_content(host))
            logins.append(dict(host=host, started_utc=C.utc(), request_sha256=C.sha_bytes(request),
                               argv=si.remote_ssh_argv(host, request, SSH_BINARY)))
            log("[%s] ssh %s" % (C.utc(), host))
            rows = read_host(host, log)
            logins[-1]["finished_utc"] = C.utc()
            for row in rows:
                row["identity"] = check_admission(host, row["name"], row["data"])
            results[host] = rows
        writer.mkdir_excl(E3_LOCAL)
        files = []
        for host in HOSTS:
            for row in results[host]:
                rel = "%s/%s" % (E3_LOCAL, e3_name(host, row["name"]))
                written = writer.create_excl(rel, row["data"], 0o444)
                require(written["sha256"] == row["sha256"], "sha", "local copy differs: " + rel)
                again = si.sha256_input(policy, "dest-read", rel, expected_size=row["size"])
                require(again["sha256"] == row["sha256"], "sha", "local re-read differs: " + rel)
                files.append(dict(host=host, name=row["name"], remote_path=row["remote_path"],
                                  remote_size=row["size"], remote_sha256=row["sha256"], remote_nlink=row["nlink"],
                                  local_path=rel, local_sha256=again["sha256"],
                                  e3_repository_path="%s/%s" % (E3_DIR, e3_name(host, row["name"])),
                                  identity=row["identity"]))
        manifest = dict(schema=SCHEMA, status="copied", started_utc=started, finished_utc=C.utc(),
                        outside_end_window=a.outside_end_window, repository_commit=a.commit,
                        history_sha256=history_sha, namespace=NAMESPACE, ssh_logins=len(logins), logins=logins,
                        reader_program_sha256=si.remote_program_sha256(), safe_input_sha256=C.SAFE_INPUT_SHA256,
                        script_sha256=C.code_sha(policy, "s1b_copy_admissions.py"),
                        common_sha256=C.code_sha(policy, "end_prep_common.py"), files=files,
                        commit_instructions="copy <dest>/%s/* to %s/ unchanged; secret-scan; commit outcome-blind "
                                            "before the evidence commit P (E3)" % (E3_LOCAL, E3_DIR))
        writer.write_json_once("s1b-admissions-manifest.json", manifest)
    except BaseException as error:
        si.write_refusal_receipt(writer, "S1B", error, {"logins": logins, "started_utc": started})
        writer.close()
        raise
    writer.close()
    manifest_sha = si.sha256_input(policy, "dest-read", "s1b-admissions-manifest.json")["sha256"]
    for f in files:
        log("  %s/%s/%s  sha256 %s" % (parent, leaf, f["local_path"], f["local_sha256"]))
    log("S1b OK: %d files, %d logins, manifest sha256 %s" % (len(files), len(logins), manifest_sha))
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], allow_abbrev=False)
    ap.add_argument("--repository", default=DEFAULT_REPOSITORY, help="clone holding the commit (git read via si)")
    ap.add_argument("--commit", required=True, help="full commit holding run-r1/rounds/history.json (pinned)")
    ap.add_argument("--dest", help="new local destination (must not exist; permitted root; canonical parent)")
    ap.add_argument("--outside-end-window", default="", help="required for a live run: GO/window reference")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not a.dry_run and a.dest is None:
        ap.error("--dest is required unless --dry-run")
    try:
        run(a)
    except si.Refusal as error:
        print("S1b REFUSED: " + str(error), file=sys.stderr)
        return 2
    except Exception as error:                                        # fail closed on anything unexpected
        print("S1b FAILED: %s: %s" % (type(error).__name__, error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
