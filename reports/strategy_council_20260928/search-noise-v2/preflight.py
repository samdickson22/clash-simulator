"""Build a fresh, timing-only, source-bound r2 preflight receipt."""
from pathlib import Path
import hashlib,json,re,time,socket
HERE=Path(__file__).resolve().parent
JOBS=Path('/mpac/sdicks02/jobs/clasher')
NATIVE='13e908c5cb235a3d81cd585b12caf6c2e5fa624888ed3a3cc0ede14933a5f309'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    assert not (HERE/'evaluation-manifest.json').exists(), 'already sealed'
    inputs=json.loads((HERE/'r2-preflight-inputs.json').read_text())
    for rel,want in inputs['files'].items():
        assert digest(HERE/rel)==want, ('preflight input changed',rel)
    assert digest(HERE/'runtime/support/clasher_core.abi3.so')==NATIVE
    evidence={};pilot=[]
    parents=[f's1-exact-replays-{i}-r2' for i in range(3)]
    parents+=['s1-tests-seal-r2','s1-fork-pilot-r2','s1-final-full-pilots-r2','s1-reference-full-pilot-r2']
    labels=parents+[f's1-fullpilot-{i}-r2' for i in range(36,54)]+[f's1-forkpilot-{i}-r2' for i in range(25,29)]
    for label in labels:
        receipt=JOBS/f'{label}.exit'
        assert receipt.read_text().strip()=='0',label
        assert receipt.stat().st_mtime>=inputs['created_unix'], ('stale receipt',label)
        evidence[label]=dict(exit_sha256=digest(receipt),log_sha256=digest(JOBS/f'{label}.log'))
    replay=[]
    for i in range(3):
        p=HERE/'replay-tests'/f'derived-audit-{i}.json'
        replay.extend(json.loads(p.read_text()));evidence[str(p.relative_to(HERE))]=digest(p)
    assert len(replay)==24 and sum(r['decisions'] for r in replay)==23058
    assert all(r['full_recorded_game_parity'] and r['elixir_errors']==r['hand_errors']==r['cycle_errors']==r['next_errors']==0 for r in replay)
    for i in range(36,54):
        p=HERE/f'pilot-{i}-full.json';row=json.loads(p.read_text())
        assert row['terminal'] and 'score' not in row and 'winner' not in row
        assert row['host']['hostname'].split('.')[0]=='127x04'
        pilot.append(row);evidence[p.name]=digest(p)
    assert len({r['variant'] for r in pilot})==18
    for i in range(25,29):
        p=HERE/f'pilot-{i}-1200.json';row=json.loads(p.read_text())
        assert row['ticks']==1200 and 'score' not in row and 'winner' not in row
        evidence[p.name]=digest(p)
    reference=json.loads((HERE/'pilot-61-full.json').read_text())
    optimized=json.loads((HERE/'pilot-43-full.json').read_text())
    assert reference['terminal'] and reference['variant']==optimized['variant']=='E4-N64'
    assert reference['action_sha256']==optimized['action_sha256']
    assert 'score' not in reference and 'winner' not in reference
    evidence['pilot-61-full.json']=digest(HERE/'pilot-61-full.json')
    evidence['optimized_reference_action_equivalence']=optimized['action_sha256']
    testlog=(JOBS/'s1-tests-seal-r2.log').read_text()
    assert re.search(r'Ran 14 tests',testlog) and '\nOK\n' in testlog
    metered=[]
    for label in parents:
        p=JOBS/f'{label}.log'
        values=re.findall(r'^\t(?:User time \(seconds\)|System time \(seconds\)):\s*([0-9.]+)',p.read_text(),re.M)
        assert len(values)==2, ('missing parent process CPU accounting',label)
        metered.append(dict(log=p.name,cpu_seconds=sum(map(float,values))))
    evidence['r2-preflight-inputs.json']=digest(HERE/'r2-preflight-inputs.json')
    out=dict(protocol='r2',preconfirmation_linux_cpu_hours=sum(r['cpu_seconds'] for r in metered)/3600,
             metered_jobs=metered,passed=True,utc=time.time(),host=socket.gethostname(),
             evidence=evidence,exact_replay_games=24,exact_checks=23058,linux_tests=14,
             native_sha256=NATIVE,pilots=pilot,
             files={p.name:digest(p) for p in HERE.glob('*.py')})
    (HERE/'preflight.json').write_text(json.dumps(out,indent=2)+'\n')
    print('r2 preflight passed; no strength outcomes inspected')

if __name__=='__main__':main()
