"""05 JSON/SHA/process metadata collection only; no arrays, Torch or native."""
import argparse,concurrent.futures,hashlib,json,subprocess
from pathlib import Path
J='/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r2';B='/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1'
ROOT=Path(__file__).resolve().parents[1]
def collect(host):
    code='''import hashlib,json,os,subprocess
from pathlib import Path
j=Path(JOB);paths=set(j.glob('*meter*.json'))|set(j.glob('*STAGING*.json'))|set(j.glob('*.log.identity.json'))
for name in ('EVAL-PGIDS.json','CPU-RELEASE-EVIDENCE.json','CPU-RELEASE-ADMITTED.json','REGRET-CPU-EVIDENCE.json','REGRET-CPU-ADMITTED.json','REGRET-SHARED-AUTHORITY.json','SHARED03-DEPLOYMENT.json','SHARED03-NICE19-DEPLOYMENT.json','REGRET-NICE19-RESTART.json','SHARED03-REPAIR-DEPLOYMENT.json','SHARED03-REPAIR-TESTS.json','SHARED03-TESTS.json','EVALUATION-DEPLOYMENT.json','CODE-QUALIFICATION.json','evaluation-freeze.json','evaluation-prelaunch.json','qualification-descriptive.json','qualification-stage2.json','descriptive-results.json','stage1-results.json','stage2-results.json','EVAL-VACATED.json'):
 paths.add(j/name)
if HOST=='127x03':
 for pattern in ('*meter*.json','*STAGING*.json','*.log.identity.json'):
  paths.update((j/'timing03').glob(pattern))
 for name in ('EVAL-PGIDS.json','CPU-RELEASE-EVIDENCE.json','CPU-RELEASE-ADMITTED.json','TIMING03-AUTHORITY.json','CODE-QUALIFICATION.json','evaluation-freeze.json','evaluation-prelaunch.json','qualification-stage2.json','stage2-results.json','EVAL-VACATED.json'):
  paths.add(j/'timing03'/name)
 for folder in ('k0-stage2-smoke','k0-stage2'):
  paths.update((j/'timing03'/folder).glob('*.json'))
for folder in ('offline','k0-descriptive-smoke','k0-descriptive','k0-stage2-smoke','k0-stage2','regret'):
 p=j/folder
 paths.update(p.glob('*meter*.json'));paths.update(p.glob('*.json'))
 if folder=='regret':paths.update((p/'games').glob('*.json'))
records=[]
for p in sorted(paths):
 if not p.is_file():continue
 raw=p.read_bytes();v=json.loads(raw);records.append(dict(relative=str(p.relative_to(j)),sha256=hashlib.sha256(raw).hexdigest(),raw=raw.decode(),value=v))
live=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  cmd=(p/'cmdline').read_bytes().replace(b'\\0',b' ').decode(errors='replace')
  if cmd.startswith(('ssh ','sshd:','rsync ')):continue
  if str(j)+'/' in cmd:live.append(dict(pid=int(p.name),pgid=os.getpgid(int(p.name)),command=cmd[:500]))
 except (FileNotFoundError,ProcessLookupError,PermissionError):pass
print(json.dumps(dict(host=HOST,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),records=records,live=live)))
'''.replace('JOB',repr(J)).replace('HOST',repr(host))
    core=39 if host=='127x01' else 59 if host=='127x03' else 126
    interpreter='/usr/bin/python3' if host=='127x03' else B+'/venv/bin/python'
    p=subprocess.run(['ssh','-o','ConnectTimeout=10',host,'nice -n '+('19' if host=='127x03' else '10')+' taskset -c '+str(core)+' '+interpreter+' -B -'],input=code,text=True,capture_output=True,check=True,timeout=45)
    bundle=json.loads(p.stdout);target=ROOT/'receipts/evaluation-snapshots'/host;target.mkdir(parents=True,exist_ok=True);history=target/'history';history.mkdir(exist_ok=True)
    for item in bundle.pop('records'):
        assert hashlib.sha256(item['raw'].encode()).hexdigest()==item['sha256'] and json.loads(item['raw'])==item['value']
        name=item['relative'].replace('/','--');raw=json.dumps(item,indent=2)+'\n';(target/name).write_text(raw);p=history/(name[:-5]+'-'+item['sha256']+'.json')
        if not p.exists():p.write_text(raw)
    (target/'collection.json').write_text(json.dumps(bundle,indent=2)+'\n');return dict(host=host,utc=bundle['utc'],live_processes=len(bundle['live']))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--hosts',nargs='+',default=['127x09','127x16','127x13','127x03']);a=p.parse_args()
    assert set(a.hosts)<=set(('127x09','127x16','127x13','127x01','127x03'))
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:print(json.dumps(list(ex.map(collect,a.hosts)),indent=2))
