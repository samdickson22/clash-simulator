"""Bounded04 metadata advance; no reporting games on this granted slot."""
import argparse,json,shlex,hashlib
from pathlib import Path
from stage import read,running,detach,remote,J,B

def advance():
    host='127x04';r=dict(host=host,actions=[])
    for arm,h in (('R3a','127x09'),('R3b','127x16')):
        if read(h,J+'/offline/'+arm+'.json') is None:r['waiting']='fit-host final-EMA GPU offline';return r
    if read(host,J+'/stage1-results.json'):r['complete']=True;return r
    stage=read(host,J+'/REGRET04-STAGING.json')
    if not stage or not stage['passed']:r['waiting']='explicit04 authority refreshed and guarded --offline staging';return r
    admission=read(host,J+'/REGRET04-ADMITTED.json')
    if not admission or any(hashlib.sha256(Path(name).read_bytes()).hexdigest()!=want for name,want in admission['a19_progress_sha256'].items()):r['waiting']='A19 authority changed; review before re-admission';return r
    if remote(host,'if [ -e '+J+'/REGRET04.STOP ]; then printf stopped; else printf clear; fi').strip()!='clear':r['waiting']='owned04 stop; inspect vacancy before any re-admission';return r
    if read(host,J+'/regret/POOL-DONE.json'):
        command='env PYTHONPATH='+J+'/source:'+J+'/source/src:'+J+'/eval-ops OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 nice -n 19 taskset -c 19 '+B+'/venv/bin/python -B '+J+'/eval-ops/reduce.py --job '+J+' --mode regret'
        r['actions'].append(dict(phase='stage1-reduce',output=remote(host,command)));r['complete']=True;return r
    if running(host,J+'/regret04-pool-attempt1.log'):r['waiting']='regret04 pool active';r['progress']=read(host,J+'/regret/progress.json');return r
    if read(host,J+'/regret/progress.json'):r['needs_review']='prior04 pool stopped; inspect and version entire game retries, retain all meters';return r
    command='env R3_REGRET04=1 PYTHONPATH='+J+'/source:'+J+'/source/src:'+J+'/eval-ops CLASHER_ROOT='+J+'/source CLASHER_EVAL_RUNTIME_ROOT='+J+'/source CUDA_VISIBLE_DEVICES=\"\" OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 XDG_CACHE_HOME='+J+'/cache TMPDIR='+J+'/tmp nice -n 19 taskset -c 19 '+B+'/venv/bin/python -B '+J+'/eval-ops/pool_regret04.py --job '+J
    r['actions'].append(dict(phase='regret04',identity=detach(host,'regret04-pool-attempt1',command)));return r
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();r=advance();Path(a.output).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
