import importlib.util
import json
import multiprocessing as mp
import os
from pathlib import Path
import signal
import time

import pytest

P = Path(__file__).parents[3]/'reports/bot/pretrain-v1/sweep/expand_eval_05.py'
spec = importlib.util.spec_from_file_location('expand_eval', P)
E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)


def claim_worker(root, cases, arm="pv1-M"):
    root = Path(root)
    for c in E.claimed_cases(cases, root, arm):
        dest = root/'rows'/f"{c['index']}.json"
        if dest.exists():
            continue
        with (root/'calls').open('a') as f:
            f.write(str(c['index'])+'\n')
        time.sleep(.003)
        dest.write_text('{}')


@pytest.mark.parametrize("arm", ["pv1-S100", "pv1-M"])
def test_exclusive_claims_across_processes(tmp_path, arm):
    (tmp_path/'rows').mkdir()
    cases = [dict(index=i) for i in range(80)]
    workers = [mp.get_context('fork').Process(target=claim_worker,args=(str(tmp_path), cases, arm)) for _ in range(8)]
    for p in workers: p.start()
    for p in workers: p.join(10); assert p.exitcode == 0
    calls = [int(x) for x in (tmp_path/'calls').read_text().splitlines()]
    assert sorted(calls) == list(range(80))
    claim_worker(str(tmp_path), cases, arm)
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


def test_marker_bad_present_data_fails_closed(tmp_path, monkeypatch):
    import pytest
    (tmp_path/'rows').mkdir()
    p=tmp_path/'rows'/'bad.attempt'; p.write_text('{')
    with pytest.raises(json.JSONDecodeError): E.active_attempts(tmp_path,7)
    monkeypatch.setattr(E,'read',lambda p:(_ for _ in ()).throw(PermissionError('denied')))
    with pytest.raises(PermissionError): E.active_attempts(tmp_path,7)


def test_validation_binds_only_registered_arms(tmp_path):
    import pytest
    package=tmp_path/'package'; package.mkdir()
    code=package/'eval.py'; code.write_text('# frozen evaluator')
    checkpoint=tmp_path/'anchor.pt';checkpoint.write_bytes(b'weights')
    bank=tmp_path/'bank.json';bank.write_text(json.dumps(dict(cases=[dict(index=1)])))
    out=tmp_path/'out';out.mkdir()
    for arm in ('pv1-S100','pv1-M'):
        man=dict(paired_only=True,arm=arm,ckpt=str(checkpoint),ckpt_sha256=E.sha(checkpoint),
                 bank_path=str(bank),bank_sha256=E.sha(bank),code_sha256={'eval.py':E.sha(code)},assigned=[1])
        (out/'manifest.json').write_text(json.dumps(man))
        assert E.validate(code,out,arm)[0]['arm']==arm
        assert E.validate(code,out)[0]['arm']==arm  # Legacy power command stays valid.
        with pytest.raises(AssertionError,match='unexpected arm'):
            E.validate(code,out,'pv1-M' if arm=='pv1-S100' else 'pv1-S100')
    man['arm']='pv1-L';(out/'manifest.json').write_text(json.dumps(man))
    with pytest.raises(AssertionError):E.validate(code,out)


def test_s100_claims_keep_exclusive_lock_across_yield(tmp_path):
    import fcntl
    import pytest
    gen=E.claimed_cases([dict(index=1)],tmp_path,'pv1-S100')
    assert next(gen)==dict(index=1)
    with (tmp_path/'expansion-claims/0001.lock').open('a') as f:
        with pytest.raises(BlockingIOError):fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        gen.close()
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)


def test_parent_resumes_only_after_successful_rows(tmp_path,monkeypatch):
    import pytest
    from types import SimpleNamespace
    code=tmp_path/'eval.py'
    code.write_text('GiB=1\ndef mem_available(): return 1000\ndef same_case(row,case): return True\ndef origins_valid(o): return True,None\n')
    out=tmp_path/'out';(out/'rows').mkdir(parents=True)
    man=dict(arm='pv1-S100',ckpt='anchor',ckpt_sha256='ckpt',bank_sha256='bank',runtime_pins={})
    (out/'manifest.json').write_text(json.dumps(man))
    monkeypatch.setattr(E,'validate',lambda *a:(man,[dict(index=1)]))
    monkeypatch.setattr(E,'drain',lambda *a:dict(parent=dict(pid=123,start='1')))
    monkeypatch.setattr(E.os,'uname',lambda:SimpleNamespace(nodename='127x05'))
    monkeypatch.setattr(E.os,'getloadavg',lambda:(0,0,0))
    monkeypatch.setattr(E.os,'fork',lambda:100)
    monkeypatch.setattr(E.os,'waitpid',lambda *a:(100,0))
    monkeypatch.setattr(E.sys,'argv',['expand','--code',str(code),'--out',str(out),'--legacy-parent','123',
                                      '--workers','1','--expected-arm','pv1-S100'])
    signals=[];monkeypatch.setattr(E,'send',lambda *a:signals.append(a))
    monkeypatch.delitem(E.sys.modules,'bot',raising=False)
    with pytest.raises(FileNotFoundError):E.main()
    assert signals==[]
    # Only a fresh fixture is allowed; a real uncertain intent cannot be retried.
    (out/'expansion-pool-intent.json').unlink()
    row=dict(ckpt_sha256='ckpt',bank_sha256='bank',runtime_pins={},module_origins_after={})
    (out/'rows/0001-pv1-S100.json').write_text(json.dumps(row))
    E.main()
    assert signals==[(dict(pid=123,start='1'),signal.SIGCONT)]
