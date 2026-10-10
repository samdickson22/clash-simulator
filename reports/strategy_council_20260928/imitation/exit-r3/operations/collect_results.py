"""Command-center metadata only; retain immutable meters before resume/transfer."""
import argparse,hashlib,json,shlex,subprocess
from pathlib import Path
J='/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r1'
B='/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1'
CONTEXT={'127x09':(10,126),'127x16':(10,126),'127x04':(19,19),'127x03':(10,59),'127x01':(10,39)}
REPO=Path(__file__).resolve().parents[1]

def collect(host):
    nice,core=CONTEXT[host]
    # No Torch/native imports, games, array reads, checkpoints or bulk data.
    code='''import hashlib,json,subprocess
from pathlib import Path
j=Path(%r)
fixed=['R3a-launch.json','R3b-launch.json','R3a-health.json','R3b-health.json','R3a-exit.json','R3b-exit.json','stage1-results.json','stage2-results.json','wrapper-qualification.json','CPU-STAGING.json','REGRET04-STAGING.json','REGRET04-VACATED.json','REGRET04-BASE-VACATED.json','REGRET04-PGIDS.json']
fixed += ['fits/'+a+'/'+n for a in ('R3a','R3b') for n in ('complete.json','segment.json')]
fixed += ['offline/'+a+n for a in ('R3a','R3b') for n in ('.json','-calibration.json')]
patterns=['offline/*-attempt-meter-*.json','regret/pool-meter-*.json','stage3-sdefault/pool-meter-*.json','stage3-sdefault-smoke/pool-meter-*.json','regret04-staging-meter-*.json','reduce-*-meter.json']
paths=set(j/n for n in fixed)
for pattern in patterns:paths.update(j.glob(pattern))
files=[]
for p in sorted(paths):
    if p.is_file():
        raw=p.read_bytes();files.append(dict(relative=str(p.relative_to(j)),sha256=hashlib.sha256(raw).hexdigest(),value=json.loads(raw)))
print(json.dumps(dict(host=%r,utc=subprocess.check_output(['date','-u','+%%FT%%TZ'],text=True).strip(),files=files)))
'''%(J,host)
    command=f'nice -n {nice} taskset -c {core} {shlex.quote(B+"/venv/bin/python")} -B -'
    result=subprocess.run(['ssh','-o','ConnectTimeout=10',host,command],input=code,capture_output=True,text=True,check=True,timeout=30)
    bundle=json.loads(result.stdout);target=REPO/'receipts/process-snapshots'/host;target.mkdir(parents=True,exist_ok=True)
    for item in bundle['files']:
        name=item['relative'].replace('/','--');p=target/name
        # Preserve complete process meters/decisions even when the remote path
        # is overwritten by an exact checkpoint resume or guarded replay.
        immutable=target/'history'/(name[:-5]+'-'+item['sha256']+'.json')
        immutable.parent.mkdir(exist_ok=True)
        if not immutable.exists():immutable.write_text(json.dumps(item,indent=2)+'\n')
        p.write_text(json.dumps(item,indent=2)+'\n')
    (target/'snapshot.json').write_text(json.dumps(dict(host=host,utc=bundle['utc'],files=len(bundle['files'])),indent=2)+'\n')
    return dict(host=host,files=len(bundle['files']),utc=bundle['utc'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--hosts',nargs='+',choices=tuple(CONTEXT),default=['127x09','127x16']);a=p.parse_args()
    print(json.dumps([collect(h) for h in a.hosts],indent=2))
