"""Final owned-job/source/schedule/census audit; never signal or alter services."""
import argparse,hashlib,json,os,socket,subprocess
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--source-correction',type=Path);a=ap.parse_args();job=a.job;repo=job/'repo';pin=json.loads((job/'runtime-pin.json').read_text())
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    correction=json.loads(a.source_correction.read_text()) if a.source_correction else None
    corrections=[]
    scientific=[];critical={'reports/explore/k-anytime/'+f for f in ('planner.py','run.py','runtime.sh','plan.json','supervise.py','launch.sh','detach.sh')}
    for name,h in pin['files'].items():
        if name in critical or name.startswith(('src/','engine-rs/','imitation/','reports/explore/e1/','reports/explore/w-screen8/','reports/explore/w-confirm/','reports/strategy_council_20260928/','reports/perf-audit/quickwins/')):
            if correction and name==correction['source_file']:
                assert h==correction['old_sha256']
                h=correction['qualified_prelaunch_sha256'];corrections.append(correction)
            assert sha(repo/name)==h,name;scientific.append(name)
    assert sha(job/'native/clasher_core.abi3.so')==pin['native_sha256']
    for name,h in pin['native_source'].items():assert sha(job/'native-source'/name)==h,name
    stages={};pauses=0
    for stage in ('single','threaded'):
        p=job/'reporting'/stage;schedule=json.loads((p/'schedule.json').read_text());receipt=json.loads((p/'receipt.json').read_text());exit=json.loads((p/'supervisor-exit.json').read_text())
        assert schedule['config_sha256']==pin['plan_sha256'] and schedule['native_sha256']==pin['native_sha256']
        assert receipt['games']==len(schedule['cases'])==len(list((p/'games').glob('*.json'))) and receipt['terminal'] and exit['returncode']==0
        census=[json.loads(x) for x in (p/'census.jsonl').read_text().splitlines()];pauses+=sum(x['paused'] for x in census)
        stages[stage]=dict(receipt=receipt,exit=exit,schedule_sha256=sha(p/'schedule.json'),launch=json.loads((p/'launch.json').read_text()),census_samples=len(census),paused_samples=sum(x['paused'] for x in census))
    assert (job/'REPORTING-DONE').exists()
    others=[]
    for p in Path('/proc').glob('[0-9]*'):
        try:
            pid=int(p.name);cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            if pid!=os.getpid() and str(job) in cmd and (p/'comm').read_text().strip() in ('python','python3','python3.12'):others.append(pid)
        except (OSError,ProcessLookupError):pass
    assert not others,others
    result=dict(audited_at_utc=subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip(),host=socket.gethostname(),reporting_games=sum(v['receipt']['games'] for v in stages.values()),stages=stages,paused_samples=pauses,scientific_files_verified=len(scientific),explicit_prelaunch_pin_corrections=corrections,native_source_files_unchanged=len(pin['native_source']),native_sha256=pin['native_sha256'],plan_sha256=pin['plan_sha256'],remaining_owned_python_processes=others,all_reporting_terminal=True,reporting_done_at_utc=(job/'REPORTING-DONE').read_text().strip())
    a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='stages'}))
if __name__=='__main__':main()
