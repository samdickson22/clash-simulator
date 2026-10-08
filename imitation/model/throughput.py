"""Bounded T4 numerical and throughput experiments; train/dev only.

No model selection or heldout scoring. Every benchmark uses the same initial
weights, seed, effective batch, objective and optimizer; artifacts are separate
from training checkpoints. Dropout is disabled ONLY for the equivalence test.
"""
import argparse
from contextlib import nullcontext
from dataclasses import replace
import gc
import importlib.util
import json
from pathlib import Path
import time
import sys
import numpy as np
import torch
from .batching import build_batch, batch_loader
from .store import PackedStore, collate, epoch_indices, sha256
from .network import ModelConfig, SetPolicy
from .train import optimizer_step, update_ema
from .evaluate import metric_rows, summarize
from .runner import transfer, joint_nll_rows


def compare_nested(a,b,tolerance):
    if isinstance(a,dict):
        assert a.keys()==b.keys()
        for k in a: compare_nested(a[k],b[k],tolerance)
    elif isinstance(a,list):
        assert len(a)==len(b)
        for x,y in zip(a,b):compare_nested(x,y,tolerance)
    elif isinstance(a,(float,int)):
        np.testing.assert_allclose(a,b,atol=tolerance,rtol=tolerance)
    else: assert a==b


def save(path, data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'receipt':str(path),**data}),flush=True)


def new_model(store, dropout=.1):
    torch.manual_seed(2903)
    c=ModelConfig(descriptors=store.assets['descriptors'].shape[1],dropout=dropout)
    return SetPolicy(c,torch.tensor(store.assets['descriptors']),torch.tensor(store.assets['tiles']),
                     torch.tensor(store.assets['costs'])).cuda()


def optimizer(m):
    return torch.optim.AdamW(m.parameters(),lr=3e-4,weight_decay=.05)


def weighted(y,store):
    return {**y,'weight':y['weight'].float()*torch.where(y['action']==2304,4*store.wait_keep_probability,1.)}


def qualify(args, store):
    out=Path(args.output); out.mkdir(parents=True,exist_ok=False)
    dev=PackedStore(Path(args.store).parent/'dev','dev',args.assets)
    dev.verify_qualification(json.loads(Path(args.qualification).read_text()))
    # Exact scalar/reference adapter check, including the maximum-entity row.
    ix=np.unique(np.append(np.linspace(0,len(dev)-1,511,dtype=np.int64),dev.arrays['entity_counts'].argmax()))
    b,y=build_batch(dev,ix); old,oy=collate([dev[int(i)] for i in ix])
    for k in b: torch.testing.assert_close(b[k],old[k],rtol=0,atol=0)
    for k in y: torch.testing.assert_close(y[k],oy[k],rtol=0,atol=0,check_dtype=False)
    save(out/'adapter.json',{'passed':True,'rows':len(ix),'equality':'bit-exact features and labels','max_entities':int(dev.arrays['entity_counts'][ix].max())})
    indices=epoch_indices(store,0,2903,.02)[:8192]
    indices=indices[np.argsort(store.arrays['entity_counts'][indices],kind='stable')]
    b,y=build_batch(store,indices); y=weighted(y,store)
    tested=[]
    for micro in (1024,2048,3072,4096,5120,6144,7168,8192):
        m=new_model(store); opt=optimizer(m)
        torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()
        try:
            start=time.perf_counter(); result=optimizer_step(m,opt,b,y,micro,torch.device('cuda')); torch.cuda.synchronize()
            seconds=time.perf_counter()-start
            total=torch.cuda.get_device_properties(0).total_memory
            peak=torch.cuda.max_memory_reserved()
            item={'microbatch':micro,'rows_per_second_step':len(indices)/seconds,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
                  'peak_reserved_bytes':peak,'total_bytes':total,'headroom_bytes':total-peak,'loss':result['loss'],'fits':total-peak>=8*2**30}
        except torch.cuda.OutOfMemoryError:
            item={'microbatch':micro,'fits':False,'oom':True}
        tested.append(item);save(out/'memory-sweep.json',{'candidates':tested})
        del m,opt;gc.collect();torch.cuda.empty_cache()
        if item.get('oom'): break
    fitted=[v['microbatch'] for v in tested if v['fits']]
    if not fitted: raise RuntimeError('no candidate fits >=8GiB headroom')
    chosen=max(fitted)
    stress_ix=indices.copy();stress_ix[-1]=store.arrays['entity_counts'].argmax()
    stress_b,stress_y=build_batch(store,stress_ix);stress_y=weighted(stress_y,store)
    stress=[]
    for candidate in sorted(fitted,reverse=True):
        m=new_model(store);opt=optimizer(m);torch.cuda.reset_peak_memory_stats()
        try:
            optimizer_step(m,opt,stress_b,stress_y,candidate,torch.device('cuda'))
            peak=torch.cuda.max_memory_reserved();total=torch.cuda.get_device_properties(0).total_memory
            item={'microbatch':candidate,'max_tokens':stress_b['ids'].shape[1]+1,'peak_reserved_bytes':peak,'headroom_bytes':total-peak,'fits':total-peak>=8*2**30}
        except torch.cuda.OutOfMemoryError:
            item={'microbatch':candidate,'fits':False,'oom':True}
        stress.append(item);del m,opt;gc.collect();torch.cuda.empty_cache()
        if item['fits']:chosen=candidate;break
    else: raise RuntimeError('no candidate fits long-row stress')
    save(out/'long-row-memory.json',{'candidates':stress,'microbatch':chosen})
    # Numerical tolerance is fixed before examining errors. Compare updates,
    # not only large unchanged parameters: relative L2 <=5%, parameter max <=2lr.
    # BF16 reductions may reverse tiny near-zero gradients under Adam's sign.
    spec=importlib.util.spec_from_file_location('imitation.model._reference_network',Path(args.reference)/'imitation/model/network.py')
    reference_network=importlib.util.module_from_spec(spec);sys.modules[spec.name]=reference_network;spec.loader.exec_module(reference_network)
    spec=importlib.util.spec_from_file_location('imitation.model._reference_train',Path(args.reference)/'imitation/model/train.py')
    reference_train=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference_train)
    models=[];losses=[];grads=[]
    initial=None
    for micro in (64,chosen):
        m=new_model(store,dropout=0.)
        step_fn=optimizer_step
        if micro==64:
            c=reference_network.ModelConfig(descriptors=store.assets['descriptors'].shape[1],dropout=0.)
            old_model=reference_network.SetPolicy(c,torch.tensor(store.assets['descriptors']),torch.tensor(store.assets['tiles']),torch.tensor(store.assets['costs'])).cuda()
            old_model.load_state_dict(m.state_dict());del m;m=old_model
            step_fn=reference_train.optimizer_step
        if initial is None: initial=torch.cat([p.detach().flatten().cpu() for p in m.parameters()])
        opt=optimizer(m)
        result=step_fn(m,opt,b,y,micro,torch.device('cuda'))
        models.append(torch.cat([p.detach().flatten().cpu() for p in m.parameters()]))
        grads.append(torch.cat([p.grad.detach().flatten().cpu() for p in m.parameters()]))
        losses.append(result['loss'])
        del m,opt;gc.collect();torch.cuda.empty_cache()
    delta=models[0]-models[1]; upd=models[0]-initial
    rel=float(delta.norm()/upd.norm().clamp_min(1e-30))
    grel=float((grads[0]-grads[1]).norm()/grads[0].norm().clamp_min(1e-30))
    equivalence={'passed':bool(rel<=.05 and grel<=.02 and float(delta.abs().max())<=6.01e-4),
        'rows':len(indices),'microbatches':[64,chosen],'dropout':0.,'training_dropout_unchanged':.1,
        'tolerance':{'relative_l2_parameter_update':.05,'relative_l2_clipped_gradient':.02,'max_parameter_absolute':6.01e-4},
        'relative_l2_parameter_update':rel,'relative_l2_clipped_gradient':grel,
        'max_parameter_absolute':float(delta.abs().max()),'p99_parameter_absolute':float(torch.quantile(delta.abs(),.99)),
        'losses':losses,'weights_same_seed':2903,'reference_micro64_uses_original_network_and_optimizer':True}
    save(out/'optimizer-equivalence.json',equivalence)
    # The paired benchmark uses3072 to fit two independent models concurrently.
    pm=new_model(store,dropout=0.);po=optimizer(pm)
    pair_loss=optimizer_step(pm,po,b,y,3072,torch.device('cuda'))['loss']
    pair_values=torch.cat([p.detach().flatten().cpu() for p in pm.parameters()])
    pair_grads=torch.cat([p.grad.detach().flatten().cpu() for p in pm.parameters()])
    pair_delta=models[0]-pair_values
    pair_rel=float(pair_delta.norm()/upd.norm().clamp_min(1e-30))
    pair_grel=float((grads[0]-pair_grads).norm()/grads[0].norm().clamp_min(1e-30))
    pair={'passed':bool(pair_rel<=.05 and pair_grel<=.02 and float(pair_delta.abs().max())<=6.01e-4),
          'microbatches':[64,3072],'relative_l2_parameter_update':pair_rel,'relative_l2_clipped_gradient':pair_grel,
          'max_parameter_absolute':float(pair_delta.abs().max()),'p99_parameter_absolute':float(torch.quantile(pair_delta.abs(),.99)),
          'losses':[losses[0],pair_loss],'dropout':0.,'tolerance':equivalence['tolerance']}
    save(out/'paired-optimizer-equivalence.json',pair)
    del pm,po;gc.collect();torch.cuda.empty_cache()
    if not pair['passed']:raise RuntimeError('paired microbatch equivalence failed')

    # Reference metric implementation from the immutable shakedown source.
    spec=importlib.util.spec_from_file_location('imitation.model._reference_evaluate',Path(args.reference)/'imitation/model/evaluate.py')
    ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
    from .inference import load_policy
    m=load_policy(args.checkpoint).model.cuda().eval()
    # Same logits -> exactly the same statistics (including discrete top-k).
    b,y=build_batch(dev,ix);b,y=transfer(b,'cuda'),transfer(y,'cuda')
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
        o=m(b,torch.empty(0,dtype=torch.long,device='cuda'))
    checks={}
    for temps in ((1.,1.,1.),(.7,1.2,1.5)):
        baseline=ref.metric_rows(o,y,b['ids'][:,:4],temps)
        actual=metric_rows(o,y,b['ids'][:,:4],temps)
        for key in baseline: np.testing.assert_allclose(actual[key],baseline[key],atol=0,rtol=0,equal_nan=True)
        checks[str(temps)]='all row metrics bit-exact from identical logits'
    with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16): teacher=m(b,(y['action'].long()//576).clamp(0,3))
    # This test uses the same batch dimensions, isolating algorithmic equality.
    np.testing.assert_allclose(joint_nll_rows(teacher,y).cpu().numpy(),ref.metric_rows(o,y,b['ids'][:,:4])['joint_nll'],atol=2e-5,rtol=2e-5,equal_nan=True)
    # Full summary (including ECE and cluster-bootstrap) from each row implementation.
    clusters=dev.arrays['perspective_ids'][ix]
    compare_nested(summarize(actual,clusters,100,1),ref.summarize(baseline,clusters,100,1),1e-12)
    save(out/'evaluator-equivalence.json',{'passed':True,'rows':len(ix),'row_metric_checks':checks,
        'joint_nll_tolerance':{'atol':2e-5,'rtol':2e-5},'summary_ece_bootstrap':'atol=rtol=1e-12','reference':args.reference})
    eval_ix=np.linspace(0,len(dev)-1,8192,dtype=np.int64)
    ref_m=reference_network.SetPolicy(reference_network.ModelConfig(),torch.tensor(dev.assets['descriptors']),torch.tensor(dev.assets['tiles']),torch.tensor(dev.assets['costs'])).cuda().eval()
    ref_m.load_state_dict(m.state_dict())
    scored=[]
    times=[]
    for net,bs in ((ref_m,64),(m,1024)):
        pieces={};start=time.perf_counter()
        with torch.inference_mode():
            for bb,yy in batch_loader(dev,bs,eval_ix,workers=2,pin_memory=True):
                bb,yy=transfer(bb,'cuda'),transfer(yy,'cuda')
                with torch.autocast('cuda',dtype=torch.bfloat16): oo=net(bb,torch.empty(0,dtype=torch.long,device='cuda'))
                rr=ref.metric_rows(oo,yy,bb['ids'][:,:4]) if bs==64 else metric_rows(oo,yy,bb['ids'][:,:4])
                for k,v in rr.items():pieces.setdefault(k,[]).append(v)
        scored.append({k:np.concatenate(v) for k,v in pieces.items()})
        times.append(time.perf_counter()-start)
    comparison={}
    for k in scored[0]:
        a,z=scored[0][k],scored[1][k]
        assert np.array_equal(np.isfinite(a),np.isfinite(z))
        use=np.isfinite(a)
        comparison[k]={'max_absolute':float(np.max(np.abs(a[use]-z[use]))) if use.any() else 0.,
                       'mean_difference':float(np.mean(a[use].astype(np.float64)-z[use])) if use.any() else 0.,
                       'unequal_count':int(np.count_nonzero(a[use]!=z[use]))}
    save(out/'batched-dev-comparison.json',{'rows':len(eval_ix),'batch_sizes':[64,1024],
          'rows_per_second':[len(eval_ix)/t for t in times],'metrics':comparison,
          'note':'Measured differences from original model/micro64; exact metric formula check is separate.'})
    del ref_m,m
    save(out/'selection.json',{'passed':equivalence['passed'],'microbatch':chosen,'candidates':tested,'note':'performance benchmarks still required'})
    if not equivalence['passed']: raise RuntimeError('bf16 equivalence tolerance not met')


def benchmark(args,store):
    out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    # Same production sampling and same source mmap, disjoint from heldout.
    ix=epoch_indices(store,0,2903,.02)
    need=(args.steps+2)*8192
    ix=np.resize(ix,need)
    for begin in range(0,len(ix),8192):
        part=ix[begin:begin+8192];ix[begin:begin+len(part)]=part[np.argsort(store.arrays['entity_counts'][part],kind='stable')]
    m=new_model(store);opt=optimizer(m);ema={k:v.detach().clone() for k,v in m.state_dict().items()}
    loader=batch_loader(store,8192,ix,workers=args.workers,pin_memory=True)
    torch.cuda.reset_peak_memory_stats()
    start=time.perf_counter(); measured_start=None;steps=[]
    for step,(b,y) in enumerate(loader):
        y=weighted(y,store)
        for group in opt.param_groups: group['lr']=3e-4*(step+1)/2000
        result=optimizer_step(m,opt,b,y,args.microbatch,torch.device('cuda'));update_ema(ema,m);torch.cuda.synchronize()
        now=time.perf_counter()
        if step==1: measured_start=now
        steps.append({'step':step+1,'loss':result['loss'],'elapsed_seconds':now-start})
        print(json.dumps(steps[-1]),flush=True)
    end=time.perf_counter()
    save(out/'benchmark.json',{'passed':True,'gpu':torch.cuda.get_device_name(),'torch':torch.__version__,
        'effective_batch':8192,'microbatch':args.microbatch,'workers':args.workers,'measured_steps':args.steps,
        'warmup_steps':2,'rows_per_second_including_loader':args.steps*8192/(end-measured_start),
        'cold_rows_per_second_including_loader':len(ix)/(end-start),'wall_seconds':end-start,
        'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved(),
        'gpu_total_bytes':torch.cuda.get_device_properties(0).total_memory,'steps':steps,'hashes':store.hashes})


def main():
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=['qualify','benchmark']);p.add_argument('--store',required=True)
    p.add_argument('--assets',required=True);p.add_argument('--qualification',required=True)
    p.add_argument('--output',required=True);p.add_argument('--reference');p.add_argument('--checkpoint')
    p.add_argument('--microbatch',type=int,default=1024);p.add_argument('--workers',type=int,default=4)
    p.add_argument('--steps',type=int,default=32)
    a=p.parse_args();torch.set_num_threads(1);torch.set_num_interop_threads(1)
    store=PackedStore(a.store,'train',a.assets)
    store.verify_qualification(json.loads(Path(a.qualification).read_text()))
    if a.mode=='qualify':qualify(a,store)
    else:benchmark(a,store)


if __name__=='__main__': main()
