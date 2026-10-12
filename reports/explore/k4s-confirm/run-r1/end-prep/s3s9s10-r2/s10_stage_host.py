#!/usr/bin/env python3
"""S10 (PREREG-K4S END, A2 staging): ship END inputs from 127x05 to ONE host. r2: safe_input adoption. CANDIDATE:
host-touching; Sol review and a coordinator A2 GO before any live run. Never inside an END timing window or a
preflight measurement on any host.

Components (at least one; bundles only, never raw Q6 inputs: ruling P2 decision 4):
  --runtime S9OUT --runtime-manifest-sha256 S   the S9 runtime (re-verified)   -> <base>/runtime/runtime-<commit12>/
  --bundle DIR TIERS_PINS_SHA256 RECEIPT_SHA256  an S4 fleet-reference bundle (repeatable; production only)
                                                                                -> <base>/bundles/<basename>/
  --guard-job S3OUT --guard-job-name NAME --guard-manifest-sha256 S   an S3 guard job (re-verified)
                                                                                -> its Q4 target (separate parent)
with <base> = si.END_BASES (03 /mpac/sdicks02/jobs/clasher/k4s-end-r1, 04 /mpac/sdicks02/jobs-k4s/k4s-end-r1: the
S5/S6/S7 bases, S10-F2) holding attempts/, preflight/, repository/, runtime/, bundles/ (RC-6; --print-roots). S10
creates <base> with attempts/ preflight/ runtime/ bundles/ only when told (--create-base, first staging on a host);
repository/ is provisioned by its own authorized step. Guard jobs are siblings under the Q4 parent, never in <base>.

Local side, before any login: every read through safe_input roles (canonical roots, names gated before any syscall,
component-wise no-follow, st_nlink == 1, expected SHAs): S9.verify (manifest pinned), S3.verify (manifest pinned),
and per bundle: tiers-pins.json / tiers-pins.sha256 / assembly-receipt.json read with expected SHAs, S4 test-only
bundles refused (k4s_s4_synthetic, SYNTHETIC-TEST-ONLY, production_pins != true, *SYNTHETIC* names: S10-F4), every
file hashed and equal to its pin, production identities, per-host admissions, runtime/measurement consistency with
the staged (or --runtime-manifest-for-checks) runtime, and guard-job byte equality when its guard job is staged too.

Logins (each `ssh -T -o BatchMode=yes -o ControlMaster=no -o ControlPath=none ...`, recorded):
  P-check   si.remote_check (pinned reader): <base> and its four subdirs (or, with --create-base, <base> absent) and
            the Q4 parent are canonical directories (every ancestor lstat'ed: no symlink); every target and its
            .partial absent.
  P-facts   hostname, df, who, each captured with its own exit status (`x=$(cmd)`; `@@RC|name|$?`); any nonzero
            status refuses before its output is used (S10-F3); free space >= bytes + 50 GiB.
  [base]    --create-base only: si.remote_receive creating <base> exclusively with the four subdirs, no files.
  R-<i>     one si.remote_receive per component (D4): the pinned receive program (bootstrap-verified SHA-256) creates
            <target>.partial EXCLUSIVELY under its canonical parent, then every directory (mkdirat) and file
            (O_CREAT|O_EXCL|O_NOFOLLOW, streamed, hashed, fsynced, mode 0444/0555); refuses an existing name of any
            kind, a symlinked ancestor, a name family, a size/SHA mismatch or extra bytes; its receipt (every file's
            size, SHA-256, st_nlink == 1, mode) is validated strictly (R7: plain single-link copies).
  F         ONE session: the pinned reader re-checks every .partial is a canonical directory and every final name is
            absent; then (runtime/bundles) `chmod -R a-w` and `mv -n -T` each .partial into place, every step's
            status echoed and checked. The reader-to-mv window is the accepted residual.
  POST      si.remote_check: every final is a canonical directory with the SAME dev/ino the F check saw for its
            .partial (and mode a-w for runtime/bundles); every .partial absent.
Nothing is ever deleted on a host (no rm/rmdir/unlink anywhere). A refusal after the first receive records the exact
.partial roots in the record's S10-REFUSAL-*.json; their cleanup needs a separately authorized step.
"""
import argparse
import json
import os
import re
import shlex
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if sys.path[:1] != [_HERE]:
    sys.path.insert(0, _HERE)
import end_prep_common as C                                           # noqa: E402

if os.path.dirname(os.path.abspath(C.__file__)) != _HERE:
    raise SystemExit("end_prep_common imported from outside " + _HERE)
S3 = C.import_sibling("s3_guard_job")
S9 = C.import_sibling("s9_end_runtime")

si = C.si
require = C.require
SCHEMA = "clasher.k4s.end-staging.v2"
ROOTS_SCHEMA = "clasher.k4s.end-rc6-roots.DRAFT.v1"
HOSTS = ("127x03", "127x04")
END_BASES = dict(si.END_BASES)
GUARD_PARENTS = dict(si.Q4_GUARD_PARENTS)
BASE_SUBDIRS = ("attempts", "preflight", "runtime", "bundles")      # created with <base>; repository/ separately
HEADROOM = 50 * 1024 ** 3
SSH_BINARY = si.SSH_BINARY
REMOTE_TOOLS = {"hostname": "/usr/bin/hostname", "df": "/usr/bin/df", "who": "/usr/bin/who",
                "chmod": "/usr/bin/chmod", "mv": "/usr/bin/mv", "sh": "/bin/sh"}
BUNDLE_SCHEMA = "clasher.e4v3.inputs.v1"
ASSEMBLY_SCHEMA = "clasher.k4s.end-fleet-reference-assembly.v2"
BUNDLE_MANIFEST, BUNDLE_SIDE, BUNDLE_RECEIPT = "tiers-pins.json", "tiers-pins.sha256", "assembly-receipt.json"
BUNDLE_UNPINNED = (BUNDLE_MANIFEST, BUNDLE_SIDE, BUNDLE_RECEIPT)
SYNTHETIC_KEY, SYNTHETIC_STAMP, SYNTHETIC_MARKER = "k4s_s4_synthetic", "SYNTHETIC-TEST-ONLY", "synthetic"
INPUT_PINS = {"states.pkl": "0addf7c0176c358e19f816a1079208eea370a2764d43a44fc9c1993811ead6f1",
              "states-rows.json": "bcd307770b70394878f7da17a97e4a1baa10f6efd7ea06d6b4240901dc0336e5",
              "states-rows.bin": "8cc2f611e867dc3891cdab643365193be685057b802cf73847c7fd6c91d6a1cb"}
# Production identities every shipped bundle must pin (frozen models; Q6 state bytes, carried inside the bundle).
PRODUCTION_PINS = dict({"v1.pt": "d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed",
                        "R3a.pt": "37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85",
                        "R3a-calibration.json": "e300353346983e888d896b20412d4075496a6f14ef3625cefc7eeadacec5e414"},
                       **INPUT_PINS)
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
RECORD_NAMES = ("s10-staging-manifest.json",)


def roots(host):
    """The RC-6 roots of one host (P2 decision 3): the END base children plus the separate Q4 guard-job parent."""
    require(host in HOSTS, "policy", "host must be 127x03 or 127x04")
    base = END_BASES[host]
    return dict(base=base, runtime=base + "/runtime", bundles=base + "/bundles", repository=base + "/repository",
                attempts=base + "/attempts", preflight=base + "/preflight", guard_job_parent=GUARD_PARENTS[host],
                guard_job_names=S3.JOB_NAME.pattern)


def roots_declaration():
    return dict(schema=ROOTS_SCHEMA, status="DRAFT (RC-6; needs coordinator adoption)",
                rulings="P2 decision 3 (k4s-end-r1 bases), Q4 (guard parents), P2-3/RC-2 (preflight), D4 (receive)",
                hosts={h: dict(roots(h), runtime_layout="runtime/runtime-<P commit 12>/ (S9 tree, a-w)",
                               bundle_layout="bundles/<S4 bundle basename>/ (a-w)",
                               guard_job_layout="<guard_job_parent>/k4s-end-guard-r1-rdRR-aNN | -pfNN (dirs writable)",
                               created_by_s10=["base"] + ["base/" + d for d in BASE_SUBDIRS],
                               provisioned_separately=["repository (the --repository clone; S6/S7)"],
                               written_by_s7=["attempts/<attempt>", "preflight/<preflight>"]) for h in HOSTS})


class Component(object):
    def __init__(self, kind, host, parent, leaf, files, dirs, extra):
        self.kind, self.host, self.parent, self.leaf = kind, host, parent, leaf
        self.final, self.partial = parent + "/" + leaf, parent + "/" + leaf + ".partial"
        self.files, self.dirs, self.extra = files, dirs, extra
        self.bytes = sum(f["size"] for f in files)

    def dest_policy(self):
        grants = ("guard-job",) if self.kind == "guard-job" else ()
        exemptions = tuple(x for x, key in (("E4", "e4"), ("E5", "e5")) if any(f.get(key) for f in self.files))
        return si.Policy(self.host, [si.Role("dest", self.partial, "write", si.MAX_ROLE_SIZE, patterns=("**",),
                                             exemptions=exemptions, grants=grants)], remote=True)

    def summary(self):
        return dict(kind=self.kind, final=self.final, partial=self.partial, files=len(self.files), dirs=len(self.dirs),
                    bytes=self.bytes, inventory_sha256=C.canonical_sha([[f["dst"], f["size"], f["sha256"], f["mode"]]
                                                                         for f in self.files]), **self.extra)


# ---------------------------------------------------------------- local components (verified before any login)

def runtime_component(policy, host, sha, log):
    manifest = S9.verify(policy, "s9", sha, log=log)
    files = []
    for rel, f in sorted(manifest["inventory"]["files"].items()):
        files.append(dict(src_role="s9-runtime", src_rel=rel, dst=rel, size=f["size"], sha256=f["sha256"],
                          mode=0o555 if f.get("executable") else 0o444, e4=bool(f.get("e4")), e5=bool(f.get("e5"))))
    leaf = "runtime-" + manifest["commit"][:12]
    return Component("runtime", host, roots(host)["runtime"], leaf, files, manifest["inventory"]["dirs"],
                     dict(commit=manifest["commit"], runtime_files_sha256=manifest["runtime_files_sha256"],
                          measurement_files_sha256=manifest["measurement_files_sha256"],
                          runtime_manifest_sha256=sha)), manifest


def guard_component(policy, host, job, sha, log):
    manifest = S3.verify(policy, "s3", policy.role("s3-out").root, job, sha, log=log)
    require(manifest["host"] == host, "check", "guard job was built for " + manifest["host"])
    final = S3.check_target(host, manifest["target_job"])
    files = [dict(src_role="s3-job", src_rel=job + "/" + r["path"], dst=r["path"], size=r["size"], sha256=r["sha256"],
                  mode=0o444, e4=False) for r in manifest["inventory"]]
    return Component("guard-job", host, GUARD_PARENTS[host], job, files, manifest["dirs"],
                     dict(job=job, kind_detail=manifest["job"], bindings=manifest["bindings"],
                          guard_manifest_sha256=sha)), manifest


def refuse_test_only(name, manifest, receipt, tiers_sha, host):
    """S10-F4: an S4 test-only (synthetic-pins) bundle is refused before staging, whatever its file pins say."""
    require(SYNTHETIC_MARKER not in name.casefold(), "check", "bundle %s: a *SYNTHETIC* (test-only) bundle name" % name)
    require(SYNTHETIC_KEY not in manifest, "check", "bundle %s: tiers-pins.json carries the S4 test stamp %s"
            % (name, SYNTHETIC_KEY))
    require(SYNTHETIC_STAMP not in json.dumps(manifest) and SYNTHETIC_STAMP not in json.dumps(receipt), "check",
            "bundle %s: SYNTHETIC-TEST-ONLY stamp present" % name)
    require(isinstance(receipt, dict) and receipt.get("schema") == ASSEMBLY_SCHEMA
            and receipt.get("production_pins") is True and receipt.get("status") == "CANDIDATE"
            and receipt.get("manifest_sha256") == tiers_sha and receipt.get("outcomes_read") is False
            and receipt.get("live_actions") is False and receipt.get("host") == host, "check",
            "bundle %s: assembly receipt is not a production (production_pins: true) receipt for this manifest" % name)


def bundle_component(policy, role, host, directory, tiers_sha, receipt_sha, runtime_manifest, guard_manifest):
    name = directory.rsplit("/", 1)[1]
    require(SAFE_NAME.fullmatch(name) is not None and not name.endswith(".partial"), "path", "bad bundle name: " + name)
    raw = si.read_bytes(policy, role, BUNDLE_MANIFEST, expected_sha256=C.need_sha256(tiers_sha, "tiers-pins SHA"),
                        max_size=64 << 20)
    manifest = si.loads_strict(raw, name + "/" + BUNDLE_MANIFEST)
    side = ("%s  %s\n" % (tiers_sha, BUNDLE_MANIFEST)).encode()
    si.read_bytes(policy, role, BUNDLE_SIDE, expected_sha256=C.sha_bytes(side), max_size=4096)
    receipt = si.read_json(policy, role, BUNDLE_RECEIPT, 1 << 20,
                           expected_sha256=C.need_sha256(receipt_sha, "assembly receipt SHA"))
    require(isinstance(manifest, dict), "check", "bundle %s: manifest is not an object" % name)
    refuse_test_only(name, manifest, receipt, tiers_sha, host)
    profile = manifest.get("reference_load_profile")
    require(manifest.get("schema") == BUNDLE_SCHEMA and manifest.get("profile") == "fleet-reference"
            and isinstance(profile, dict) and profile.get("host") == host and isinstance(profile.get("guard"), dict),
            "check", "bundle %s is not a fleet-reference bundle for %s" % (name, host))
    guard = profile["guard"]
    S3.check_target(host, guard.get("job"))
    require(receipt.get("guard_job") == guard["job"], "check", "bundle %s: receipt guard job differs" % name)
    pinned = manifest.get("files")
    require(isinstance(pinned, dict) and all(C.is_sha256(v) for v in pinned.values()), "check",
            "bundle %s: malformed files pins" % name)
    walk = si.walk_tree(policy, role)
    require(walk["e1"] is None and not walk["e4"], "check", "bundle %s holds an E1/E4 entry" % name)
    present = {f["rel"]: f for f in walk["files"]}
    require(set(present) == set(pinned) | set(BUNDLE_UNPINNED) and not set(pinned) & set(BUNDLE_UNPINNED), "check",
            "bundle %s holds unpinned or lacks pinned files: %r" % (name, sorted(set(present) ^ (set(pinned)
                                                                                   | set(BUNDLE_UNPINNED)))[:6]))
    shas = {BUNDLE_MANIFEST: tiers_sha, BUNDLE_SIDE: C.sha_bytes(side), BUNDLE_RECEIPT: receipt_sha}
    for rel, expected in sorted(pinned.items()):
        got = si.sha256_input(policy, role, rel, expected_size=present[rel]["size"])
        require(got["sha256"] == expected, "check", "bundle %s: %s differs from its pin" % (name, rel))
        shas[rel] = expected
    for rel, expected in PRODUCTION_PINS.items():
        require(pinned.get(rel) == expected, "check", "bundle %s: %s is not the production identity %s"
                % (name, rel, expected[:8]))
    want = set(S3.S1B.NAMES[host])
    require(isinstance(guard.get("admissions"), dict) and set(guard["admissions"]) == want, "check",
            "bundle %s: guard admissions must be exactly %s on %s" % (name, sorted(want), host))
    require(runtime_manifest is not None, "policy", "bundles are checked against the staged runtime: give --runtime "
            "or --runtime-manifest-for-checks")
    require(C.canonical_sha(manifest.get("runtime_files")) == runtime_manifest["runtime_files_sha256"]
            and C.canonical_sha(manifest.get("measurement_files")) == runtime_manifest["measurement_files_sha256"],
            "check", "bundle %s was not built from the staged runtime (runtime/measurement canonical SHA)" % name)
    checks = dict(name=name, guard_job=guard["job"], tiers_pins_sha256=tiers_sha, assembly_receipt_sha256=receipt_sha,
                  runtime_consistent=True, production=True)
    if guard_manifest is not None and guard["job"] == guard_manifest["target_job"]:
        pairs = [(guard.get("freeze"), S3.FROZEN_T1_SHA)]
        require(set(guard["admissions"]) == set(guard_manifest["admissions"]), "check",
                "bundle/guard-job admission names differ")
        pairs += [(guard["admissions"][n], guard_manifest["admissions"][n]["sha256"]) for n in guard["admissions"]]
        seeds = {b["path"]: b["sha256"] for b in guard_manifest["bindings"]}
        require(isinstance(guard.get("seed_inputs"), dict) and set(guard["seed_inputs"]) == set(seeds), "check",
                "bundle/guard-job seed inputs differ")
        pairs += [(guard["seed_inputs"][p], s) for p, s in seeds.items()]
        for rel, expected in pairs:
            require(pinned.get(rel) == expected, "check", "bundle %s: %s differs from the guard job's bytes"
                    % (name, rel))
        checks["guard_job_bytes_equal"] = True
    files = [dict(src_role=role, src_rel=rel, dst=rel, size=present[rel]["size"], sha256=shas[rel], mode=0o444,
                  e4=False) for rel in sorted(present)]
    return Component("bundle", host, roots(host)["bundles"], name, files, C.dirs_of(present), checks)


# ---------------------------------------------------------------- remote requests and scripts

def check_policy(host, components, create_base):
    """Remote (description-only) policy for the P/F/POST reader requests."""
    base = END_BASES[host]
    base_parent, base_leaf = base.rsplit("/", 1)
    roles = [si.Role("base-parent", base_parent, "read", 1, exact=(base_leaf,)),
             si.Role("base", base, "read", 1, exact=BASE_SUBDIRS)]
    by_parent = {}
    for c in components:
        by_parent.setdefault(c.parent, []).extend([c.leaf, c.leaf + ".partial"])
    for i, (parent, names) in enumerate(sorted(by_parent.items())):
        grants = ("guard-job",) if parent in GUARD_PARENTS.values() else ()
        roles.append(si.Role("parent-%d" % i, parent, "read", 1, exact=tuple(sorted(set(names))), grants=grants))
    return si.Policy(host, roles, remote=True), {parent: "parent-%d" % i for i, parent in enumerate(sorted(by_parent))}


def p_items(components, roles, create_base):
    if create_base:
        items = [{"role": "base-parent", "kind": "dir"}, {"role": "base-parent", "kind": "absent",
                                                           "rel": END_BASES[components[0].host].rsplit("/", 1)[1]}]
    else:
        items = [{"role": "base", "kind": "dir"}] + [{"role": "base", "kind": "dir", "rel": d} for d in BASE_SUBDIRS]
    for c in components:
        inside_new_base = create_base and c.kind != "guard-job"
        if c.kind == "guard-job":
            items.append({"role": roles[c.parent], "kind": "dir"})
        if not inside_new_base:
            items += [{"role": roles[c.parent], "kind": "absent", "rel": c.leaf},
                      {"role": roles[c.parent], "kind": "absent", "rel": c.leaf + ".partial"}]
    return items


def f_items(components, roles):
    items = []
    for c in components:
        items += [{"role": roles[c.parent], "kind": "dir", "rel": c.leaf + ".partial"},
                  {"role": roles[c.parent], "kind": "absent", "rel": c.leaf}]
    return items


def post_items(components, roles):
    items = []
    for c in components:
        items += [{"role": roles[c.parent], "kind": "dir", "rel": c.leaf},
                  {"role": roles[c.parent], "kind": "absent", "rel": c.leaf + ".partial"}]
    return items


def facts_script():
    t = REMOTE_TOOLS
    lines = ["export LC_ALL=C"]
    for name, cmd in (("hostname", t["hostname"]), ("df", t["df"] + " -P -B1 -- /mpac/sdicks02"), ("who", t["who"])):
        # The assignment's status IS the command's status; it is echoed and checked before the output is used.
        lines += ["out=$(%s)" % cmd, 'echo "@@RC|%s|$?"' % name, "printf '@@OUT|%s\\n%%s\\n' \"$out\"" % name]
    lines.append("echo @@DONE")
    return "\n".join(lines)


def reader_words(host, request):
    argv = si.remote_ssh_argv(host, request, SSH_BINARY)
    words = argv[argv.index("--") + 2:]
    require(all(re.fullmatch(r"[A-Za-z0-9/-]+", w) for w in words), "policy", "unsafe reader words")
    return " ".join(words)


def f_script(host, components, request):
    t = REMOTE_TOOLS
    q = shlex.quote
    lines = ["export LC_ALL=C", reader_words(host, request), "rc=$?", 'echo "@@RC|check|$rc"', '[ "$rc" = 0 ] || exit 9']
    for i, c in enumerate(components):
        if c.kind != "guard-job":
            lines += ["%s -R a-w -- %s" % (t["chmod"], q(c.partial)), "rc=$?", 'echo "@@RC|chmod|%d|$rc"' % i,
                      '[ "$rc" = 0 ] || exit 10']
        lines += ["%s -n -T -- %s %s" % (t["mv"], q(c.partial), q(c.final)), "rc=$?", 'echo "@@RC|mv|%d|$rc"' % i,
                  '[ "$rc" = 0 ] || exit 11']
    lines.append("echo @@DONE")
    return "\n".join(lines)


def ssh_script_argv(host, script):
    require(host in HOSTS, "policy", "unknown END host " + host)
    return [SSH_BINARY] + list(si.SSH_OPTIONS) + ["--", host, REMOTE_TOOLS["sh"] + " -c " + shlex.quote(script)]


def parse_facts(host, out, need_bytes):
    text = out.decode("utf-8", "replace")
    lines = text.split("\n")
    require(lines[-2:] == ["@@DONE", ""], "remote", "P-facts did not complete")
    rcs, outs, key = {}, {}, None
    for line in lines[:-2]:
        if line.startswith("@@RC|"):
            _, name, rc = line.split("|", 2)
            rcs[name] = rc
            key = None
        elif line.startswith("@@OUT|"):
            key = line.split("|", 1)[1]
            outs[key] = []
        elif key is not None:
            outs[key].append(line)
    require(sorted(rcs) == ["df", "hostname", "who"], "remote", "P-facts statuses missing: %r" % sorted(rcs))
    bad = {k: v for k, v in rcs.items() if v != "0"}
    require(not bad, "subprocess", "P-facts: nonzero status (output not used): %r" % bad)
    require(outs.get("hostname") == [host], "host", "P-facts hostname %r is not %s" % (outs.get("hostname"), host))
    df = outs.get("df", [])
    require(len(df) == 2 and df[0].split()[:4] == ["Filesystem", "1-blocks", "Used", "Available"], "remote",
            "P-facts df output malformed: %r" % df[:3])
    fields = df[1].split()
    require(len(fields) >= 6 and fields[3].isdigit(), "remote", "P-facts df row malformed: %r" % df[1])
    free = int(fields[3])
    require(free >= need_bytes + HEADROOM, "space", "%d bytes free on /mpac < %d + 50 GiB headroom" % (free, need_bytes))
    who = [w for w in outs.get("who", []) if w.strip()]
    return dict(free_bytes=free, need_bytes=need_bytes, who_lines=len(who))


def parse_f(host, request, rc, out, components):
    first, _, rest = out.partition(b"\n")
    lines = rest.decode("utf-8", "replace").split("\n")
    rcs = [line for line in lines if line.startswith("@@RC|")]
    require(rcs[:1] and rcs[0].startswith("@@RC|check|"), "remote", "F: reader status missing (rc %s)" % rc)
    check_rc = rcs[0].split("|")[2]
    require(check_rc.isdigit(), "remote", "F: bad reader status")
    records = si.parse_remote_response(request, int(check_rc), first + b"\n")
    require(rc == 0 and lines[-2:] == ["@@DONE", ""], "remote", "F stopped (rc %s): %r" % (rc, rcs))
    want = []
    for i, c in enumerate(components):
        if c.kind != "guard-job":
            want.append("@@RC|chmod|%d|0" % i)
        want.append("@@RC|mv|%d|0" % i)
    require(rcs[1:] == want, "remote", "F step statuses differ: %r" % rcs[1:])
    dirs = [r for r in records if r["kind"] == "dir"]
    return {c.partial: dict(dev=d["dev"], ino=d["ino"]) for c, d in zip(components, dirs)}


# ---------------------------------------------------------------- run

def local_policy(a):
    roles = [C.code_role()]
    s9out = a.runtime or a.runtime_manifest_for_checks
    if s9out:
        roles += S9.verify_roles("s9", C.input_dir(s9out, "--runtime"))
    for i, (directory, _, _) in enumerate(a.bundle or ()):
        roles.append(si.Role("b%02d" % i, C.input_dir(directory, "--bundle"), "read", si.MAX_ROLE_SIZE,
                             patterns=("**",)))
    if a.guard_job:
        roles += S3.verify_roles("s3", C.input_dir(a.guard_job, "--guard-job"), a.guard_job_name or "")
    return si.Policy(C.local_host(), roles)


def plan(a, policy, log):
    host = a.host
    require(host in HOSTS, "policy", "--host must be 127x03 or 127x04")
    require(a.runtime or a.bundle or a.guard_job, "policy", "nothing to stage")
    require(not (a.runtime and a.runtime_manifest_for_checks), "policy", "--runtime and --runtime-manifest-for-checks "
            "are exclusive")
    components, runtime_manifest, guard_manifest = [], None, None
    if a.runtime:
        component, runtime_manifest = runtime_component(policy, host, a.runtime_manifest_sha256, log)
        components.append(component)
    elif a.runtime_manifest_for_checks:
        runtime_manifest = S9.load_manifest(policy, "s9", a.runtime_manifest_sha256)
    guard = None
    if a.guard_job:
        require(bool(a.guard_job_name) and C.is_sha256(a.guard_manifest_sha256), "policy",
                "--guard-job needs --guard-job-name and --guard-manifest-sha256")
        guard, guard_manifest = guard_component(policy, host, a.guard_job_name, a.guard_manifest_sha256, log)
    for i, (directory, tiers_sha, receipt_sha) in enumerate(a.bundle or ()):
        components.append(bundle_component(policy, "b%02d" % i, host, directory, tiers_sha, receipt_sha,
                                           runtime_manifest, guard_manifest))
    if guard is not None:
        components.append(guard)
    finals = [c.final for c in components]
    require(len(set(finals)) == len(finals), "policy", "two components share a target")
    return components


def run(a, log=print):
    started = C.utc()
    record = None if a.dry_run else C.Record(a.record, "S10", RECORD_NAMES).open()   # first: receipts need a home
    logins, components, received = [], [], []
    try:
        policy = local_policy(a)
        if not a.dry_run:
            require(bool(a.outside_end_window), "policy",
                    "live run requires --outside-end-window '<coordinator A2 GO / window reference>'")
        components = plan(a, policy, log)
        need = sum(c.bytes for c in components)
        checkp, roles = check_policy(a.host, components, a.create_base)
        p_request = si.build_remote_request(checkp, p_items(components, roles, a.create_base))
        if a.dry_run:
            log(json.dumps(dict(mode="dry-run", host=a.host, bytes=need, create_base=a.create_base,
                                components=[c.summary() for c in components],
                                reader_program_sha256=si.remote_program_sha256(),
                                receive_program_sha256=si.receive_program_sha256()), indent=1, sort_keys=True))
            log("# P-check request " + p_request.decode())
            log(shlex.join(si.remote_ssh_argv(a.host, p_request, SSH_BINARY)))
            log("# P-facts\n" + shlex.join(ssh_script_argv(a.host, facts_script())))
            for c in components:
                log("# receive %s -> %s (%d files, %d dirs, %d bytes)" % (c.kind, c.partial, len(c.files),
                                                                          len(c.dirs), c.bytes))
            return None

        def note(label, **extra):
            logins.append(dict(label=label, host=a.host, utc=C.utc(), **extra))
            log("[%s] ssh %s %s" % (C.utc(), label, a.host))

        note("P-check", request_sha256=C.sha_bytes(p_request))
        si.remote_check(checkp, p_items(components, roles, a.create_base), ssh_binary=SSH_BINARY, timeout=300)
        note("P-facts")
        facts = si.run_checked(ssh_script_argv(a.host, facts_script()), 300, 1 << 20, env={"LC_ALL": "C"})
        inspect = parse_facts(a.host, facts.stdout, need)
        if a.create_base:
            note("base")
            base_policy = si.Policy(a.host, [si.Role("dest", END_BASES[a.host], "write", 1, patterns=("**",))],
                                    remote=True)
            received.append(END_BASES[a.host])
            si.remote_receive(base_policy, "dest", policy, [], list(BASE_SUBDIRS), 0, ssh_binary=SSH_BINARY,
                              timeout=300)
        receipts = {}
        for c in components:
            note("receive-" + c.kind, partial=c.partial, files=len(c.files), bytes=c.bytes)
            received.append(c.partial)
            receipt = si.remote_receive(c.dest_policy(), "dest", policy, c.files, c.dirs, c.bytes,
                                        ssh_binary=SSH_BINARY, timeout=6 * 3600)
            receipts[c.partial] = dict(files=len(receipt["files"]), root=receipt["root"],
                                       receipt_sha256=C.canonical_sha(receipt))
        f_request = si.build_remote_request(checkp, f_items(components, roles))
        note("F", request_sha256=C.sha_bytes(f_request))
        result = si.run_checked(ssh_script_argv(a.host, f_script(a.host, components, f_request)), 1800, 1 << 20,
                                stdin_bytes=si.remote_program_source().encode(), env={"LC_ALL": "C"},
                                ok_rcs=(0, 3, 9, 10, 11))
        identities = parse_f(a.host, f_request, result.rc, result.stdout, components)
        note("POST")
        post = si.remote_check(checkp, post_items(components, roles), ssh_binary=SSH_BINARY, timeout=300)
        final = {}
        for c, d in zip(components, [r for r in post if r["kind"] == "dir"]):
            require((d["dev"], d["ino"]) == (identities[c.partial]["dev"], identities[c.partial]["ino"]), "changed",
                    "POST: %s is not the directory F moved" % c.final)
            writable = d["mode"] & 0o222
            require((writable == 0) if c.kind != "guard-job" else (d["mode"] & 0o200 != 0), "check",
                    "POST: %s has mode %o" % (c.final, d["mode"] & 0o7777))
            final[c.final] = dict(mode=oct(d["mode"] & 0o7777), dev=d["dev"], ino=d["ino"])
        manifest = dict(schema=SCHEMA, status="staged", host=a.host, started_utc=started, finished_utc=C.utc(),
                        outside_end_window=a.outside_end_window, ssh_logins=len(logins), logins=logins,
                        inspect=inspect, create_base=a.create_base, components=[c.summary() for c in components],
                        receipts=receipts, final=final, roots=roots(a.host),
                        reader_program_sha256=si.remote_program_sha256(),
                        receive_program_sha256=si.receive_program_sha256(), safe_input_sha256=C.SAFE_INPUT_SHA256,
                        script_sha256=C.code_sha(policy, "s10_stage_host.py"),
                        s3_sha256=C.code_sha(policy, "s3_guard_job.py"), s9_sha256=C.code_sha(policy, "s9_end_runtime.py"),
                        common_sha256=C.code_sha(policy, "end_prep_common.py"),
                        inventories={c.final: [[f["dst"], f["size"], f["sha256"], f["mode"]] for f in c.files]
                                     for c in components})
        sha = record.write("s10-staging-manifest.json", manifest)
        log("S10 OK: %s/s10-staging-manifest.json sha256 %s" % (a.record, sha))
        return manifest
    except BaseException as error:
        if record is not None:
            record.refusal(error, {"logins": logins, "started_utc": started,
                                   "host_paths_created_or_attempted_needing_authorized_cleanup": received})
        raise
    finally:
        if record is not None:
            record.close()


class BundleAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        items = list(getattr(namespace, self.dest) or [])
        items.append(tuple(values))
        setattr(namespace, self.dest, items)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0], allow_abbrev=False)
    ap.add_argument("--print-roots", action="store_true", help="print the RC-6 roots declaration draft (JSON) and exit")
    ap.add_argument("--host", choices=HOSTS)
    ap.add_argument("--runtime", help="S9 output directory (ships the runtime)")
    ap.add_argument("--runtime-manifest-for-checks", help="S9 output used only to check bundles (no ship)")
    ap.add_argument("--runtime-manifest-sha256")
    ap.add_argument("--bundle", nargs=3, action=BundleAction, metavar=("DIR", "TIERS_PINS_SHA256", "RECEIPT_SHA256"))
    ap.add_argument("--guard-job", help="S3 output directory")
    ap.add_argument("--guard-job-name")
    ap.add_argument("--guard-manifest-sha256")
    ap.add_argument("--create-base", action="store_true", help="first staging on this host: create <base> + subdirs")
    ap.add_argument("--record", help="new local directory for the staging manifest (live run)")
    ap.add_argument("--outside-end-window", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.print_roots:
        print(json.dumps(roots_declaration(), indent=1, sort_keys=True))
        return 0
    if a.host is None:
        ap.error("--host is required")
    if not a.dry_run and not a.record:
        ap.error("--record is required unless --dry-run")
    try:
        run(a)
    except si.Refusal as error:
        print("S10 REFUSED: " + str(error), file=sys.stderr)
        return 2
    except Exception as error:                                        # fail closed on anything unexpected
        print("S10 FAILED: %s: %s" % (type(error).__name__, error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
