"""K4S END launch gate, HOST side (S7 candidate r4). Python 3.8 stdlib + the shipped, SHA-pinned safe_input layer.

k4s_end_launch_gate.py (on 05) sends ONE program over ONE ``ssh -T -o ControlMaster=no -o ControlPath=none ...
HOST /usr/bin/python3 -I -B -`` session: a prelude that base64-decodes safe_input.py and k4s_end_host_tool.py,
checks each SHA-256 on the host BEFORE exec (and the safe_input constants fingerprint), then ``CONFIG``, then this
body. In that one session (RC-7) it runs, every subprocess through ``si.run_checked`` (absolute argv[0], explicit
env, bounded output, rc checked before stdout is used), every file access through safe_input roles:

  1  hostname          si.hostname_checked (rc 0 and one valid line; valid stdout + nonzero rc = failure)
  2  quiet-read v3 #1, sleep, quiet-read v3 #2 (verbatim bash -c <pinned bytes>)
  3  unfiltered ``systemctl list-timers --all`` (TZ=UTC): >= clearance for every timer unless allowlisted (RC-8)
  4  motd stamps (gated fstatat, no read) vs apt lists (C2 extension)
  5  who (rc-checked)
  6  si.ps_checked table (rc 0, every line parsed, own process present with its real parent): other sshd sessions
  7  staged tool SHAs through the descriptor gate
  8  host base: canonical, no symlinked base or ancestor (si.check_dir); job parent canonical; job absent
  9  frozen-reader ruling: bundle tiers-pins.json read with its declared SHA; its guard job equals the declared one;
     END: its guard-job-free digest equals the qualifying preflight's (r3 F5b); the guard job is fresh; its repo/
     (role "guard-repo": the S3 shallow Q3 repo) and the --repository clone (role "repository": full) pass
     k4s_end_host_tool.verify_clone; Q3 seed commits; the frozen-reader env check (r3 F3)
 9b  r4 (audit L1): the declared runtime is a canonical directory and its end_reference.py has the frozen pin; the
     argv's native/corpus exist as regular single-link files (opened, never read); when the argv carries
     --end-job-sha256, `git show HEAD:<END-JOB>` of the --repository clone has exactly that SHA-256 and binds this
     argv's evidence and the K4S manifest
 10  END: registry names-only (k4s_end_host_tool.registry_listing); second attempt only with a pinned ruling
 11  C5 pre-exec gate from the rc-checked ps table (this process and its parent ni 0 / TS; argv byte-equal)
 12  job created exclusively (si.Writer.mkdir_excl), the pinned argv run once through /usr/bin/env (no shell, the
     exact argv; frozen detach.sh returns after its PID receipt), postexec priority read-back (no signal, C6)

It prints exactly one ``__K4S_GATE_RESULT__ <json>`` line and exits; the session closes with it.
Exit: 0 launched, 3 refused before launch (nothing created), 4 job created but the launch command failed.
"""
import calendar
import json
import os
import re
import time

MARK = "__K4S_GATE_RESULT__ "
UNITS = ("apt-daily.service", "apt-daily-upgrade.service")
QUIET_STATES = ("inactive", "failed")
DAY = 86400
TIMER_NEXT = re.compile(r"^\s*(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) )?(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) UTC\s")
CURRENT = {}                       # the result so far; reported even if an unexpected exception escapes main()


def iso(t=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if t is None else t))


def run(cfg, argv, timeout=60, limit=4 << 20, env=None):
    """si.run_checked with the host PATH; returns {rc, stdout, stderr} or {refused: reason} (rc != 0 included)."""
    try:
        r = si.run_checked(argv, timeout, limit, env=env or {"PATH": cfg["path"], "LC_ALL": "C"})
    except si.Refusal as error:
        return dict(rc=None, refused=str(error), stdout="", stderr="")
    return dict(rc=r.rc, stdout=r.stdout.decode("utf-8", "replace"), stderr=r.stderr.decode("utf-8", "replace")[-2000:])


def argv_sha256(argv):
    import hashlib
    return hashlib.sha256(b"".join(x.encode() + b"\0" for x in argv)).hexdigest()


def parse_quiet(out, rc, helper_pid):
    """Quiet rules: rc 0, both apt units not active, maint 0, who 0; helper change is noted, never fatal."""
    failures, values = [], {}
    for unit in UNITS:
        m = re.search(r"^" + re.escape(unit) + r"=(.*)$", out, re.M)
        values[unit] = m.group(1) if m else None
        if values[unit] not in QUIET_STATES:
            failures.append("quiet: %s is %r" % (unit, values[unit]))
    for key in ("maint", "who"):
        m = re.search(r"^" + key + r"=([0-9]+)$", out, re.M)
        values[key] = int(m.group(1)) if m else None
        if values[key] != 0:
            failures.append("quiet: %s=%r" % (key, values[key]))
    m = re.search(r"^helper=(.*?)\nmaint_lines=<<", out, re.M | re.S)
    helper = m.group(1) if m else None
    pids = [int(line.split()[0]) for line in (helper or "").splitlines() if line.strip()]
    if rc != 0:
        failures.append("quiet: rc=%r" % rc)
    if m is None:
        failures.append("quiet: helper line missing")
    return dict(values=values, helper_pids=pids, helper_changed=pids != [helper_pid], failures=failures)


def quiet(cfg):
    started = time.time()
    r = run(cfg, [cfg["bin"]["bash"], "-c", cfg["quiet_cmd"]], timeout=120)
    parsed = parse_quiet(r["stdout"], r["rc"], cfg["helper_pid"])
    if r.get("refused"):
        parsed["failures"].append("quiet: " + r["refused"][:300])
    return dict(read_utc=iso(started), rc=r["rc"], stdout=r["stdout"], stderr=r["stderr"], **parsed)


def parse_timers(out, now, clearance, allow):
    """Every timer of the unfiltered list needs >= clearance seconds to its next elapse unless allowlisted."""
    timers, failures = [], []
    for line in out.splitlines():
        units = [t for t in line.split() if t.endswith(".timer")]
        if not units:
            continue
        unit = units[0]
        m = TIMER_NEXT.match(line)
        if m:
            next_epoch = calendar.timegm(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"))
        elif line.strip().startswith("n/a"):
            next_epoch = None
        else:
            failures.append("timers: unparseable line for " + unit)
            continue
        left = None if next_epoch is None else next_epoch - now
        ok = left is None or left >= clearance
        row = dict(unit=unit, next_utc=None if next_epoch is None else iso(next_epoch), clearance_seconds=left,
                   clear=ok, allowlisted=allow.get(unit))
        if not ok and unit not in allow:
            failures.append("timers: %s fires in %ds (< %ds)" % (unit, left, clearance))
        timers.append(row)
    if not timers:
        failures.append("timers: no timer parsed")
    return timers, failures


def timers_check(cfg, now):
    r = run(cfg, [cfg["bin"]["systemctl"], "list-timers", "--all", "--no-pager"],
            env={"PATH": cfg["path"], "TZ": "UTC", "LC_ALL": "C"})
    timers, failures = parse_timers(r["stdout"], now, cfg["clearance_seconds"], cfg["allow_timers"])
    if r.get("refused"):
        failures.append("timers: " + r["refused"][:300])
    return dict(raw=r["stdout"], stderr=r["stderr"], rc=r["rc"], timers=timers, failures=failures)


def gated_stat(P, role, rel, directory=False):
    """fstatat of a gated name (si names/allowlist, canonical root, O_NOFOLLOW components); a regular file also
    passes the descriptor gate (single link, no symlink); nothing is read."""
    si.gate_names(P, role, rel)
    parts = rel.split("/")
    root = si.open_root(P.role(role).root)
    try:
        parent = si.open_dirs(root, parts[:-1], rel)
    finally:
        os.close(root)
    try:
        if directory:
            fd = si.open_dirs(parent, parts[-1:], rel)
            st = os.fstat(fd)
        else:
            fd, st = si.open_leaf(parent, parts[-1], 1 << 30, None, rel)
        os.close(fd)
    finally:
        os.close(parent)
    return st


def stamps_check(cfg, P, now):
    """release-upgrade-available younger than 24 h minus the window; updates-available newer than apt lists."""
    out, failures = {}, []
    for key, (root, rel) in sorted(cfg["stamps"].items()):
        try:
            st = gated_stat(P, "stamp-" + key, rel, directory=key == "apt_lists")
            out[key] = dict(path=root + "/" + rel, mtime_utc=iso(st.st_mtime), mtime=st.st_mtime)
        except (si.Refusal, OSError) as error:
            out[key] = dict(path=root + "/" + rel, error=str(error))
            failures.append("stamps: missing or not plain " + root + "/" + rel)
    if not failures:
        age = now - out["release_upgrade_available"]["mtime"]
        out["release_upgrade_age_seconds"] = age
        if age > DAY - cfg["window_seconds"]:
            failures.append("stamps: release-upgrade-available %ds old; stale within the window" % age)
        if not out["updates_available"]["mtime"] > out["apt_lists"]["mtime"]:
            failures.append("stamps: updates-available not newer than apt lists")
    return dict(stamps=out, failures=failures)


def ps_table(cfg):
    """si.ps_checked: rc 0, every line parsed, this process present with its real parent; else Refusal."""
    rows = si.ps_checked(binary=cfg["bin"]["ps"], fields=("pid", "ppid", "ni", "cls"))
    return {r["pid"]: r for r in rows}


def ancestry(table, pid):
    chain = []
    while pid in table and pid not in chain:
        chain.append(pid)
        pid = table[pid]["ppid"]
    return chain


def other_ssh_sessions(table, me):
    """sshd session processes (not the listener) outside this session's own ancestry."""
    mine = set(ancestry(table, me))
    return sorted(p for p, r in table.items()
                  if r["args"].startswith("sshd: ") and "[listener]" not in r["args"] and p not in mine)


def descendants(table, root):
    out, frontier = [], [root]
    while frontier:
        parent = frontier.pop()
        for p, r in table.items():
            if r["ppid"] == parent and p not in out:
                out.append(p)
                frontier.append(p)
    return out


def host_policy(cfg):
    R = si.Role
    roles = [R("tools", cfg["tools"], "read", 64 << 20, exact=tuple(os.path.basename(p) for p in cfg["file_pins"])),
             R("base", cfg["base"], "read", 1, exact=(os.path.basename(cfg["attempt_parent"]),)),
             R("parent", cfg["attempt_parent"], "read", 1, exact=(cfg["attempt"],)),
             R("parent-write", cfg["attempt_parent"], "write", 1, exact=(cfg["attempt"],)),
             R("bundle", cfg["bundle"], "read", 64 << 20, exact=("tiers-pins.json",)),
             R("guard-job", cfg["guard_job"], "read", 1, exact=tuple(cfg["guard_side_files"]) +
               ("STOP", "STOP-" + cfg["host"]), grants=("guard-job",))]
    for key, (root, rel) in sorted(cfg["stamps"].items()):
        roles.append(R("stamp-" + key, root, "read", 1 << 30, exact=(rel,)))
    return si.Policy(cfg["host"], roles)


def frozen_reader(cfg, P, res, failures):
    """Frozen-reader ruling (COORDINATOR 21:28Z): the clones frozen code will run git in, before any launch."""
    out = res["frozen_reader"] = {}
    try:
        manifest = si.read_json(P, "bundle", "tiers-pins.json", 64 << 20, expected_sha256=cfg["bundle_pins_sha256"])
        guard = ((manifest.get("reference_load_profile") or {}).get("guard") or {}).get("job")
        if guard != cfg["guard_job"] or "k4s_s4_synthetic" in manifest:
            failures.append("bundle: guard job differs from the declared one, or S4 test-only bundle")
            return
        digest = out["bundle_sans_guard_sha256"] = tool.bundle_sans_guard_sha256(manifest)
        if cfg["kind"] == "end" and digest != cfg.get("bundle_sans_guard_sha256"):
            failures.append("bundle: differs from the qualifying preflight's bundles beyond guard.job (RC-9, F5)")
            return
        for name in tuple(cfg["guard_side_files"]) + ("STOP", "STOP-" + cfg["host"]):
            si.check_absent(P, "guard-job", name)
        out["guard_job_fresh"] = True
        out["repository"] = tool.verify_clone(si, cfg["host"], cfg["repository"], role="repository")
        out["guard_repo"] = tool.verify_clone(si, cfg["host"], cfg["guard_job"] + "/repo", grants=("guard-job",),
                                              role="guard-repo")
        out["seed_commits"] = tool.seed_commits(si, cfg["guard_job"] + "/repo", cfg["seed_commits"], role="guard-repo")
        # the environment the launched wrapper inherits (dict(os.environ) below); frozen-exec re-checks it at exec
        out["global_git_config"] = tool.frozen_env_checked(si, cfg["host"], dict(os.environ))[1]
    except (si.Refusal, tool.HostRefusal, OSError, ValueError, KeyError) as error:
        failures.append("frozen-reader: %s" % error)


def staged_runtime_and_job(cfg, res, failures):
    """r4 (INTEGRATION-AUDIT-r1 L1): what the frozen END would otherwise only find after the launch window opened.
    The runtime root is a canonical directory (no symlinked ancestor) and end_reference.py has its frozen SHA; the
    native and corpus the argv names exist as regular single-link files (descriptor gate, never read); and the END-JOB
    the argv pins (--end-job-sha256) is the blob at HEAD of the verified --repository clone, bound to this argv's
    END evidence and the K4S manifest of record."""
    out = res["staged"] = {}
    R = si.Role
    try:
        P = si.Policy(cfg["host"], [
            R("runtime", cfg["runtime"], "read", 64 << 20, exact=(cfg["end_reference_rel"],)),
            R("repository-end", cfg["repository"], "read", 1 << 16, exact=(cfg["end_job_rel"],),
              grants=tuple(cfg["end_grants"]))] + [
            R("input-%d" % i, os.path.dirname(p), "read", 64 << 30, exact=(os.path.basename(p),))
            for i, p in enumerate(cfg["inputs"])])
        out["runtime"] = si.check_dir(P, "runtime")
        got = out["end_reference_sha256"] = si.sha256_input(P, "runtime", cfg["end_reference_rel"])["sha256"]
        if got != cfg["end_reference_sha256"]:
            failures.append("runtime: %s differs from its frozen pin" % cfg["end_reference_rel"])
        for i, path in enumerate(cfg["inputs"]):
            role = "input-%d" % i
            si.gate_names(P, role, os.path.basename(path))
            root = si.open_root(os.path.dirname(path))
            try:
                fd, _ = si.open_leaf(root, os.path.basename(path), 64 << 30, None, path)
                os.close(fd)
            finally:
                os.close(root)
        out["inputs_present"] = True
        if cfg.get("end_job_sha256"):
            repo = si.GitRepo(work_tree=cfg["repository"])
            head = si.git_run(repo, ["rev-parse", "--verify", "HEAD^{commit}"], timeout=60,
                              stdout_limit=256).stdout.decode().strip()
            data = si.git_show_file(P, "repository-end", repo, head, cfg["end_job_rel"], max_size=1 << 16,
                                    expected_sha256=cfg["end_job_sha256"])
            job = si.loads_strict(data, cfg["end_job_rel"])
            bound = (isinstance(job, dict) and job.get("schema") == cfg["end_job_schema"]
                     and job.get("end_evidence_sha256") == cfg["end_evidence_sha256"]
                     and job.get("k4s_manifest_sha256") == cfg["k4s_manifest_sha256"])
            out["end_job"] = dict(head=head, sha256=cfg["end_job_sha256"], bound=bound)
            if not bound:
                failures.append("END-JOB at HEAD does not bind this argv's END evidence / K4S manifest")
    except (si.Refusal, OSError, ValueError) as error:
        failures.append("staged: %s" % error)


def main(cfg):
    res = CURRENT
    res.update(schema="clasher.k4s.end-launch-gate-host.v2", started_utc=iso(), kind=cfg["kind"],
               host_expected=cfg["host"], launched=False, safe_input_sha256=cfg["safe_input_sha256"],
               host_tool_sha256=cfg["host_tool_sha256"])
    failures = res["failures"] = []
    try:
        res["host"] = si.hostname_checked(binary=cfg["bin"]["hostname"], expected=cfg["host"])
    except si.Refusal as error:
        res["host"] = None
        failures.append("hostname: %s" % error)
        return finish(res, 3)
    P = host_policy(cfg)
    res["quiet_1"] = quiet(cfg)
    time.sleep(cfg["quiet_gap_seconds"])
    res["quiet_2"] = quiet(cfg)
    failures += res["quiet_1"]["failures"] + res["quiet_2"]["failures"]
    now = time.time()
    res["timers"] = timers_check(cfg, now)
    res["stamps"] = stamps_check(cfg, P, now)
    failures += res["timers"]["failures"] + res["stamps"]["failures"]
    who = run(cfg, [cfg["bin"]["who"]])
    res["who"] = dict(rc=who["rc"], refused=who.get("refused"),
                      lines=len([x for x in who["stdout"].splitlines() if x.strip()]))
    if who["rc"] != 0 or res["who"]["lines"]:
        failures.append("who: %d line(s), rc=%r" % (res["who"]["lines"], who["rc"]))
    try:
        table = ps_table(cfg)
        res["ps"] = dict(rc=0, rows=len(table))
    except si.Refusal as error:
        table = {}
        res["ps"] = dict(rc=None, refused=str(error)[-600:])
        failures.append("ps: %s" % str(error)[:300])
    me = os.getpid()
    others = other_ssh_sessions(table, me)
    res["other_ssh_session_pids"] = others
    if others:
        failures.append("other SSH sessions open on the host (ControlMaster/login): %d" % len(others))
    pins = res["file_pins"] = {}
    for path, expected in sorted(cfg["file_pins"].items()):
        try:
            ok = si.sha256_input(P, "tools", os.path.basename(path))["sha256"] == expected
        except si.Refusal as error:
            ok = False
            pins[path + ":refusal"] = str(error)[:300]
        pins[path] = dict(expected=expected, matches=ok)
        if not ok:
            failures.append("pin: " + path)
    try:
        res["base"] = si.check_dir(P, "base")                       # canonical: no symlinked base/ancestor
        si.check_dir(P, "base", os.path.basename(cfg["attempt_parent"]))
        si.check_absent(P, "parent", cfg["attempt"])
        res["job_parent_ready"] = True
    except si.Refusal as error:
        res["job_parent_ready"] = False
        failures.append("job: %s" % error)
    frozen_reader(cfg, P, res, failures)
    staged_runtime_and_job(cfg, res, failures)
    if cfg["kind"] == "end":
        try:
            listing = tool.registry_listing(si, cfg["host"], cfg["repository"])
            names = listing["claims"].get("round-%02d/%s" % (cfg["round"], cfg["host"]), [])
            res["registry"] = dict(listing, claims_this_round=len(names))
            if len(names) >= 2:
                failures.append("registry: two claims already; no further attempt this round")
            elif len(names) == 1 and not cfg.get("second_attempt_ruling"):
                failures.append("registry: second attempt needs a coordinator ruling (04 op1_interference => STOP)")
        except (si.Refusal, tool.HostRefusal, OSError) as error:
            failures.append("registry: %s" % error)
    argv = cfg["launch_argv"]
    self_row, parent_row = table.get(me, {}), table.get(table.get(me, {}).get("ppid"), {})
    gate = res["C5_preexec_gate"] = dict(
        utc=iso(), exact_exec_pid=me, ps_nice=self_row.get("ni"), scheduler=self_row.get("cls"),
        parent_pid=self_row.get("ppid"), parent_ps_nice=parent_row.get("ni"), parent_scheduler=parent_row.get("cls"),
        frozen_launch_argv_nul_sha256=argv_sha256(argv),
        command_byte_equal=argv_sha256(argv) == cfg["argv_sha256"],
        outside_priority_prefix=argv[:6] != ["nice", "-n", "10", "taskset", "-c", cfg["supervisor_cpu"]])
    gate["SCHED_OTHER"] = gate["scheduler"] == "TS" and gate["parent_scheduler"] == "TS"
    gate["preexec_gate_pass"] = (gate["ps_nice"] == "0" and gate["parent_ps_nice"] == "0" and gate["SCHED_OTHER"]
                                 and gate["command_byte_equal"] and not gate["outside_priority_prefix"])
    if not gate["preexec_gate_pass"]:
        failures.append("C5 pre-exec gate failed")
    if failures:
        return finish(res, 3)
    with si.Writer(P, "parent-write") as writer:
        writer.mkdir_excl(cfg["attempt"])
    res["job_created_utc"] = iso()
    launch = run(cfg, [cfg["bin"]["env"], "--"] + argv, timeout=60, env=dict(os.environ))
    res["launch"] = launch
    if launch["rc"] != 0:
        failures.append("launch command failed: %s" % (launch.get("refused") or launch["rc"]))
        return finish(res, 4)
    res["launched"] = True
    try:
        receipt = json.loads(launch["stdout"].strip().splitlines()[-1])
        res["detach_receipt"] = receipt
        res["utc"] = receipt["launched_at_utc"]
    except (ValueError, IndexError, KeyError) as error:
        failures.append("detach receipt unreadable: %s" % error)
        return finish(res, 0)
    post = res["postexec"] = dict(python_visible=False)
    limit = time.time() + cfg["postexec_seconds"]
    wrapper, python = None, []
    while True:
        try:
            table = ps_table(cfg)
        except si.Refusal as error:
            post["ps_refused"] = str(error)[-300:]
            break
        wrapper = table.get(receipt["pid"])
        post["wrapper"] = None if wrapper is None else dict(pid=wrapper["pid"], ni=wrapper["ni"], cls=wrapper["cls"])
        children = [table[p] for p in descendants(table, receipt["pid"]) if p in table]
        python = [c for c in children if cfg["python_marker"] in c["args"]
                  and os.path.basename((c["args"].split() or [""])[0]).startswith("python")]
        post["python"] = [dict(pid=c["pid"], ni=c["ni"], cls=c["cls"]) for c in python]
        post["python_visible"] = bool(python)
        if python or time.time() > limit:
            break
        time.sleep(.5)
    post["postexec_priority_pass"] = bool(
        wrapper is not None and wrapper["ni"] == "10" and wrapper["cls"] == "TS"
        and all(c["ni"] == "10" and c["cls"] == "TS" for c in python))
    post["no_signals_sent"] = True
    return finish(res, 0)


def finish(res, code):
    res["exit_code"] = code
    res["finished_utc"] = iso()
    print(MARK + json.dumps(res, sort_keys=True), flush=True)
    return code


if __name__ == "__main__":
    try:
        code = main(globals()["CONFIG"])
    except BaseException:
        import traceback
        CURRENT.setdefault("failures", []).append("exception in host gate: " + traceback.format_exc()[-600:])
        code = finish(CURRENT, 0 if CURRENT.get("launched") else 4 if CURRENT.get("job_created_utc") else 3)
    raise SystemExit(code)
