import collections,datetime,hashlib,json,os,socket,time
from pathlib import Path
HERE=Path('/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/search-noise-v2')
OPS=HERE/'operations';host=socket.gethostname().split('.')[0]
assert host in ('127x01','127x04')
SHA='3ad63c0a7ad1634bac32bf5b031a7a312013497d8863aeaa3b0e2b0e077e5677'
assert hashlib.sha256((HERE/'evaluation-manifest.json').read_bytes()).hexdigest()==SHA
scope={};exec((HERE/'cells.py').read_text(),scope)
expected=[(e,c,s) for e in json.loads((HERE/'schedule.json').read_text())['pairs'] for c in (scope['CELLS'] if e['mode']=='scripts' else scope['H2H']) for s in (0,1)]
cutoff=datetime.datetime(2026,10,8,1,39,tzinfo=datetime.timezone.utc).timestamp()
logs=Path('/mpac/sdicks02/jobs/clasher') if host=='127x04' else OPS/'original-04-r2'
admitted=collections.Counter();excluded=collections.Counter();records=[];excluded_cpu=0
for p in sorted((HERE/'confirmation').glob('*.json')):
    r=json.loads(p.read_text());i=int(p.stem);ep,cell,seat=expected[i]
    for k,w in [('manifest',SHA),('terminal',True),('job',i),('seed',ep['seed']),('noise_seed',ep['noise_seed']),('pair',ep['pair']),('seat',seat),('variant',cell),('mode',ep['mode'])]:assert r[k]==w,(i,k)
    origin=r['host']['hostname'].split('.')[0];assert origin in ('127x04','127x08')
    assert (origin=='127x04' and i%248<48) or (origin=='127x08' and i%248>=148)
    # The frozen receipt stores its own completion time as started + elapsed.
    finished=r['started']+r['elapsed'];eligible=origin=='127x08' or finished<cutoff
    if origin=='127x04':
        lines=(logs/f's1-confirm-{i%248}-r2.log').read_text().splitlines()
        matches=[n for n,line in enumerate(lines) if line.startswith('{') and json.loads(line).get('job')==i]
        assert len(matches)==1,(i,'missing/duplicate worker log')
        assert not any('Traceback' in line or 'RuntimeError' in line or 'Frozen file changed:' in line for line in lines[:matches[0]]),(i,'verify failure precedes game')
    records.append(dict(job=i,origin=origin,completed_unix=finished,eligible=eligible,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    if eligible:admitted[origin]+=1
    else:
        excluded[origin]+=1;excluded_cpu+=r['cpu_seconds']
        dest=OPS/'incident-seal-overwrite-r2b'/f'excluded-post-cutoff-{host}-r2e'/p.name
        dest.parent.mkdir(parents=True,exist_ok=True);assert not dest.exists();p.rename(dest)
out=dict(utc=time.time(),host=host,rule='08: every identity-valid receipt; 04: receipt started + elapsed < 2026-10-08T01:39:00Z, terminal log precedes all verify failures',admitted_by_origin=dict(admitted),excluded_by_origin=dict(excluded),excluded_recorded_cpu_hours=excluded_cpu/3600,records=records,outcomes_inspected=False)
(OPS/f'receipt-qualification-{host}-r2e.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='records'}))
