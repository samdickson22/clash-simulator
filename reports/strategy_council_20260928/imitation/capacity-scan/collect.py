"""Small receipt/curve collector, run on an arm host; never emits weights."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--work',required=True)
    p.add_argument('--width',type=int,required=True)
    a=p.parse_args();w=Path(a.work);out=w/'runs'/f'width{a.width}'
    labels=w/'ops/active-labels.json'
    label=json.loads(labels.read_text()).get(str(a.width),f'width{a.width}-v1') if labels.exists() else f'width{a.width}-v1'
    result=dict(width=a.width,work=str(w),curve=[],quarters=None)
    for name,path in [('quarter',out/'quarter.json'),('decision',out/'kill-decision.json'),
                      ('scan_exit',out/'scan-exit.json'),('complete',out/'complete.json'),
                      ('guard_exit',w/f'{label}-exit.json'),
                      ('store',w/'ops/store-verified.json')]:
        if path.exists():
            r=json.loads(path.read_text())
            if name=='store':
                r={k:v for k,v in r.items() if k!='files'}
                r['receipt_sha256']=sha(path)
            result[name]=r
    segments=out/'scan-segments.jsonl'
    result['segments']=[json.loads(x) for x in segments.read_text().splitlines()] if segments.exists() else []
    result['guard_history']=[json.loads(x.read_text()) for x in sorted(w.glob(f'width{a.width}-*-exit.json'))]
    result['gpu_hours']=sum(x['wall_seconds'] for x in result['segments'])/3600
    log=out/'train.jsonl';last=None;starts=[]
    if log.exists():
        result['train_log_sha256']=sha(log)
        for line in log.open():
            r=json.loads(line)
            if r.get('event')=='start':starts.append(r)
            if r.get('event')=='step':last=r
            elif r.get('event')=='dev':
                assert last and last['step']==r['step']
                result['curve'].append(dict(rows=last['rows'],step=r['step'],ema_joint_nll=r['ema_joint_nll']))
        result['latest_step']=last
        result['start_pins']=[dict(parameters=x['parameters'],hashes=x['hashes'],args=x['args']) for x in starts]
    if 'quarter' in result:
        q=result['quarter'];result['curve'].append({k:q[k] for k in ('rows','step','ema_joint_nll')})
    result['curve']=sorted(result['curve'],key=lambda x:x['rows'])
    candidates=list(out.glob('quarter-step-*.pt'))
    if result.get('complete') and (out/'checkpoints.json').exists():
        c=json.loads((out/'checkpoints.json').read_text());candidates.append(out/c['last'])
    result['checkpoints']=[dict(path=str(x),sha256=sha(x),bytes=x.stat().st_size) for x in sorted(set(candidates))]
    if result.get('decision',{}).get('killed'):
        result['status']='killed_dev_gain'
    elif result.get('complete') and not result['complete'].get('stopped_by_signal'):
        result['status']='schedule_complete'
    elif a.width==192 and result.get('scan_exit',{}).get('status')=='control_replay_complete':
        result['status']='control_replay_complete'
    elif result.get('guard_exit'):
        result['status']='resource_censored' if result['guard_exit'].get('stop_reason') else 'technical_failure'
    else:
        result['status']='running'
    def finite(value):
        if isinstance(value,float) and not math.isfinite(value):return None
        if isinstance(value,dict):return {k:finite(v) for k,v in value.items()}
        if isinstance(value,list):return [finite(v) for v in value]
        return value
    print(json.dumps(finite(result),indent=2,allow_nan=False))


if __name__=='__main__':main()
