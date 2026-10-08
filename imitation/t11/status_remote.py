"""Small read-only remote status; no checkpoint loads, dataset reads or scoring."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import socket
import subprocess


def main():
    host=socket.gethostname().split('.')[0]
    assert host in ('127x16','127x18')
    seed={'127x16':2026100821,'127x18':2026100822}[host]
    base=Path('/mpac/sdicks02/repos/clasher-lease');work=base/'t11-20261008-v1'
    label=f't11-v2-main-{seed}-v1';out=work/'runs'/f'main-{seed}'
    result=dict(host=host,at=datetime.now(timezone.utc).isoformat(),seed=seed,label=label,output=str(out))
    copy_label='t11-v2-store-copy-'+host+'-v1'
    for name,p in [('lease',Path('/mpac/sdicks02/fleet-leases',host+'.json')),
                   ('state',base/'jobs'/(label+'.state.json')),('exit',base/'jobs'/(label+'.exit.json')),
                   ('copy_state',base/'jobs'/(copy_label+'.state.json')),('copy_exit',base/'jobs'/(copy_label+'.exit.json')),
                   ('copy',work/'copy-receipt.json'),('complete',out/'complete.json')]:
        result[name]=json.loads(p.read_text()) if p.exists() else None
    all_processes={}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            if p.stat().st_uid!=os.getuid():continue
            argv=(p/'cmdline').read_bytes().split(b'\0');cmd=b' '.join(argv).decode(errors='replace')
            stat=(p/'stat').read_text().split(') ',1)[1].split()
            all_processes[int(p.name)]=dict(pid=int(p.name),ppid=int(stat[1]),start_ticks=int(stat[19]),nice=int(stat[16]),
                                  cpu_ticks=int(stat[11])+int(stat[12]),command=cmd)
        except (FileNotFoundError,ProcessLookupError):continue
    owned={pid for pid,p in all_processes.items() if any(s in p['command'] for s in
           ('/mpac/sdicks02/repos/clasher','/mpac/sdicks02/jobs/clasher','imitation.t11'))}
    while True:
        new={pid for pid,p in all_processes.items() if p['ppid'] in owned}-owned
        if not new:break
        owned.update(new)
    processes=[]
    for pid in sorted(owned):
        try:
            p=all_processes[pid]
            p['pss_bytes']=sum(int(l.split()[1])*1024 for l in Path('/proc',str(pid),'smaps_rollup').read_text().splitlines() if l.startswith('Pss:'))
            processes.append(p)
        except (FileNotFoundError,ProcessLookupError):continue
    result['borrower_processes']=processes
    result['verified_processes']=[p for p in processes if str(work) in p['command'] and 'imitation.t11.train' in p['command']]
    result['console_users']=int(subprocess.check_output([str(Path.home()/'.local/bin/fleet-console-users')],text=True))
    result['who']=subprocess.check_output(['who'],text=True)
    result['gpu']=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip()
    result['borrower_pss_bytes']=sum(p['pss_bytes'] for p in processes)
    lease=result['lease'];now=datetime.now(timezone.utc)
    result['process_cap']=min(96,lease['max_workers'],16 if result['console_users'] or result['who'].strip() else 96) if lease else 0
    result['checks']=dict(live_lease=bool(lease and lease['project']=='clasher' and lease['gpu'] and not lease.get('refused') and not lease.get('reclaim') and datetime.fromisoformat(lease['expected_end_utc'].replace('Z','+00:00'))>now),
        process_cap=len(processes)+2<=result['process_cap'],pss_cap=result['borrower_pss_bytes']<=64000000000,
        nice=all(p['nice']>=10 for p in processes),gpu_headroom=int(result['gpu'].split(',')[0])>=8192)
    target=base/'data/v2-store-v1'
    result['destination_bytes']=int(subprocess.check_output(['du','-sb',str(target)],text=True).split()[0]) if target.exists() else 0
    result['dev_curve']=[];steps=[]
    if (out/'train.jsonl').exists():
        with (out/'train.jsonl').open() as f:
            for line in f:
                try:r=json.loads(line)
                except json.JSONDecodeError:continue
                if r['event']=='dev':result['dev_curve'].append(r)
                elif r['event']=='step':
                    if not steps:result['first_step']=r
                    steps.append(r)
                    if len(steps)>20:steps.pop(0)
        result['last_step']=steps[-1] if steps else None
        result['last_20_step_loss_mean']=sum(s['loss'] for s in steps)/len(steps) if steps else None
    files=sorted(out.glob('*.pt'),key=lambda p:p.stat().st_mtime)
    result['checkpoints']=[dict(path=str(p),bytes=p.stat().st_size,mtime=p.stat().st_mtime) for p in files[-4:]]
    if (out/'segments.jsonl').exists():result['segments']=[json.loads(l) for l in (out/'segments.jsonl').read_text().splitlines()]
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
