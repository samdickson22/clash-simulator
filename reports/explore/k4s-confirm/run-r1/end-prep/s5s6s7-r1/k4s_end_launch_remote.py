"""K4S END launch gate, HOST side (S7 candidate). Python 3.8 stdlib only; never imported by the host's repository.

k4s_end_launch_gate.py (on 05) prepends one line ``CONFIG = json.loads(...)`` and sends this file over ONE
``ssh -o ControlMaster=no -o ControlPath=none -o BatchMode=yes HOST /usr/bin/python3 -I -B -`` session. In that
session it: runs quiet-read v3 #1 verbatim, waits ``quiet_gap_seconds``, runs quiet-read v3 #2 verbatim; reads the
UNFILTERED ``systemctl list-timers --all`` (TZ=UTC) and requires >= clearance for every timer not in the explicit
allowlist (RC-8); reads the two motd stamps against apt lists (C2 extension); ``who``; other sshd sessions on the
host (any open ControlMaster/login from anywhere); the staged detach/wrapper/preflight SHAs; the claim registry
(names only); then the C5 pre-exec gate (this process and its parent nice 0 / SCHED_OTHER, argv byte-equal to the
pinned argv, which starts with the frozen inner ``nice -n 10 taskset -c 61`` and has no outer prefix); then runs
the pinned argv once (frozen detach.sh returns after its PID receipt) and reads back the wrapper/END python
priority for at most ``postexec_seconds`` without sending any signal (C6). It prints exactly one
``__K4S_GATE_RESULT__ <json>`` line and exits; the SSH session closes with it.
Exit: 0 launched, 3 refused before launch (nothing created), 4 job created but the launch command failed.
"""
import calendar
import hashlib
import json
import os
import re
import subprocess
import time

MARK = "__K4S_GATE_RESULT__ "
UNITS = ("apt-daily.service", "apt-daily-upgrade.service")
QUIET_STATES = ("inactive", "failed")
DAY = 86400
TIMER_NEXT = re.compile(r"^\s*(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) )?(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) UTC\s")
CLAIM = re.compile(r"attempt-[0-9]{2}\.json")
CURRENT = {}                       # the result so far; reported even if an unexpected exception escapes main()


def iso(t=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if t is None else t))


def run(argv, env=None, timeout=60):
    p = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=timeout, env=env, universal_newlines=True)
    return dict(rc=p.returncode, stdout=p.stdout, stderr=p.stderr)


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def argv_sha256(argv):
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
    r = run(["bash", "-c", cfg["quiet_cmd"]])
    parsed = parse_quiet(r["stdout"], r["rc"], cfg["helper_pid"])
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
    env = dict(os.environ, TZ="UTC", LC_ALL="C")
    r = run(["systemctl", "list-timers", "--all", "--no-pager"], env=env)
    timers, failures = parse_timers(r["stdout"], now, cfg["clearance_seconds"], cfg["allow_timers"])
    if r["rc"] != 0:
        failures.append("timers: systemctl rc=%d" % r["rc"])
    return dict(raw=r["stdout"], stderr=r["stderr"], rc=r["rc"], timers=timers, failures=failures)


def stamps_check(cfg, now):
    """release-upgrade-available younger than 24 h minus the window; updates-available newer than apt lists."""
    paths, out, failures = cfg["stamps"], {}, []
    for key, path in paths.items():
        try:
            out[key] = dict(path=path, mtime_utc=iso(os.stat(path).st_mtime), mtime=os.stat(path).st_mtime)
        except OSError as error:
            out[key] = dict(path=path, error=str(error))
            failures.append("stamps: missing " + path)
    if not failures:
        age = now - out["release_upgrade_available"]["mtime"]
        out["release_upgrade_age_seconds"] = age
        if age > DAY - cfg["window_seconds"]:
            failures.append("stamps: release-upgrade-available %ds old; stale within the window" % age)
        if not out["updates_available"]["mtime"] > out["apt_lists"]["mtime"]:
            failures.append("stamps: updates-available not newer than apt lists")
    return dict(stamps=out, failures=failures)


def ps_table():
    r = run(["ps", "-eo", "pid=,ppid=,ni=,cls=,args="])
    rows = {}
    for line in r["stdout"].splitlines():
        parts = line.split(None, 4)
        if len(parts) >= 4 and parts[0].isdigit() and parts[1].isdigit():
            rows[int(parts[0])] = dict(pid=int(parts[0]), ppid=int(parts[1]), ni=parts[2], cls=parts[3],
                                       args=parts[4] if len(parts) > 4 else "")
    return rows


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


def main(cfg):
    res = CURRENT
    res.update(schema="clasher.k4s.end-launch-gate-host.v1", started_utc=iso(), kind=cfg["kind"],
               host_expected=cfg["host"], launched=False)
    failures = res["failures"] = []
    res["host"] = run(["hostname"])["stdout"].strip()
    if res["host"] != cfg["host"]:
        failures.append("host is %r" % res["host"])
        return finish(res, 3)
    res["quiet_1"] = quiet(cfg)
    time.sleep(cfg["quiet_gap_seconds"])
    res["quiet_2"] = quiet(cfg)
    failures += res["quiet_1"]["failures"] + res["quiet_2"]["failures"]
    now = time.time()
    res["timers"] = timers_check(cfg, now)
    res["stamps"] = stamps_check(cfg, now)
    failures += res["timers"]["failures"] + res["stamps"]["failures"]
    who = run(["who"])
    res["who"] = dict(rc=who["rc"], lines=len([x for x in who["stdout"].splitlines() if x.strip()]))
    if who["rc"] != 0 or res["who"]["lines"]:
        failures.append("who: %d line(s), rc=%d" % (res["who"]["lines"], who["rc"]))
    table = ps_table()
    me = os.getpid()
    others = other_ssh_sessions(table, me)
    res["other_ssh_session_pids"] = others
    if others:
        failures.append("other SSH sessions open on the host (ControlMaster/login): %d" % len(others))
    pins = res["file_pins"] = {}
    for path, expected in cfg["file_pins"].items():
        ok = os.path.isfile(path) and not os.path.islink(path) and sha_file(path) == expected
        pins[path] = dict(expected=expected, matches=ok)
        if not ok:
            failures.append("pin: " + path)
    parent, job = cfg["attempt_parent"], cfg["job"]
    res["job_parent_ready"] = os.path.isdir(parent) and not os.path.islink(parent) and not os.path.lexists(job)
    if not res["job_parent_ready"]:
        failures.append("job: parent missing or job already exists")
    if cfg.get("registry_dir"):
        names = sorted(os.listdir(cfg["registry_dir"])) if os.path.isdir(cfg["registry_dir"]) else []
        claims = [n for n in names if CLAIM.fullmatch(n)]
        res["registry"] = dict(path=cfg["registry_dir"], names=names, claims=len(claims))
        if len(claims) != len(names):
            failures.append("registry: unexpected names")
        if len(claims) >= 2:
            failures.append("registry: two claims already; no further attempt this round")
        elif len(claims) == 1 and not cfg.get("second_attempt_ruling"):
            failures.append("registry: second attempt needs a coordinator ruling (04 op1_interference => STOP)")
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
    os.mkdir(job)
    res["job_created_utc"] = iso()
    launch = run(argv, timeout=60)
    res["launch"] = dict(rc=launch["rc"], stdout=launch["stdout"], stderr=launch["stderr"])
    if launch["rc"] != 0:
        failures.append("launch command rc=%d" % launch["rc"])
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
    while True:
        table = ps_table()
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
