"""FSC host-side checks (stdlib, python3 -I; exploration, NEVER ADOPTABLE). Read-only except for the printed JSON.
Exit 0 = the stated expectation holds; any other status (10 = expectation not met, 1 = error) is a failure.

  census empty|live PGID [PID ...]   processes in that process group or with those PIDs; "live" needs >= 2 in the group
  exitstatus PHASE                   supervisor-exit.json is valid and its reason is a planned end
                                     (worklist done, owned STOP, hard stop time) with an empty group and empty census
  prestop PHASE                      before a STOP test: a block has started and the run's group is live (>= 2
                                     processes, supervisor alive); prints the JSON that stoptest consumes
  stoptest PHASE TOUCH_EPOCH PRE_STOP_JSON
                                     live STOP test: work was live before STOP (started block, >= 2 group processes),
                                     exit reason owned_STOP within 120 s of the STOP touch, every pre-STOP PID gone,
                                     and at least one started block left without proof (an interrupted live block)
  smoke PHASE CONFIG HOST            8-seed smoke gate (no losses printed)
"""
import json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
STOP_BOUND_S = 120
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
    if cmd == 'census':
        want, pgid = sys.argv[2], int(sys.argv[3]); pids = {int(x) for x in sys.argv[4:]}
        assert want in ('empty', 'live') and pgid > 1
        group, listed = census(pgid, pids)
        ok = (not group and not listed) if want == 'empty' else (len(group) >= 2 and listed == sorted(pids))
        done(ok, dict(expect=want, pgid=pgid, pids=sorted(pids), group=group, listed=listed))
    phase = Path(sys.argv[2])
    if cmd == 'exitstatus':
        done(*exit_ok(phase))
    if cmd == 'prestop':
        launch = load(phase/'launch.json')
        group, listed = census(launch['child_pgid'], {launch['supervisor_pid']})
        started = sorted(p.name for p in (phase/'blocks').glob('*.started')) if (phase/'blocks').is_dir() else []
        done(len(group) >= 2 and listed == [launch['supervisor_pid']] and bool(started),
             dict(phase=str(phase), group=group, supervisor=listed, started=started))
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
