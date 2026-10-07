"""Build a timing-only, source-bound preflight receipt before sealing."""
from pathlib import Path
import hashlib,json,re,time
HERE=Path(__file__).resolve().parent
JOBS=Path('/mpac/sdicks02/jobs/clasher')

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    evidence={};pilot=[]
    labels=['s1-exact-replays-0-r1','s1-exact-replays-1-r1','s1-exact-replays-2-r1',
            's1-tests-seal-r4','s1-fork-pilot-r1']
    labels += ['s1-final-full-pilots-r1','s1-optimized-full-pilot-r1']
    labels += [f's1-fullpilot-{i}-r1' for i in range(36,54)]
    for label in labels:
        receipt=JOBS/f'{label}.exit'
        assert receipt.read_text().strip()=='0',(label,receipt.read_text())
        evidence[label]=dict(exit_sha256=digest(receipt),log_sha256=digest(JOBS/f'{label}.log'))
    replay=[]
    for p in sorted((HERE/'replay-tests').glob('*.json')):
        replay.extend(json.loads(p.read_text()));evidence[p.name]=digest(p)
    assert len(replay)==24 and sum(r['decisions'] for r in replay)==23058
    assert all(r['full_recorded_game_parity'] and r['elixir_errors']==r['hand_errors']==r['cycle_errors']==r['next_errors']==0 for r in replay)
    for i in range(36,54):
        p=HERE/f'pilot-{i}-full.json';row=json.loads(p.read_text())
        assert row['terminal'] and 'score' not in row and 'winner' not in row
        pilot.append(row);evidence[p.name]=digest(p)
    optimized=json.loads((HERE/'pilot-61-full.json').read_text())
    baseline=json.loads((HERE/'pilot-43-full.json').read_text())
    assert optimized['terminal'] and optimized['action_sha256']==baseline['action_sha256']
    evidence['optimized_action_equivalence']=optimized['action_sha256']
    testlog=(JOBS/'s1-tests-seal-r4.log').read_text()
    assert re.search(r'Ran 14 tests',testlog) and '\nOK\n' in testlog
    pre_cpu=0.
    metered=[]
    for p in JOBS.glob('s1-*.log'):
        if 'confirm' in p.name:continue
        values=re.findall(r'^\t(?:User time \(seconds\)|System time \(seconds\)):\s*([0-9.]+)',p.read_text(),re.M)
        if values:
            seconds=sum(map(float,values));pre_cpu+=seconds;metered.append(dict(log=p.name,cpu_seconds=seconds))
    out=dict(preconfirmation_linux_cpu_hours=pre_cpu/3600,metered_jobs=metered,passed=True,utc=time.time(),evidence=evidence,exact_replay_games=24,exact_checks=23058,
             pilots=pilot,files={p.name:digest(p) for p in HERE.glob('*.py')})
    (HERE/'preflight.json').write_text(json.dumps(out,indent=2)+'\n')
    print('preflight passed; no strength outcomes inspected')

if __name__=='__main__':main()
