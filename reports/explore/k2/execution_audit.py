"""Final read-only source, execution and process-vacate receipt."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def utc():return subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip()
def main():
    p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();phase=a.job/'reporting'
    pin=json.loads((a.job/'runtime-pin.json').read_text());cfg=json.loads((a.job/'repo/reports/explore/k2/plan.json').read_text())
    assert sha(a.job/'repo/reports/explore/k2/plan.json')==pin['plan_sha256']
    assert sha(a.job/'native/clasher_core.abi3.so')==pin['native_sha256']==cfg['source_reference']['native_sha256']
    assert sha(Path(cfg['policy']['checkpoint']))==cfg['policy']['checkpoint_sha256']
    source_mismatch=[f for f,h in pin['files'].items() if sha(a.job/'repo'/f)!=h]
    native_mismatch=[f for f,h in pin['native_source'].items() if sha(a.job/'native-source'/f)!=h]
    assert not source_mismatch and not native_mismatch,(source_mismatch,native_mismatch)
    receipt=json.loads((phase/'receipt.json').read_text());exited=json.loads((phase/'supervisor-exit.json').read_text());launch=json.loads((phase/'launch.json').read_text())
    assert receipt['games']==1800 and receipt['terminal'] and exited['returncode']==0 and exited['reason'] is None
    census=[json.loads(x) for x in (phase/'census.jsonl').read_text().splitlines()]
    assert census and all(not x['paused'] and x['memavailable_GiB']>=24 for x in census)
    groups={launch['supervisor_pgid'],launch['child_pgid']};remaining=[]
    for d in Path('/proc').iterdir():
        if not d.name.isdigit():continue
        try:
            stat=(d/'stat').read_text().rsplit(')',1)[1].split();pgid=int(stat[2])
            if pgid in groups:remaining.append(dict(pid=int(d.name),pgid=pgid,state=stat[0],cmd=(d/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')))
        except FileNotFoundError:continue
    assert not remaining,remaining
    result=dict(utc=utc(),complete=True,receipt=receipt,supervisor_exit=exited,launch=launch,census_samples=len(census),min_memavailable_GiB=min(x['memavailable_GiB'] for x in census),paused_samples=0,source_files_checked=len(pin['files']),native_source_files_checked=len(pin['native_source']),source_mismatch=[],native_mismatch=[],runtime_pin_sha256=sha(a.job/'runtime-pin.json'),plan_sha256=pin['plan_sha256'],native_sha256=pin['native_sha256'],fully_vacated_pgids=sorted(groups),remaining_processes=[],G_STOP03_retained=Path('/mpac/sdicks02/jobs/clasher/exit-g-topup-20261010/STOP-03').exists())
    assert result['G_STOP03_retained']
    a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('receipt','launch','supervisor_exit')},indent=2))
if __name__=='__main__':main()
