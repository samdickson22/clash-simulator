import importlib.util
import json
import multiprocessing as mp
import os
from pathlib import Path
import signal
import time

P = Path(__file__).parents[3]/'reports/bot/pretrain-v1/sweep/expand_eval_05.py'
spec = importlib.util.spec_from_file_location('expand_eval', P)
E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)


def claim_worker(root, cases):
    root = Path(root)
    for c in E.claimed_cases(cases, root, 'pv1-M'):
        dest = root/'rows'/f"{c['index']}.json"
        if dest.exists():
            continue
        with (root/'calls').open('a') as f:
            f.write(str(c['index'])+'\n')
        time.sleep(.003)
        dest.write_text('{}')


def test_exclusive_claims_across_processes(tmp_path):
    (tmp_path/'rows').mkdir()
    cases = [dict(index=i) for i in range(80)]
    workers = [mp.get_context('fork').Process(target=claim_worker,args=(str(tmp_path), cases)) for _ in range(8)]
    for p in workers: p.start()
    for p in workers: p.join(10); assert p.exitcode == 0
    calls = [int(x) for x in (tmp_path/'calls').read_text().splitlines()]
    assert sorted(calls) == list(range(80))
    claim_worker(str(tmp_path), cases)
    assert (tmp_path/'calls').read_text().splitlines() == [str(i) for i in calls]


def test_crashed_claim_releases_but_preserves_attempt(tmp_path):
    (tmp_path/'rows').mkdir()
    pid = os.fork()
    if pid == 0:
        for c in E.claimed_cases([dict(index=1)], tmp_path, 'pv1-M'):
            (tmp_path/'rows'/'0001-pv1-M.attempt').write_text('{"pid": 123}')
            os._exit(3)
    os.waitpid(pid, 0)
    assert list(E.claimed_cases([dict(index=1)], tmp_path, 'pv1-M')) == [dict(index=1)]
    assert (tmp_path/'rows'/'0001-pv1-M.attempt').exists()


def test_drain_never_interrupts_started_attempt(tmp_path):
    (tmp_path/'rows').mkdir()
    script = tmp_path/'legacy.py'
    script.write_text('''import os,time,json,sys
from pathlib import Path
root=Path(sys.argv[1]); kids=[]
for w in range(4):
 p=os.fork()
 if p==0:
  for i in range(8):
   q=root/'rows'/f'{w}-{i}.attempt'
   q.write_text(json.dumps(dict(pid=os.getpid())))
   time.sleep(.08)
   q.with_suffix('.json').write_text('{}')
   q.unlink()
   time.sleep(.025)
  os._exit(0)
 kids.append(p)
(root/'started').write_text('yes')
for p in kids: os.waitpid(p,0)
''')
    import subprocess
    p = subprocess.Popen([os.sys.executable, str(script), str(tmp_path)])
    try:
        while not (tmp_path/'started').exists(): time.sleep(.005)
        initial = list((tmp_path/'rows').glob('*.attempt'))
        assert initial
        state = E.drain(script, tmp_path, p.pid, tmp_path/'receipt.json', timeout=10)
        assert not list((tmp_path/'rows').glob('*.attempt'))
        assert all(q.with_suffix('.json').exists() for q in initial)
        assert E.proc(p.pid)['state'] == 'T'
        assert len(state['retired']) == 4
        E.send(state['parent'], signal.SIGCONT)
        assert p.wait(5) == 0
    finally:
        if p.poll() is None:
            p.send_signal(signal.SIGCONT); p.terminate(); p.wait(5)


def test_pid_reuse_guard():
    current = E.proc(os.getpid())
    assert E.same_process(dict(pid=os.getpid(), start=current['start']))
    assert E.same_process(dict(pid=os.getpid(), start='impossible')) is None


def test_other_workers_sealing_during_marker_scan(tmp_path, monkeypatch):
    (tmp_path/'rows').mkdir()
    (tmp_path/'rows'/'unrelated.attempt').write_text('{"pid": 99}')
    (tmp_path/'rows'/'active.attempt').write_text('{"pid": 7}')
    original_read = E.read
    def vanishing_read(path):
        if path.name == 'unrelated.attempt':
            path.unlink()
        return original_read(path)
    monkeypatch.setattr(E, 'read', vanishing_read)
    assert E.active_attempts(tmp_path, 7) == [tmp_path/'rows'/'active.attempt']
