"""Review the known diagnostic stop and register outcome-preserving recovery."""
import hashlib,json,os,shlex,subprocess,time
from pathlib import Path
import fullpool_clean
J=Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2');D=J/'fullpool'
def cmd(args):return subprocess.check_output(list(map(str,args)),text=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return cmd(['date','-u','+%Y-%m-%dT%H:%M:%SZ']).strip()
def active(host):
    code="from pathlib import Path; import json; out=[]\nfor p in Path('/proc').glob('[0-9]*/cmdline'):\n try:\n  a=p.read_bytes().split(b'\\0')\n  if b'/mpac/sdicks02/jobs/clasher/bot-deckopt2/fullpool_entry.py' in a:out.append(int(p.parent.name))\n except (FileNotFoundError,PermissionError,ProcessLookupError):pass\nprint(json.dumps(out))"
    return json.loads(cmd(['ssh',host,shlex.join(['python3','-c',code])]))
def main():
    while True:
        live={h:active(h) for h in ('127x01','127x03','127x04')}
        (D/'drain-status.json').write_text(json.dumps(dict(utc=utc(),active=live),indent=2))
        if not any(live.values()):break
        time.sleep(15)
    for host in ('127x01','127x03','127x04'):
        cmd(['rsync','-a',f'{host}:{D}/validation/rows/',str(D/'validation/rows')+'/'])
    rows={int(p.stem):json.loads(p.read_text()) for p in (D/'validation/rows').glob('*.json')}
    assert all(not fullpool_clean.problems(r) for r in rows.values()),[(i,fullpool_clean.problems(r)) for i,r in rows.items() if fullpool_clean.problems(r)]
    bank=json.loads((D/'validation/bank.json').read_text());arms=len(bank['candidates'])*len(bank['players'])
    partial=[]
    for p in (D/'claims').glob('*.json'):
        claim=json.loads(p.read_text());i=claim['index'];done=[a for a in range(arms) if i*arms+a in rows]
        if len(done)<arms:partial.append(dict(index=i,host=claim['worker'].split('-')[0],preserved_arms=done,original_claim_sha256=sha(p)))
    helpers=('fullpool_clean.py','fullpool_resume.py','fullpool_resume_queue.py','fullpool_resume_entry.py','fullpool_wait_entry.py','run-fullpool-resume.sh')
    amendment=dict(utc=utc(),reason='Expected visual-only SpearGoblin_Dummy counter was misclassified; raw rows unchanged',
        original_manifest_sha256=sha(D/'manifest.json'),bank_sha256=sha(D/'validation/bank.json'),
        unchanged_game_worker_sha256=sha(J/'fullpool_worker.py'),helper_sha256={n:sha(J/n) for n in helpers},
        drain_check=live,partial_blocks=partial,preserved_rows={p.name:sha(p) for p in (D/'validation/rows').glob('*.json')})
    assert not (D/'resume-manifest.json').exists()
    (D/'resume-manifest.json').write_text(json.dumps(amendment,indent=2));(D/'recovery-claims').mkdir()
    # Every original producer is dead, all retained rows are classified clean,
    # and every partial block is pinned to its original host before reopening.
    (D/'STOP').rename(D/'STOP-expected-visual-counter')
    print(json.dumps(dict(utc=utc(),preserved=len(rows),partial_blocks=partial)),flush=True)
if __name__=='__main__':main()
