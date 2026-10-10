"""Reallocated bounded05 advance: original GPU/shared03 regret only.

No new01 or03 timing launch until the separately frozen timing03 executor
and coordinator G drain/admission exist. Original scientific bytes unchanged.
"""
import argparse,fcntl,hashlib,json,shlex,subprocess
from pathlib import Path
J='/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r2';B='/mpac/sdicks02/jobs/clasher/exit-r2-20261010-r1'
ARMS={'R3c':('127x09',5000),'R3d':('127x16',2500),'R3e':('127x13',5000)}
def remote(host,cmd):return subprocess.run(['ssh','-o','ConnectTimeout=10',host,cmd],capture_output=True,text=True,check=True,timeout=30).stdout
def read(host,name):
    if host=='127x01':
        root=Path(__file__).resolve().parents[2]
        if name=='R3-CPU-RELEASE.json':
            raw=(root/'receipts/vacancy-audits/127x01/R3-CPU-RELEASE.json').read_bytes()
            assert hashlib.sha256(raw).hexdigest()=='6569581ba301576d0b9c574173ce1edddfb40d73991a7b240267bc2d9c6ab2d7'
            return json.loads(raw)
        p=root/'receipts/evaluation-snapshots/127x01'/name.replace('/','--')
        if not p.exists():return None
        v=json.loads(p.read_text());assert hashlib.sha256(v['raw'].encode()).hexdigest()==v['sha256'] and json.loads(v['raw'])==v['value']
        return v['value']
    return json.loads(remote(host,'if [ -f '+shlex.quote(J+'/'+name)+' ]; then cat '+shlex.quote(J+'/'+name)+'; else printf null; fi'))
def phase(host,label):
    p=J+'/'+label+'.log.pid'
    return remote(host,'if [ -f '+shlex.quote(p)+' ]; then p=$(cat '+shlex.quote(p)+'); if [ -e /proc/$p ]; then printf active; else printf closed; fi; else printf fresh; fi').strip()
def launch(state,host,label,cmd):
    status=phase(host,label)
    if status!='fresh':state['waiting']=label+' '+status;state['needs_review']=status=='closed';return False
    identity=json.loads(remote(host,'bash '+J+'/metadata/detach.sh '+J+'/'+label+'.log '+cmd));state['actions'].append(dict(host=host,label=label,identity=identity));return True
def env(host,scorer=False):
    root=J+('/scorer-source' if scorer else '/eval-source' if host=='127x01' else '/source')
    return 'env PYTHONPATH='+root+':'+root+'/src:'+J+'/student-source:'+J+'/eval-ops:'+J+'/ops CLASHER_ROOT='+root+' CLASHER_EVAL_RUNTIME_ROOT='+root+' CLASHER_DELAY_NATIVE_DIR='+J+('/scorer-native' if scorer else '/reporting-native')+' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 RAYON_NUM_THREADS=1 XDG_CACHE_HOME='+J+'/cache TORCH_HOME='+J+'/cache/torch TMPDIR='+J+'/tmp '+('CUDA_VISIBLE_DEVICES= ' if host in ('127x01','127x03') else '')+'nice -n '+('19' if host=='127x03' else '10')+' taskset -c '+('39' if host=='127x01' else '58' if host=='127x03' else '126')+' '+B+'/venv/bin/python -B '
def lane(state,lane):
    host='127x01'
    if read(host,('descriptive-results.json' if lane=='descriptive' else 'stage2-results.json')):return True
    for smoke in (True,False):
        if smoke and read(host,'qualification-'+lane+'.json'):continue
        name='k0-'+lane+('-smoke' if smoke else '');done=read(host,name+'/POOL-DONE.json')
        if done:
            launch(state,host,'reduce-'+name+'-attempt1',env(host)+J+'/eval-ops/reduce_games.py --job '+J+' --lane '+lane+(' --smoke' if smoke else ''));return False
        label=name+'-pool-attempt1'
        if phase(host,label)=='fresh':launch(state,host,label,'nice -n 10 taskset -c 39 bash '+J+'/eval-ops/run_pool.sh --lane '+lane+(' --smoke' if smoke else '')+' --cores '+('0 1' if smoke else ' '.join(map(str,range(39)))))
        else:state['waiting']=label+' '+phase(host,label);state['needs_review']=phase(host,label)=='closed'
        return False
def advance(descriptive=False,round2=False):
    state=dict(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),actions=[],fits={})
    for arm,(host,steps) in ARMS.items():
        complete=read(host,'fits/'+arm+'/complete.json');segment=read(host,'fits/'+arm+'/segment.json');ex=read(host,arm+'-exit.json');identity=read(host,arm+'-launch.json');off=read(host,'offline/'+arm+'.json')
        state['fits'][arm]=dict(complete=complete,offline=off)
        if off or not complete or not segment or not ex or not identity:continue
        # A stale void-startup exit is not the current attempt's clean-exit proof.
        if ex['utc']<identity['utc']:continue
        if complete['step']!=steps or complete['stopped'] or segment['status']!='returned' or ex['exit_code']!=0 or ex['reason'] is not None:state['fits'][arm]['needs_review']=True;continue
        launch(state,host,'offline-'+arm+'-attempt1',env(host)+J+'/eval-ops/offline.py --job '+J+' --arm '+arm)
    if descriptive:
        assert read('127x01','R3-CPU-RELEASE.json')['released']
        assert read('127x01','descriptive-results.json')['paired_seeds']==600
        state['descriptive_complete']=True
    if round2:
        if not all(v['offline'] for v in state['fits'].values()):state['round2_waiting']='final EMAs/clean exits/GPU offline';return state
        stage1=read('127x03','stage1-results.json')
        if not stage1:
            if not read('127x03','REGRET-PROPOSALS-STAGING.json'):
                launch(state,'127x03','regret-proposals-staging-attempt2',env('127x03',True)+J+'/eval-ops/stage_proposals.py --job '+J);return state
            if not read('127x03','REGRET-CORE58-RESTART.json'):
                state['round2_waiting']='Reviewed core58/nice19/PSI amendment awaits pushed freeze and fresh admission';return state
            if not read('127x03','regret/POOL-DONE.json'):
                launch(state,'127x03','regret-pool-attempt3',env('127x03',True)+J+'/eval-ops/pool_regret.py --job '+J);return state
            state['round2_waiting']='Shared03 replay manager must seal Stage1 in-process; closed attempts require review';state['needs_review']=phase('127x03','regret-pool-attempt3')=='closed';return state
        if not any(v['survives'] for v in stage1.values()):state['stage2_skipped']='all round2 arms killed at complete Stage1';state['round2_complete']=True;return state
        state['round2_waiting']='Survivors require coordinator G STOP/full drain and separately frozen timing03 admission; no further01 launches'
        state['stage2_survivors']=[a for a,v in stage1.items() if v['survives']]

    return state
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--descriptive',action='store_true');p.add_argument('--round2',action='store_true');a=p.parse_args();path=Path(a.output)
    lock=Path(str(path)+'.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    state=advance(a.descriptive,a.round2);path.write_text(json.dumps(state,indent=2)+'\n');print(json.dumps(state,indent=2))
