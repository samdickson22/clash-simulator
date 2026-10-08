"""Detached single-process CUDA trainer, train split only, resumable last.pt."""
import argparse
import contextlib
import json
from pathlib import Path
import random
import time
import signal
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from collections import deque

import cv2
import torch
from clasher.vision.l1_v4 import PerceptionV4
from data_v4 import Windows, batch, loss_fn, sha


def save(path,payload):
    temporary=path.with_suffix('.tmp');torch.save(payload,temporary);temporary.replace(path)


def resume_history(path,last_step):
    """Keep an interrupted log intact, then continue at the saved update boundary."""
    raw=path.read_bytes();lines=raw.splitlines(keepends=True)
    rows=[];partial=False
    for i,line in enumerate(lines):
        try:rows.append(json.loads(line))
        except json.JSONDecodeError:
            if i!=len(lines)-1 or line.endswith(b'\n'):raise ValueError('Malformed interior training log')
            partial=True
    if type(last_step) is not int or last_step<0 or last_step>len(rows):
        raise ValueError('Checkpoint/log boundary differs')
    if [r['step'] for r in rows]!=list(range(1,len(rows)+1)):
        raise ValueError('Training history is not a contiguous unique prefix')
    if len(rows)==last_step and not partial:return None
    suffix=uuid.uuid4().hex
    backup=path.with_name('training-pre-resume-'+suffix+'.jsonl')
    with backup.open('xb') as f:f.write(raw)
    temporary=path.with_name('training-resume-'+suffix+'.tmp')
    with temporary.open('xb') as f:f.write(b''.join(lines[:last_step]))
    temporary.replace(path)
    return backup


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--split',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--steps',type=int,default=400);p.add_argument('--epochs',type=int,default=24)
    p.add_argument('--max-matches',type=int,default=0);p.add_argument('--windows-per-match',type=int,default=32)
    p.add_argument('--pixel-cache',type=Path)
    p.add_argument('--engineering-union',type=Path,help='Bounded preformal union benchmark only')
    p.add_argument('--formal-union',type=Path,help='Full authenticated train/validation cache runtime')
    p.add_argument('--phase-state',type=Path);p.add_argument('--phase-exit',type=Path)
    p.add_argument('--loader-workers',type=int,default=6)
    p.add_argument('--resume',action='store_true');p.add_argument('--device',default='cuda');a=p.parse_args()
    if a.engineering_union and (a.pixel_cache or a.epochs!=1 or not 1<=a.steps<=128 or a.max_matches):
        raise ValueError('Engineering union is restricted to full-snapshot 1x1..128 steps')
    if a.formal_union and (a.engineering_union or a.pixel_cache or a.epochs!=24 or a.steps!=400
            or a.max_matches or a.windows_per_match!=32 or a.loader_workers!=6 or a.device!='cuda'
            or a.phase_state is None or a.phase_exit is None):
        raise ValueError('Formal union requires registered full T7 configuration and producer receipts')
    union=None
    if a.formal_union:
        from formal_union_v4 import open_formal_union, snapshot_indices
        union=open_formal_union(a.source,a.split,a.phase_state,a.phase_exit,
                                a.output.parent/'admission.json',a.formal_union)
    a.output.mkdir(parents=True,exist_ok=a.resume);torch.set_num_threads(1);cv2.setNumThreads(1)
    random.seed(6108);torch.manual_seed(6108)
    if a.device=='cuda':
        free,total=torch.cuda.mem_get_info()
        if free<16*1024**3:raise RuntimeError('Need 16GiB free before training')
        torch.cuda.set_per_process_memory_fraction(.65);torch.cuda.reset_peak_memory_stats()
    if a.engineering_union:
        from union_training_v4 import open_union, parity
        union=open_union(a.source,a.split,a.engineering_union)
    data=Windows(a.source,a.split,a.output/'data',max_matches=a.max_matches,windows_per_match=a.windows_per_match,pixel_cache=a.pixel_cache,pixel_reader=union)
    if a.formal_union:snapshot_indices(union,a.output/'cache-indices')
    if union and not a.resume:
        from union_training_v4 import parity
        (a.output/'union-parity.json').write_text(json.dumps(parity(data,union),indent=2)+'\n')
    model=PerceptionV4(len(data.cards),len(data.bodies)).to(a.device)
    opt=torch.optim.AdamW(model.parameters(),lr=.0003,weight_decay=.0001)
    first=0
    if a.resume:
        state=torch.load(a.output/'last.pt',map_location=a.device,weights_only=True)
        if state['cards']!=data.cards or state['bodies']!=data.bodies:raise ValueError('Changed vocabulary')
        model.load_state_dict(state['model']);opt.load_state_dict(state['optimizer']);first=state['step']
        random.setstate(state['random']);data.rng.setstate(state['data_random']);torch.set_rng_state(state['torch_random'].cpu())
        if a.device=='cuda':torch.cuda.set_rng_state_all([x.cpu() for x in state['cuda_random']])
    sources=[Path(__file__),*[Path(__file__).with_name(n) for n in ('data_v4.py','labels_v4.py','pixel_cache.py')]]
    import clasher.vision.l1_v4 as module
    sources.append(Path(module.__file__))
    from data_v4 import ROOT,CALIBRATION
    sources.extend([ROOT/'gamedata.json',CALIBRATION,Path(__file__).parents[1]/'body-catalog.json'])
    if union:sources.extend(Path(__file__).with_name(n) for n in ('union_training_v4.py','cache_union_v4.py','cache_transport_v4.py','cache_budget.py','formal_guard.py','reference_sample.py'))
    if a.formal_union:sources.append(Path(__file__).with_name('formal_union_v4.py'))
    has_cache=bool(a.pixel_cache or union)
    pins={ep:h for shard in union.provenance for ep,h in shard['index_sha256'].items()} if union else {}
    manifest=dict(seed=6108,device=a.device,precision='bf16' if a.device=='cuda' else 'fp32',compile=False,
                  parameters=model.parameter_counts(),training_matches=len(data.receipts),windows=len(data),cards=data.cards,bodies=data.bodies,
                  source_hashes={str(x):sha(x) for x in sources},split_sha256=sha(a.split),heldout_opened=False,
                  epochs=a.epochs,steps=a.steps,max_matches=a.max_matches,windows_per_match=a.windows_per_match,
                  pixel_cache=str(a.output/'cache-indices') if a.formal_union else (str(a.pixel_cache) if a.pixel_cache else None),loader_workers=a.loader_workers if has_cache else 0,
                  cache_index_sha256={r['episode']:pins[r['episode']] for r in data.receipts} if union else ({r['episode']:sha(a.pixel_cache/r['episode']/'index.json') for r in data.receipts} if a.pixel_cache else {}))
    if union:manifest.update(engineering_only=not bool(a.formal_union),cache_union_provenance=union.provenance)
    if a.formal_union:manifest.update(formal_cache_union=True,formal_admission_sha256=sha(a.output.parent/'admission.json'))
    mpath=a.output/'manifest.json'
    if a.resume:
        old=json.loads(mpath.read_text())
        if old!=manifest:raise ValueError('Resume configuration/source changed; use a new run')
        resume_history(a.output/'training.jsonl',first)
    else:
        mpath.write_text(json.dumps(manifest,indent=2)+'\n')
        snapshot=a.output/'source';snapshot.mkdir()
        for source in sources:shutil.copy2(source,snapshot/source.name)
    if first==a.epochs*a.steps and (a.output/'complete.json').exists():
        print('Already complete; checkpoint and manifest verified',flush=True);return
    sync=lambda:torch.cuda.synchronize() if a.device=='cuda' else None
    measured=[];load_times=[];started=time.perf_counter();last_parts=None
    stopping=False
    def stop(signum,frame):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGUSR1,stop)
    def next_sample(index,plan):
        begin=time.perf_counter();sample=data.sample(index,plan)
        return sample,time.perf_counter()-begin
    # Plans are drawn serially in the original RNG order. Image/target work
    # may finish out of order, but batches and checkpoint RNGs stay ordered.
    if not 1<=a.loader_workers<=8:raise ValueError('Loader threads must be 1..8')
    pool=ThreadPoolExecutor(max_workers=a.loader_workers) if has_cache else None
    pending=deque();submitted=first
    def enqueue():
        nonlocal submitted
        index=random.randrange(len(data));plan=data.plan(index)
        states=(random.getstate(),data.rng.getstate())
        pending.append((pool.submit(next_sample,index,plan),*states));submitted+=1
    if pool:
        for _ in range(min(a.loader_workers*2,a.epochs*a.steps-first)):enqueue()
    for step in range(first,a.epochs*a.steps):
        load=time.perf_counter()
        if pool:
            future,sample_random,sample_data_random=pending.popleft();sample,sample_seconds=future.result()
            if submitted<a.epochs*a.steps and not stopping:enqueue()
        else:
            index=random.randrange(len(data));plan=data.plan(index)
            sample,sample_seconds=next_sample(index,plan);sample_random=random.getstate();sample_data_random=data.rng.getstate()
        b=batch(sample,a.device);load_times.append(time.perf_counter()-load)
        sync();begin=time.perf_counter();opt.zero_grad(set_to_none=True)
        ctx=torch.autocast('cuda',dtype=torch.bfloat16) if a.device=='cuda' else contextlib.nullcontext()
        with ctx:
            out=model(b['arena'],b['hud'],b['ages'],b['valid'],b['births']);loss,parts=loss_fn(out,b['target'])
        if not torch.isfinite(loss):raise ValueError('Nonfinite loss')
        loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),10);opt.step();sync()
        elapsed=time.perf_counter()-begin;measured.append(elapsed);last_parts={k:float(v.detach()) for k,v in parts.items()}
        row=dict(step=step+1,loss=float(loss.detach()),parts=last_parts,step_seconds=elapsed,load_seconds=load_times[-1],sample_seconds=sample_seconds)
        with (a.output/'training.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        if (step+1)%8==0 or step+1==a.epochs*a.steps or stopping:
            save(a.output/'last.pt',dict(model=model.state_dict(),optimizer=opt.state_dict(),step=step+1,cards=data.cards,bodies=data.bodies,
                 random=sample_random,data_random=sample_data_random,torch_random=torch.get_rng_state(),
                 cuda_random=torch.cuda.get_rng_state_all() if a.device=='cuda' else []))
            print(json.dumps(row),flush=True)
        if (step+1)%a.steps==0:save(a.output/f'epoch-{(step+1)//a.steps}.pt',dict(model=model.state_dict(),cards=data.cards,bodies=data.bodies,step=step+1))
        if stopping:
            if pool:pool.shutdown(wait=True)
            (a.output/'checkpoint-stop.json').write_text(json.dumps(dict(step=step+1,reason='signal',heldout_opened=False))+'\n')
            return
    if pool:pool.shutdown(wait=True)
    elapsed=time.perf_counter()-started
    if not measured:
        # A crash after the final checkpoint but before benchmarking must remain
        # resumable. Recover timing from unique persisted steps, not empty lists.
        records={r['step']:r for r in (json.loads(line) for line in (a.output/'training.jsonl').read_text().splitlines())}
        rows=[records[k] for k in sorted(records)]
        measured=[r['step_seconds'] for r in rows];load_times=[r['load_seconds'] for r in rows]
        elapsed=sum(measured)+sum(load_times);last_parts=rows[-1]['parts']
        b=batch(data.sample(0),a.device)
    # Separate warm-cache runtime benchmark, including one current frame encode + temporal head.
    model.eval();timings=[]
    with torch.inference_mode():
        for i in range(24):
            sync();start=time.perf_counter()
            with torch.autocast('cuda',dtype=torch.bfloat16) if a.device=='cuda' else contextlib.nullcontext():
                frame=model.encode(b['arena'][:,-1],b['hud'])
                cache=frame['features'][:,None].expand(-1,16,-1,-1,-1).contiguous()
                model.temporal(cache,b['ages'],b['valid'],b['births'])
            sync()
            if i>=4:timings.append((time.perf_counter()-start)*1000)
    metrics=dict(manifest=manifest,steps_completed=a.epochs*a.steps,steps_this_process=len(measured),wall_seconds=elapsed,
                 steps_per_second=len(measured)/sum(measured),encoded_frames_per_second=16*len(measured)/sum(measured),
                 end_to_end_windows_per_second=len(measured)/elapsed,mean_decode_seconds=sum(load_times)/max(1,len(load_times)),
                 runtime_cuda_p50_ms=float(torch.tensor(timings).quantile(.5)),runtime_cuda_p95_ms=float(torch.tensor(timings).quantile(.95)),
                 peak_allocated_mib=torch.cuda.max_memory_allocated()/2**20 if a.device=='cuda' else None,
                 peak_reserved_mib=torch.cuda.max_memory_reserved()/2**20 if a.device=='cuda' else None,
                 final_loss_parts=last_parts,checkpoint_sha256=sha(a.output/'last.pt'),heldout_opened=False,
                 caveat='GPU shakedown, not a Mac gate; runtime uses repeated cached feature shapes, no decode/fusion/emulator')
    (a.output/'complete.json').write_text(json.dumps(metrics,indent=2)+'\n');print(json.dumps(metrics),flush=True)

if __name__=='__main__':main()
