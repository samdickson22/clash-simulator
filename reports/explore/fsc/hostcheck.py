"""FSC host-side checks (stdlib, python3 -I; exploration, NEVER ADOPTABLE). Read-only except for the printed JSON.

  census PGID [PID ...]      live processes in that process group or with those PIDs (exit 1 if any)
  smoke PHASE CONFIG HOST    8-seed smoke gate: all blocks proven, X4S2 game checks, metadata, clean exit (no losses printed)
  stoptest PHASE             live STOP test: reason owned_STOP, empty group, census empty, STOP-to-exit seconds
"""
import datetime, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def census(pgid, pids=()):
    live = []
    for d in Path('/proc').iterdir():
        if d.name.isdigit():
            try:
                if int(d.name) in pids or int((d/'stat').read_text().rsplit(')', 1)[1].split()[2]) == pgid:
                    live.append(int(d.name))
            except (FileNotFoundError, ProcessLookupError, IndexError, ValueError):
                pass
    return sorted(live)


def utc(s): return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ')


def main():
    cmd = sys.argv[1]
    if cmd == 'census':
        live = census(int(sys.argv[2]), {int(x) for x in sys.argv[3:]})
        print(json.dumps(dict(pgid=int(sys.argv[2]), pids=sys.argv[3:], live=live))); sys.exit(1 if live else 0)
    phase = Path(sys.argv[2])
    ex = json.loads((phase/'supervisor-exit.json').read_text()); launch = json.loads((phase/'launch.json').read_text())
    live = census(launch['child_pgid'], {launch['supervisor_pid']})
    if cmd == 'stoptest':
        stop = json.loads((phase/'stop-reason.json').read_text())
        ok = ex['reason'] == 'owned_STOP' and ex['remaining_group_pids'] == [] and not live
        print(json.dumps(dict(stoptest_pass=ok, reason=ex['reason'], remaining=ex['remaining_group_pids'], live=live,
                              stop_seen_utc=stop['utc'], exit_utc=ex['utc'],
                              stop_to_exit_s=(utc(ex['utc'])-utc(stop['utc'])).total_seconds())))
        sys.exit(0 if ok else 1)
    assert cmd == 'smoke'
    import reduce as R
    cfg = json.loads(Path(sys.argv[3]).read_text()); host = sys.argv[4]
    sched = json.loads((phase/'schedule.json').read_text())
    assert sched['native_sha256'] == R.NATIVE and launch['host'] == host and sched['range'] == 'smoke'
    rows, excluded, hosts, nblocks = R.X.load_x4s2([phase], cfg, 'smoke', {'X'})
    want = {c[1]: [] for c in sched['cases']}
    for c in sched['cases']: want[c[1]].append(c[3])
    R.check_more(rows, cfg, want)
    ok = (ex['reason'] is None and ex['returncode'] == 0 and ex['remaining_group_pids'] == [] and not live
          and not excluded and len(rows) == len(want) == 8 and set(hosts) == {host})
    arms = {}
    for arm in sorted({a for v in want.values() for a in v}):
        s = R.summary(rows, cfg, arm)
        arms[arm] = {k: s[k] for k in ('games', 'decisions', 'cutoff_pct', 'student_default_pct', 'overrun_pct', 'fallback_pct',
                                       'poll_ms', 'scale_sleep_ms', 'wall_ms', 'game_cpu_hours')}
    games = sum(len(v) for v in rows.values())
    print(json.dumps(dict(smoke_pass=ok, host=host, blocks=len(rows), games=games, workers=launch['workers'],
                          wall_s=ex['wall_seconds'], games_per_hour_at_this_width=3600*games/ex['wall_seconds'],
                          arms=arms, excluded=excluded, live=live)))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
