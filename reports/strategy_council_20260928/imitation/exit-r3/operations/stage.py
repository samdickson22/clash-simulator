"""One bounded metadata-driven advance; no duplicate fits, games or host claims."""
import argparse,json,os,shlex,subprocess,time
from pathlib import Path
J='/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r1';B='/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1';ARMS={'R3a':'127x09','R3b':'127x16'}

def remote(host,command):return subprocess.run(['ssh','-o','ConnectTimeout=10',host,command],check=True,capture_output=True,text=True).stdout

def read(host,path):
    value=remote(host,'if [ -f '+shlex.quote(path)+' ]; then cat '+shlex.quote(path)+'; else printf null; fi')
    return json.loads(value)

def running(host,path):
    return remote(host,'if [ -f '+shlex.quote(path+'.pid')+' ]; then p=$(cat '+shlex.quote(path+'.pid')+'); if [ -e /proc/$p ]; then printf yes; fi; fi').strip()=='yes'

def detach(host,label,command):
    assert not running(host,J+'/'+label+'.log'),'duplicate active phase'
    assert remote(host,'test ! -e '+shlex.quote(J+'/'+label+'.log.pid')+' && printf clear').strip()=='clear','attempt name already used; inspect and version a retry'
    return remote(host,'bash '+shlex.quote(J+'/pilot/detach.sh')+' '+shlex.quote(J+'/'+label+'.log')+' '+command)

def pool_state(host,mode):
    stage={'regret':'regret','smoke':'stage3-sdefault-smoke','reporting':'stage3-sdefault'}[mode]
    return read(host,J+'/'+stage+'/POOL-DONE.json'),read(host,J+'/'+stage+'/progress.json')

def advance(cpu_host=None):
    state={'utc':subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),'arms':{},'actions':[]}
    for arm,host in ARMS.items():
        complete=read(host,J+'/fits/'+arm+'/complete.json');exit=read(host,J+'/'+arm+'-exit.json');segment=read(host,J+'/fits/'+arm+'/segment.json');offline=read(host,J+'/offline/'+arm+'.json')
        state['arms'][arm]=dict(fit=complete,exit=exit,offline=offline)
        if complete is None or exit is None or segment is None:continue
        if complete['step']!=2500 or complete['stopped'] or exit['exit_code'] or exit['reason'] or segment['status']!='returned':
            state['arms'][arm]['needs_review']='fit pause/failure; preserve exact checkpoint and inspect reason';continue
        if offline is None and not running(host,J+'/offline-'+arm+'-attempt1.log'):
            command='env PYTHONPATH='+J+'/source:'+J+'/source/src:'+J+'/eval-ops:'+J+'/ops PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 XDG_CACHE_HOME='+J+'/cache TMPDIR='+J+'/tmp nice -n 10 taskset -c 126 '+B+'/venv/bin/python -B '+J+'/eval-ops/offline.py --job '+J+' --arm '+arm
            state['actions'].append(dict(phase='offline',arm=arm,identity=detach(host,'offline-'+arm+'-attempt1',command)))
    if not all(s['offline'] is not None for s in state['arms'].values()):state['waiting']='final fit/clean exit/GPU offline';return state
    if cpu_host is None:state['waiting']='explicit K2/X CPU release and own CPU-RELEASE-ADMITTED.json';return state
    assert cpu_host in ('127x01','127x03')
    receipt=read(cpu_host,J+'/CPU-RELEASE-ADMITTED.json')
    assert receipt and receipt['explicit_release'] and receipt['host']==cpu_host,'do not infer release from ETA or markers alone'
    core=59 if cpu_host=='127x03' else 39
    # Home artifacts must have been staged and SHA checked by the agent after release.
    assert read(cpu_host,J+'/CPU-STAGING.json')['passed']
    verdict=remote(cpu_host,'env PYTHONPATH='+J+'/source:'+J+'/source/src:'+J+'/eval-ops nice -n 10 taskset -c '+str(core)+' '+B+'/venv/bin/python -B -c '+shlex.quote('from pathlib import Path; from admission import allowed; print(allowed(Path("'+J+'")))')).strip()
    if verdict!='True':state['waiting']='live CPU admission conflict/resource floor';return state
    reducer='env PYTHONPATH='+J+'/source:'+J+'/source/src:'+J+'/eval-ops OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 nice -n 10 taskset -c '+str(core)+' '+B+'/venv/bin/python -B '+J+'/eval-ops/reduce.py --job '+J
    for mode in ('regret','smoke','reporting'):
        if mode=='regret' and read(cpu_host,J+'/stage1-results.json'):continue
        if mode=='smoke':
            stage1=read(cpu_host,J+'/stage1-results.json');assert stage1
            if not any(v['survives'] for v in stage1.values()):state['complete']=True;state['stage2_skipped']='both arms killed at stage1';return state
            if read(cpu_host,J+'/wrapper-qualification.json'):continue
        if mode=='reporting' and read(cpu_host,J+'/stage2-results.json'):state['complete']=True;return state
        done,progress=pool_state(cpu_host,mode)
        if done:
            reduction={'regret':'regret','smoke':'qualify','reporting':'reporting'}[mode]
            state['actions'].append(dict(phase='reduce-'+mode,output=remote(cpu_host,reducer+' --mode '+reduction)));continue
        if running(cpu_host,J+'/'+mode+'-pool-attempt1.log'):
            state['waiting']=mode+' pool active';state['pool_progress']=progress;return state
        if progress is not None:
            state['needs_review']=mode+' prior attempt closed without POOL-DONE; inspect failures and version a complete-block retry';return state
        cores=list(range(8)) if mode=='regret' else [0,1] if mode=='smoke' else list(range(min(core,46)))
        command='nice -n 10 taskset -c '+str(core)+' bash '+J+'/eval-ops/run_pool.sh --mode '+mode+' --cores '+' '.join(map(str,cores))
        state['actions'].append(dict(phase=mode,identity=detach(cpu_host,mode+'-pool-attempt1',command)));state['waiting']=mode+' pool launched';return state
    state['complete']=True;return state

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--cpu-host',choices=('127x01','127x03'));a=p.parse_args();state=advance(a.cpu_host);Path(a.output).write_text(json.dumps(state,indent=2)+'\n');print(json.dumps(state,indent=2))
