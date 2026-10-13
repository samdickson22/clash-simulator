"""FSC offline tests (05, stdlib): prefix rule, outcome labels, per-game checks on real X4S2 phase-E games."""
import json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reduce as R

CFG = json.loads((HERE/'plan-fsc-04.json').read_text())
SHAS = {R.sha(HERE/'plan-fsc.json'), R.sha(HERE/'plan-fsc-04.json')}


def fake_phase(root, name, host):
    p = root/name; p.mkdir()
    (p/'schedule.json').write_text(json.dumps(dict(native_sha256=R.NATIVE, config_sha256=sorted(SHAS)[0], cases=[])))
    (p/'launch.json').write_text(json.dumps(dict(host=host)))
    return p


def run(phases_rows, host='127x03'):
    """phases_rows: list of (complete indices, interrupted indices) per phase."""
    with tempfile.TemporaryDirectory() as t:
        phases, table = [], {}
        for n, (done, broken) in enumerate(phases_rows):
            p = fake_phase(Path(t), f'rep{n}', host); phases.append(p)
            table[p.name] = ({('X', i): {'K4-200': {}, 'K4S-200': {}} for i in done},
                             [dict(index=i) for i in broken], {host: 1} if done else {}, {p.name: len(done)})
        old_load, old_check = R.X.load_x4s2, R.check_more
        R.X.load_x4s2 = lambda ph, cfg, rng, pops: table[ph[0].name]
        R.check_more = lambda rows, cfg, arms_of: None
        try:
            return R.load_host(host, phases, CFG, SHAS)
        finally:
            R.X.load_x4s2, R.check_more = old_load, old_check


def test_prefix():
    kept, info = run([(list(range(10))+[11, 12], [10])])
    assert sorted(i for _, i in kept) == list(range(10)) and info['first_incomplete_index'] == 10
    assert info['complete_beyond_prefix_dropped'] == 2
    # A block retired by an intermediate (yield) STOP is skipped inside the prefix; the final phase's is not.
    kept, info = run([(list(range(5)), [5]), (list(range(6, 9)), [9])])
    assert sorted(i for _, i in kept) == [0, 1, 2, 3, 4, 6, 7, 8] and info['yield_retired_skipped'] == [5]
    assert info['first_incomplete_index'] == 9
    # 03's worklist is the primary segment only (top-ups dropped for the 05:00Z hard STOP).
    kept, info = run([(list(range(2400)), [])])
    assert len(kept) == 2400 and info['first_incomplete_index'] is None


def test_outcome():
    assert R.outcome(dict(ci95_pp=[-1.0, 0.9])) == 'always-on supported'
    assert R.outcome(dict(ci95_pp=[0.1, 0.9])).startswith('always-on supported (small positive cost')
    assert R.outcome(dict(ci95_pp=[0.2, 2.4])) == 'speed gate needed'
    assert R.outcome(dict(ci95_pp=[-0.5, 2.0])) == 'unresolved'


def test_game_checks():
    # Real X4S2 phase-E games (K4-180 / K4S-180, published results) exercise the per-game metadata checks.
    phase = R.X4S2_E[0]
    i = next(int(p.name[1:5]) for p in sorted((phase/'blocks').glob('X*.json')))
    games = {arm: json.loads((phase/'games'/f'sim-X{i:04d}-d27-{arm}.json').read_text()) for arm in ('K4-180', 'K4S-180')}
    R.check_more({('X', i): games}, CFG, {i: ['K4-180', 'K4S-180']})
    bad = json.loads(json.dumps(games)); bad['K4S-180']['metadata']['checkpoint_sha256'] = R.POLICY
    try:
        R.check_more({('X', i): bad}, CFG, {i: ['K4-180', 'K4S-180']})
    except AssertionError:
        pass
    else:
        raise AssertionError('wrong checkpoint accepted')


def _tmp():
    return Path(os.path.realpath(tempfile.mkdtemp(prefix='fsc-test-')))


def test_nolinks_and_inside():
    import stage
    d = _tmp(); (d/'a').mkdir(); (d/'a/f').write_text('x')
    assert stage.nolinks(d) == 2
    os.symlink('/tmp', d/'a/link')
    for bad in (lambda: stage.nolinks(d), lambda: stage.inside(d, d/'a/link/escape.txt')):
        try: bad()
        except AssertionError: pass
        else: raise AssertionError('symlink accepted')
    assert stage.inside(d, d/'a/new/file.txt') == d/'a/new/file.txt'
    shutil.rmtree(d)


def test_shadowscan():
    import stage
    bundle = HERE.parent  # bundle/fsc/s1-runtime-pin-r2.json resolves to this directory
    d = _tmp(); (d/'src').mkdir(); (d/'src/unique_zz_module.py').write_text('')
    assert stage.shadowscan(d, bundle)['shadowscan'] == 'ok'
    (d/'src/belief.py').write_text('')  # unpinned module that shadows the pinned reports/explore/s1/belief.py
    try: stage.shadowscan(d, bundle)
    except AssertionError: pass
    else: raise AssertionError('shadow accepted')
    shutil.rmtree(d)


def _hc(*args):
    return subprocess.run([sys.executable, '-I', str(HERE/'hostcheck.py'), *map(str, args)], capture_output=True, text=True)


def test_hostcheck_stop_paths():
    d = _tmp(); phase = d/'stoptest-03'; (phase/'blocks').mkdir(parents=True)
    G = ['choom', '-n', '1000', '--', 'prlimit', '--as=8589934592']
    group = subprocess.Popen(G+['bash', '-c', 'sleep 120 & sleep 120; wait'], start_new_session=True)
    sup = subprocess.Popen(G+['sleep', '120'], start_new_session=True)
    time.sleep(0.5)
    (phase/'launch.json').write_text(json.dumps(dict(child_pgid=group.pid, supervisor_pid=sup.pid)))
    assert _hc('prestop', phase).returncode == 10  # no started block yet
    (phase/'blocks/X0000.started').write_text('{}')
    r = _hc('prestop', phase); assert r.returncode == 0, r.stdout+r.stderr
    (d/'pre.json').write_text(r.stdout)
    assert _hc('census', 'live', group.pid, sup.pid).returncode == 0
    assert _hc('census', 'empty', group.pid, sup.pid).returncode == 10
    touch = time.time()
    os.killpg(group.pid, 9); sup.kill(); group.wait(); sup.wait(); time.sleep(0.5)
    (phase/'supervisor-exit.json').write_text(json.dumps(dict(reason='owned_STOP', returncode=-15, remaining_group_pids=[])))
    assert _hc('census', 'empty', group.pid, sup.pid).returncode == 0
    r = _hc('stoptest', phase, touch, d/'pre.json'); assert r.returncode == 0, r.stdout+r.stderr
    assert _hc('stoptest', phase, touch-200, d/'pre.json').returncode == 10       # exit beyond the 120 s bound
    (phase/'blocks/X0000.json').write_text('{}')
    assert _hc('stoptest', phase, touch, d/'pre.json').returncode == 10           # nothing was interrupted
    (phase/'supervisor-exit.json').write_text(json.dumps(dict(reason='memory_guard', returncode=1, remaining_group_pids=[])))
    assert _hc('exitstatus', phase).returncode == 10
    (phase/'supervisor-exit.json').write_text('not json')
    assert _hc('exitstatus', phase).returncode not in (0, 10)
    shutil.rmtree(d)


def test_wrappers_fail_closed():
    def last(r): return [l for l in r.stdout.splitlines() if l.startswith('__RC=')][-1]
    r = subprocess.run(['bash', str(HERE/'session.sh'), 'launch', '127x09'], capture_output=True, text=True)
    assert r.returncode == 2 and last(r) == '__RC=2'
    r = subprocess.run(['bash', str(HERE/'remote_bootstrap.sh'), '127x03', '0'*64, '2026-10-13T04:50:00Z'], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert r.returncode != 0 and last(r) == f'__RC={r.returncode}' and not os.path.exists('/mpac/sdicks02/jobs-fsc')
    r = subprocess.run(['bash', str(HERE/'session.sh'), 'launch', '127x03', '0'*40, '0'*64, '2026-10-13T08:30:00Z'], capture_output=True, text=True)
    assert r.returncode == 2 and last(r) == '__RC=2'  # STOP_AT after the 04:50Z deadline
    r = subprocess.run(['bash', str(HERE/'session.sh'), 'launch', '127x03', '0'*40, '0'*64], capture_output=True, text=True)
    assert r.returncode == 2  # launch without STOP_AT
    r = subprocess.run(['bash', str(HERE/'stop_runner.sh'), '2026-10-13T08:30:00Z', '0'*40, '0'*64, '127x03'], capture_output=True, text=True)
    assert r.returncode == 2
    r = subprocess.run(['bash', str(HERE/'host_session.sh'), 'launch', '127x03'], capture_output=True, text=True)
    assert r.returncode == 90 and last(r) == '__RC=90'
    r = subprocess.run(['bash', str(HERE/'lan_copy_04.sh')], capture_output=True, text=True)
    assert r.returncode == 1 and 'not 127x04' in r.stderr


def test_guard_and_proof():
    plain = subprocess.Popen(['bash', '-c', 'sleep 60 & sleep 60; wait'], start_new_session=True)
    guarded = subprocess.Popen(['choom', '-n', '1000', '--', 'prlimit', '--as=8589934592', 'bash', '-c', 'sleep 60 & sleep 60; wait'],
                               start_new_session=True)
    time.sleep(0.5)
    d = _tmp()
    for name, proc in (('plain', plain), ('guarded', guarded)):
        ph = d/name; ph.mkdir()
        (ph/'launch.json').write_text(json.dumps(dict(child_pgid=proc.pid, supervisor_pid=proc.pid)))
    assert _hc('guard', d/'plain').returncode == 10
    r = _hc('guard', d/'guarded'); assert r.returncode == 0, r.stdout
    # STOP proof: a recorded PID/PGID still alive fails; once gone, the recorded checks are clean.
    J = d/'J'; (J/'logs').mkdir(parents=True); inst = J/'inst/rep03'; (inst/'rep03/blocks').mkdir(parents=True)
    assert _hc('snapshot', J/'logs/baseline-ps.json').returncode == 0
    (inst/'receipt.json').write_text(json.dumps(dict(pid=guarded.pid, pgid=guarded.pid)))
    (inst/'rep03/launch.json').write_text(json.dumps(dict(supervisor_pid=guarded.pid, supervisor_pgid=guarded.pid,
                                                           child_pid=plain.pid, child_pgid=plain.pid)))
    r = _hc('proof', J); out = json.loads(r.stdout)
    assert r.returncode == 10 and guarded.pid in out['recorded_alive'] and out['in_recorded_groups']
    for proc in (plain, guarded):
        os.killpg(proc.pid, 9); proc.wait()
    time.sleep(0.5)
    out = json.loads(_hc('proof', J).stdout)
    assert not out['recorded_alive'] and not out['in_recorded_groups']  # extras on 05 itself are not asserted here
    shutil.rmtree(d)


if __name__ == '__main__':
    for name, f in list(globals().items()):
        if name.startswith('test_'):
            f(); print('ok', name)
