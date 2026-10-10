"""05 command-center JSON/process metadata only; no model or scientific imports."""
import argparse,concurrent.futures,json,subprocess
from pathlib import Path
J='/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r2'
B='/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1'
ROOT=Path(__file__).resolve().parents[1]
ARMS={'R3c':'127x09','R3d':'127x16','R3e':'127x13'}
def check(spec):
    arm,host=spec
    code='''import hashlib,json,subprocess
from pathlib import Path
j=Path(JOB);arm=ARM;files=[];values={}
names=[arm+'-'+n+'.json' for n in ('launch','health','exit')]+['fits/'+arm+'/'+n+'.json' for n in ('inputs','complete','segment')]+['BASE-STAGING.json','VOID-ATTEMPT1-VACATED.json','prelaunch.json']
for n in names:
 p=j/n
 if p.exists():
  raw=p.read_bytes();v=json.loads(raw);files.append(dict(relative=n,sha256=hashlib.sha256(raw).hexdigest(),value=v));values[n]=v
launch=values.get(arm+'-launch.json');active=bool(launch and Path('/proc/'+str(launch['supervisor_pid'])).exists())
step=0;p=j/'fits'/arm/'train.jsonl'
if p.exists():
 with p.open('rb') as f:
  f.seek(0,2);size=f.tell();f.seek(max(0,size-2048));lines=f.read().splitlines()
 for line in reversed(lines):
  try:step=int(json.loads(line)['step']);break
  except (ValueError,KeyError):pass
print(json.dumps(dict(arm=arm,host=HOST,active=active,step=step,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),files=files)))
'''.replace('JOB',repr(J)).replace('ARM',repr(arm)).replace('HOST',repr(host))
    p=subprocess.run(['ssh','-o','ConnectTimeout=10',host,'nice -n 10 taskset -c 126 '+B+'/venv/bin/python -B -'],input=code,capture_output=True,text=True,check=True,timeout=30)
    bundle=json.loads(p.stdout);target=ROOT/'receipts/process-snapshots'/host;target.mkdir(parents=True,exist_ok=True);history=target/'history';history.mkdir(exist_ok=True)
    for item in bundle.pop('files'):
        n=item['relative'].replace('/','--');raw=json.dumps(item,indent=2)+'\n';(target/n).write_text(raw);p=history/(n[:-5]+'-'+item['sha256']+'.json')
        if not p.exists():p.write_text(raw)
    return bundle
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:r=list(ex.map(check,ARMS.items()))
    Path(a.output).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
