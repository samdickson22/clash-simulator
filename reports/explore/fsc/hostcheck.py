"""FSC host-side checks (stdlib, python3 -I; exploration, NEVER ADOPTABLE). Read-only except for the printed JSON.
Exit 0 = the stated expectation holds; any other status (10 = expectation not met, 1 = error) is a failure.

  census empty|live PGID [PID ...]   processes in that process group or with those PIDs; "live" needs >= 2 in the group
  exitstatus PHASE                   supervisor-exit.json is valid and its reason is a planned end
                                     (worklist done, owned STOP, hard stop time) with an empty group and empty census
  prestop PHASE                      before a STOP test: a block has started and the run's group is live (>= 2
                                     processes, supervisor alive) under the memory guards; prints the JSON stoptest consumes
  guard PHASE                        the live run's group and supervisor carry oom_score_adj 1000 and RLIMIT_AS 8 GiB
  snapshot OUT                       baseline: every sdicks02 process (ps, exact fields) except this session's own
  proof J                            STOP proof: every recorded PID gone (ps -p, exact PIDs), no process in a recorded
                                     PGID/SID, and no sdicks02 process outside the launch baseline (no orphans), the
                                     last in two samples 15 s apart
  stoptest PHASE TOUCH_EPOCH PRE_STOP_JSON
                                     live STOP test: work was live before STOP (started block, >= 2 group processes),
                                     exit reason owned_STOP within 120 s of the STOP touch, every pre-STOP PID gone,
                                     and at least one started block left without proof (an interrupted live block)
  smoke PHASE CONFIG HOST            8-seed smoke gate (no losses printed)
  resident HOST                      ruling FSC-1: 127x03's pinned idle resident (v4 validation cache service, PGID
                                     2180934 = PIDs 2180934/2180946/2180947, start_ticks of 2180947 = 139691386).
                                     Reads /proc/<pid>/stat only; prints their summed utime+stime if every identity
                                     holds on 127x03, else "none"
  resident-idle T1 T2                exit 0 only if both samples are tick counts and T2 - T1 is in [0, 15] (1 % of one
                                     core over the 15 s window at 100 Hz)
"""
import json, os, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
STOP_BOUND_S = 120
RESIDENT = dict(host='127x03', pgid=2180934, pids=(2180934, 2180946, 2180947), anchor=2180947, start_ticks=139691386)
RESIDENT_IDLE_TICKS = 15


def resident_ticks(host, proc='/proc'):
    """Summed utime+stime of the exempt resident's PIDs, or None unless every identity holds (FSC-1)."""
    if host != RESIDENT['host']:
        return None
    total = 0
    for pid in RESIDENT['pids']:
        try:
            f = Path(proc, str(pid), 'stat').read_text().rsplit(')', 1)[1].split()
        except (OSError, IndexError):
            return None
        # After the ')' of comm: f[0] = field 3 (state), so field N is f[N-3].
        pgid, utime, stime, start = int(f[2]), int(f[11]), int(f[12]), int(f[19])
        if pgid != RESIDENT['pgid'] or (pid == RESIDENT['anchor'] and start != RESIDENT['start_ticks']):
            return None
        total += utime + stime
    return total


def resident_idle(t1, t2):
    return t1.isdigit() and t2.isdigit() and 0 <= int(t2) - int(t1) <= RESIDENT_IDLE_TICKS
AS_LIMIT = 8*2**30
PS_ENV = dict(os.environ, TZ='UTC', LC_ALL='C')


def ps_table(all_users=False):
    """[{pid, ppid, pgid, sid, lstart, args}] from one ps call (exact fields; no pattern matching)."""
    sel = ['-e'] if all_users else ['-u', str(os.getuid())]
    r = subprocess.run(['ps', *sel, '-o', 'pid=,ppid=,pgid=,sid=,lstart=,args='], capture_output=True, text=True, env=PS_ENV, timeout=60)
    assert r.returncode == 0 and r.stdout.strip(), ('ps failed', r.returncode, r.stderr[-300:])
    rows = []
    for line in r.stdout.splitlines():
        f = line.split(None, 9)
        assert len(f) >= 9, line
        rows.append(dict(pid=int(f[0]), ppid=int(f[1]), pgid=int(f[2]), sid=int(f[3]), lstart=' '.join(f[4:9]),
                         args=f[9] if len(f) > 9 else ''))
    return rows


def own_session(rows):
    """This session: the ancestors of this process owned by us (sshd child, shells) and everything in our SID."""
    by = {r['pid']: r for r in rows}; me = by[os.getpid()]
    own, cur = {r['pid'] for r in rows if r['sid'] == me['sid']}, me
    while cur is not None:
        own.add(cur['pid']); cur = by.get(cur['ppid'])
    return own


def ps_alive(pids):
    if not pids:
        return []
    r = subprocess.run(['ps', '-p', ','.join(map(str, sorted(pids))), '-o', 'pid='], capture_output=True, text=True, env=PS_ENV, timeout=60)
    assert r.returncode in (0, 1) and not r.stderr.strip(), ('ps -p failed', r.returncode, r.stderr[-300:])
    return sorted(int(x) for x in r.stdout.split())


def guards(pids):
    checked, bad = 0, []
    for pid in pids:
        try:
            adj = Path(f'/proc/{pid}/oom_score_adj').read_text().strip()
            line = next(l for l in Path(f'/proc/{pid}/limits').read_text().splitlines() if l.startswith('Max address space'))
        except (FileNotFoundError, ProcessLookupError):
            continue
        soft, hard = line.split()[3:5]; checked += 1
        if adj != '1000' or soft != str(AS_LIMIT) or hard != str(AS_LIMIT):
            bad.append(dict(pid=pid, oom_score_adj=adj, as_soft=soft, as_hard=hard))
    return checked, bad
PLANNED = {None, 'owned_STOP', 'hard_stop_time'}


def census(pgid, pids=()):
    in_group, listed = [], []
    for d in Path('/proc').iterdir():
        if d.name.isdigit():
            try:
                pg = int((d/'stat').read_text().rsplit(')', 1)[1].split()[2])
            except (FileNotFoundError, ProcessLookupError):
                continue  # exited while scanning
            if pg == pgid: in_group.append(int(d.name))
            if int(d.name) in pids: listed.append(int(d.name))
    return sorted(in_group), sorted(listed)


def load(path):
    return json.loads(Path(path).read_text())


def exit_ok(phase):
    ex, launch = load(phase/'supervisor-exit.json'), load(phase/'launch.json')
    group, listed = census(launch['child_pgid'], {launch['supervisor_pid']})
    ok = (set(ex) >= {'reason', 'returncode', 'remaining_group_pids'} and ex['reason'] in PLANNED
          and ex['remaining_group_pids'] == [] and not group and not listed
          and (ex['reason'] is not None or ex['returncode'] == 0))
    return ok, dict(phase=str(phase), reason=ex['reason'], returncode=ex['returncode'], remaining=ex['remaining_group_pids'],
                    census_group=group, census_supervisor=listed, complete_blocks=ex.get('complete_blocks'))


def done(ok, info):
    info['pass'] = bool(ok); print(json.dumps(info)); sys.exit(0 if ok else 10)


def main():
    cmd = sys.argv[1]
    if cmd == 'resident':
        t = resident_ticks(sys.argv[2]); print('none' if t is None else t); sys.exit(0)
    if cmd == 'resident-idle':
        sys.exit(0 if resident_idle(sys.argv[2], sys.argv[3]) else 10)
    if cmd == 'census':
        want, pgid = sys.argv[2], int(sys.argv[3]); pids = {int(x) for x in sys.argv[4:]}
        assert want in ('empty', 'live') and pgid > 1
        group, listed = census(pgid, pids)
        ok = (not group and not listed) if want == 'empty' else (len(group) >= 2 and listed == sorted(pids))
        done(ok, dict(expect=want, pgid=pgid, pids=sorted(pids), group=group, listed=listed))
    phase = Path(sys.argv[2])
    if cmd == 'exitstatus':
        done(*exit_ok(phase))
    if cmd == 'snapshot':
        out = Path(sys.argv[2]); assert not os.path.lexists(out)
        rows = ps_table(); own = own_session(rows)
        base = [r for r in rows if r['pid'] not in own]
        out.write_text(json.dumps(dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), processes=base), indent=1)+'\n')
        done(True, dict(snapshot=str(out), processes=len(base), own_session_excluded=len(own)))
    if cmd == 'proof':
        J = Path(sys.argv[2]); base = load(J/'logs/baseline-ps.json')['processes']
        pids, pgids = set(), set()
        for inst in sorted((J/'inst').iterdir()):
            rec = load(inst/'receipt.json'); pids.add(rec['pid']); pgids.add(rec['pgid'])
            ph = inst/inst.name
            if (ph/'launch.json').exists():
                la = load(ph/'launch.json')
                pids |= {la['supervisor_pid'], la['child_pid']}; pgids |= {la['supervisor_pgid'], la['child_pgid']}
            for m in sorted((ph/'blocks').glob('*.started')) if (ph/'blocks').is_dir() else []:
                pids.add(load(m)['pid'])
            for m in sorted((ph/'blocks').glob('*.json')) if (ph/'blocks').is_dir() else []:
                b = load(m); pids.add(b['worker_pid']); pgids.add(b['worker_pgid'])
        alive = ps_alive(pids)
        keys = {(r['pid'], r['lstart']) for r in base}
        samples = []
        for n in range(2):
            if n: time.sleep(15)
            rows = ps_table(); own = own_session(rows); everyone = ps_table(all_users=True)
            in_groups = sorted({r['pid'] for r in everyone if r['pgid'] in pgids or r['sid'] in pgids})
            extra = {(r['pid'], r['lstart']): r for r in rows if r['pid'] not in own and (r['pid'], r['lstart']) not in keys}
            samples.append((in_groups, extra))
        persistent = [samples[1][1][k] for k in sorted(set(samples[0][1]) & set(samples[1][1]))]
        orphans = [r for r in persistent if r['ppid'] == 1]
        ok = not alive and not samples[0][0] and not samples[1][0] and not persistent
        done(ok, dict(recorded_pids=len(pids), recorded_pgids=sorted(pgids), recorded_alive=alive,
                      in_recorded_groups=sorted(set(samples[0][0]) | set(samples[1][0])),
                      extra_sdicks02_processes=persistent, orphans_under_init=orphans, baseline_processes=len(base)))
    if cmd == 'guard':
        launch = load(phase/'launch.json')
        group, listed = census(launch['child_pgid'], {launch['supervisor_pid']})
        checked, bad = guards(group+listed)
        done(checked >= 2 and not bad, dict(phase=str(phase), checked=checked, bad=bad))
    if cmd == 'prestop':
        launch = load(phase/'launch.json')
        group, listed = census(launch['child_pgid'], {launch['supervisor_pid']})
        started = sorted(p.name for p in (phase/'blocks').glob('*.started')) if (phase/'blocks').is_dir() else []
        checked, bad = guards(group+listed)
        done(len(group) >= 2 and listed == [launch['supervisor_pid']] and bool(started) and checked >= 2 and not bad,
             dict(phase=str(phase), group=group, supervisor=listed, started=started, guards_checked=checked, guards_bad=bad))
    if cmd == 'stoptest':
        touch, pre = float(sys.argv[3]), load(sys.argv[4])
        ok, info = exit_ok(phase)
        exit_s = os.stat(phase/'supervisor-exit.json').st_mtime - touch
        gone = [p for p in pre['group'] if os.path.exists(f'/proc/{p}')]
        started = {p.name[:-8] for p in (phase/'blocks').glob('*.started')}
        proved = {p.name[:-5] for p in (phase/'blocks').glob('*.json')}
        interrupted = sorted(started - proved)
        ok = (ok and info['reason'] == 'owned_STOP' and len(pre['group']) >= 2 and pre['started']
              and 0 < exit_s <= STOP_BOUND_S and not gone and interrupted)
        info.update(pre_stop_group=pre['group'], pre_stop_started=pre['started'], stop_touch_epoch=touch,
                    stop_to_exit_s=round(exit_s, 1), bound_s=STOP_BOUND_S, still_alive=gone, interrupted_blocks=interrupted)
        done(ok, info)
    assert cmd == 'smoke'
    import reduce as R
    cfg = load(sys.argv[3]); host = sys.argv[4]
    sched, launch = load(phase/'schedule.json'), load(phase/'launch.json')
    assert sched['native_sha256'] == R.NATIVE and launch['host'] == host and sched['range'] == 'smoke'
    rows, excluded, hosts, nblocks = R.X.load_x4s2([phase], cfg, 'smoke', {'X'})
    want = {}
    for c in sched['cases']: want.setdefault(c[1], []).append(c[3])
    R.check_more(rows, cfg, want)
    ok_exit, info = exit_ok(phase)
    ok = (ok_exit and info['reason'] is None and not excluded and len(rows) == len(want) == 8 and set(hosts) == {host})
    arms = {}
    for arm in sorted({a for v in want.values() for a in v}):
        s = R.summary(rows, cfg, arm)
        arms[arm] = {k: s[k] for k in ('games', 'decisions', 'cutoff_pct', 'student_default_pct', 'overrun_pct', 'fallback_pct',
                                       'poll_ms', 'scale_sleep_ms', 'wall_ms', 'game_cpu_hours')}
    ex = load(phase/'supervisor-exit.json'); games = sum(len(v) for v in rows.values())
    info.update(host=host, blocks=len(rows), games=games, workers=launch['workers'], wall_s=ex['wall_seconds'],
                games_per_hour_at_this_width=3600*games/ex['wall_seconds'], arms=arms, excluded=excluded)
    done(ok, info)


if __name__ == '__main__':
    main()
