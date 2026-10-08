"""Detached single-process CUDA trainer, train split only, resumable last.pt."""
import argparse
import contextlib
import json
from pathlib import Path
import random
import time

import cv2
import torch
from clasher.vision.l1_v4 import PerceptionV4
from data_v4 import Windows, batch, loss_fn, sha


def save(path,payload):
    temporary=path.with_suffix('.tmp');torch.save(payload,temporary);temporary.replace(path)


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--split',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--steps',type=int,default=400);p.add_argument('--epochs',type=int,default=24)
    p.add_argument('--max-matches',type=int,default=0);p.add_argument('--windows-per-match',type=int,default=32)
    p.add_argument('--resume',action='store_true');p.add_argument('--device',default='cuda');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=a.resume);torch.set_num_threads(1);cv2.setNumThreads(1)
    random.seed(6108);torch.manual_seed(6108)
    if a.device=='cuda':
        free,total=torch.cuda.mem_get_info()
        if free<16*1024**3:raise RuntimeError('Need 16GiB free before training')
        torch.cuda.set_per_process_memory_fraction(.65);torch.cuda.reset_peak_memory_stats()
    data=Windows(a.source,a.split,a.output/'data',max_matches=a.max_matches,windows_per_match=a.windows_per_match)
    model=PerceptionV4(len(data.cards),len(data.bodies)).to(a.device)
    opt=torch.optim.AdamW(model.parameters(),lr=.0003,weight_decay=.0001)
    first=0
    if a.resume:
        state=torch.load(a.output/'last.pt',map_location=a.device,weights_only=True)
        if state['cards']!=data.cards or state['bodies']!=data.bodies:raise ValueError('Changed vocabulary')
        model.load_state_dict(state['model']);opt.load_state_dict(state['optimizer']);first=state['step']
        random.setstate(state['random']);data.rng.setstate(state['data_random']);torch.set_rng_state(state['torch_random'].cpu())
        if a.device=='cuda':torch.cuda.set_rng_state_all([x.cpu() for x in state['cuda_random']])
    sources=[Path(__file__),Path(__file__).with_name('data_v4.py')]
    import clasher.vision.l1_v4 as module
    sources.append(Path(module.__file__))
    manifest=dict(seed=6108,device=a.device,precision='bf16' if a.device=='cuda' else 'fp32',compile=False,
                  parameters=model.parameter_counts(),training_matches=len(data.receipts),windows=len(data),cards=data.cards,bodies=data.bodies,
                  source_hashes={str(x):sha(x) for x in sources},split_sha256=sha(a.split),heldout_opened=False,
                  epochs=a.epochs,steps=a.steps,max_matches=a.max_matches,windows_per_match=a.windows_per_match)
    mpath=a.output/'manifest.json'
    if a.resume:
        old=json.loads(mpath.read_text())
        if old!=manifest:raise ValueError('Resume configuration/source changed; use a new run')
    else:mpath.write_text(json.dumps(manifest,indent=2)+'\n')
    if first==a.epochs*a.steps and (a.output/'complete.json').exists():
        print('Already complete; checkpoint and manifest verified',flush=True);return
    sync=lambda:torch.cuda.synchronize() if a.device=='cuda' else None
    measured=[];load_times=[];started=time.perf_counter();last_parts=None
    for step in range(first,a.epochs*a.steps):
        load=time.perf_counter();sample=data.sample(random.randrange(len(data)));b=batch(sample,a.device);load_times.append(time.perf_counter()-load)
        sync();begin=time.perf_counter();opt.zero_grad(set_to_none=True)
        ctx=torch.autocast('cuda',dtype=torch.bfloat16) if a.device=='cuda' else contextlib.nullcontext()
        with ctx:
            out=model(b['arena'],b['hud'],b['ages'],b['valid'],b['births']);loss,parts=loss_fn(out,b['target'])
        if not torch.isfinite(loss):raise ValueError('Nonfinite loss')
        loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),10);opt.step();sync()
        elapsed=time.perf_counter()-begin;measured.append(elapsed);last_parts={k:float(v.detach()) for k,v in parts.items()}
        row=dict(step=step+1,loss=float(loss.detach()),parts=last_parts,step_seconds=elapsed,load_seconds=load_times[-1])
        with (a.output/'training.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        if (step+1)%8==0 or step+1==a.epochs*a.steps:
            save(a.output/'last.pt',dict(model=model.state_dict(),optimizer=opt.state_dict(),step=step+1,cards=data.cards,bodies=data.bodies,
                 random=random.getstate(),data_random=data.rng.getstate(),torch_random=torch.get_rng_state(),
                 cuda_random=torch.cuda.get_rng_state_all() if a.device=='cuda' else []))
            print(json.dumps(row),flush=True)
        if (step+1)%a.steps==0:save(a.output/f'epoch-{(step+1)//a.steps}.pt',dict(model=model.state_dict(),cards=data.cards,bodies=data.bodies,step=step+1))
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
