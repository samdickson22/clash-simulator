"""T10: orchestration around unchanged frozen v3b reconstruction and T2 observer.

No engine/extractor edits, no v2 reuse/deletion path. Units are immutable after
verified publication. Existing successful receipts are checksum-verified on resume.
All truth arrays live exclusively in audit/. Input and code hashes bind every unit.
"""
from __future__ import annotations
import argparse, collections, concurrent.futures, gzip, hashlib, json, multiprocessing, os
from pathlib import Path
import resource, signal, socket, subprocess, sys, time, traceback
HERE=Path(__file__).resolve().parent
IM=HERE.parent; DATA=IM/'data'; C56=IM.parent/'c56/data'; RUNTIME=C56/'runtime-engine-v3b'
os.environ['CLASHER_ROOT']=str(RUNTIME)
sys.path[:0]=[str(RUNTIME/'src'),str(C56/'scripts'),str(IM)]
import numpy as np
import c56_v3_bootstrap as cb
from clasher.rl import human_replay_v5 as v5
from clasher.rl.contract_v5 import ContractV5ObservationBuilder,CachedContractV5ActionMask
from clasher.rl.human_replay_demonstrations import parse_il_replay_record
from v3_common import write_parts,validate
from qa_v3 import aggregate
from sidecar_observer import SidecarObserver,intent_targets
from fetch_source import sha
BUILDER=None; PIN=None

def read(p):return json.loads(Path(p).read_text())
def write(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,sort_keys=True)+'\n');tmp.replace(p)
def pins():
    d1_receipt=read(DATA/'receipts/T1-PASS.json')
    assert d1_receipt['passed'] and 'T1' in d1_receipt['tasks']
    assert all(sha(IM/n)==digest for n,digest in d1_receipt['source_sha256'].items()), 'T1 source pins changed'
    gate=read(C56/'qa/v3b/gates.json'); manifest=cb.runtime_manifest()
    assert manifest['sha256']==gate['runtime']['sha256']
    assert sha(C56/'scripts/extract_v3.py')==gate['driver_sha256']
    return {'runtime':manifest,'extractor_sha256':gate['driver_sha256'],
            'code_sha256':{str(p.relative_to(IM)):sha(p) for p in [IM/'derived_d1.py',IM/'own_cycle.py',IM/'sidecar_observer.py',Path(__file__)]},
            'T1_receipt_sha256':sha(DATA/'receipts/T1-PASS.json'),'T9_receipt_sha256':sha(DATA/'receipts/T9-PASS.json')}
def initialize(pin):
    global BUILDER,PIN
    cb.bind_runtime();PIN=pin
    assert pins()==pin
    BUILDER=ContractV5ObservationBuilder()
def unchanged():
    assert all(sha(IM/n)==s for n,s in PIN['code_sha256'].items()),'pinned observer/driver changed'

def terminal_row(observer,game):
    # Frozen extractor does not call row_observer for its terminal context row.
    # Reuse the SAME T2 observer, supplying final public top-up counters for its
    # separate truth audit; these counters are never a policy input.
    counters=game.summary['counters']
    observer(observer.battle,observer.learner,2304)

def per_card(compact,summary):
    attempts=collections.Counter(); rejected=collections.Counter()
    for i,a in enumerate(compact['expert_actions']):
        if a<2304:attempts[BUILDER.token_names[int(compact['hand_ids'][i,int(a)//576])]]+=1
    reason=summary['cut_reason'];detail=summary['cut_detail']
    if reason in ('own_masked_tile','pocket_play_but_sim_tower_alive') and detail.get('side')!='opponent':
        card=detail['card'];attempts[card]+=1;rejected[card]+=1
    elif reason=='own_placement_rejected':
        a=int(compact['expert_actions'][-1]);assert a<2304
        rejected[BUILDER.token_names[int(compact['hand_ids'][-1,a//576])]]+=1
    assert sum(attempts.values())==summary['counters']['own_plays_labelled']+int(reason in ('own_masked_tile','pocket_play_but_sim_tower_alive') and detail.get('side')!='opponent')
    return {'attempts':dict(attempts),'rejected':dict(rejected)}

def run_unit(job):
    unit,outname,excluded,baseline=job;out=Path(outname);name=unit['unit']; receipt=out/'units'/f'{name}.json'
    unchanged()
    if receipt.exists():
        value=read(receipt)
        assert value['pins']==PIN and value['input_sha256']==unit['sha256'] and value['excluded_cards']==excluded
        assert all(sha(out/n)==s for n,s in value['files'].items())
        assert not any(value['violations'])
        return value|{'reused':True}
    source=DATA/unit['file'];assert sha(source)==unit['sha256']
    items=json.loads(gzip.decompress(source.read_bytes()))
    start=time.perf_counter();cpu=time.process_time();parts=[];summaries=[];sidecars=[];audits=[];events=[];errors=[];skipped=[];stats=[]
    coverage=np.zeros((21,7),np.int64);masks=CachedContractV5ActionMask(BUILDER);template=None;files={}
    slugs=cb.slug_map()
    for pair in items:
        item=pair['item'];record=pair['record'];assert item['tag']==record['tag']
        if set(item['own_base'])&set(excluded):skipped.append(item['tag']+'|'+item['side']);continue
        try:
            match=parse_il_replay_record(record,slugs)
            if baseline:
                game=v5.reconstruct_perspective_v5(match,item['seat'],BUILDER,mask_builder=masks,episode_id=item['episode_id'],config=v5.ReconstructionConfigV5(tower_clamp=True))
                observer=None
            else:
                with SidecarObserver(BUILDER) as observer:
                    game=v5.reconstruct_perspective_v5(match,item['seat'],BUILDER,mask_builder=masks,episode_id=item['episode_id'],config=v5.ReconstructionConfigV5(tower_clamp=True),row_observer=observer)
                if len(observer.rows)+1==game.summary['rows'] and game.summary['terminal_context_row']:terminal_row(observer,game)
            compact=v5.compact_demonstration_v5(game)
            if observer is not None:
                d1,audit=observer.arrays();assert len(d1['opp_elixir'])==len(compact['expert_actions'])
                d1.update(intent_targets(compact,d1,game.summary['cut_tick']))
                d1.update(episode_ids=compact['episode_ids'],submitted_ticks=compact['submitted_ticks'])
                audit.update(episode_ids=compact['episode_ids'],submitted_ticks=compact['submitted_ticks'])
                assert not audit['violation'].any(),('sidecar truth audit',audit['violation'].sum(0).tolist())
                sidecars.append(d1);audits.append(audit);events.append({'episode_id':item['episode_id'],'events':observer.public_events})
                bins=np.minimum(compact['submitted_ticks']//300,20);known=(d1['opp_hand_known']!=0).sum(1)
                for b in np.unique(bins):
                    take=bins==b;coverage[b,0]+=take.sum();coverage[b,1]+=(d1['opp_next_card'][take]!=0).sum();coverage[b,2:]+=np.bincount(known[take],minlength=5)
            if template is None:
                p=out/'header-seed'/f'{name}.npz';p.parent.mkdir(parents=True,exist_ok=True)
                w=v5.HumanReplayShardWriterV5();w.add(game);template=w.write(p);files[str(p.relative_to(out))]=sha(p)
            parts.append(compact);summaries.append(game.summary)
            stats.append({'item':item,'per_card':per_card(compact,game.summary)})
        except Exception as exc:
            error={'item':item,'error':repr(exc),'traceback':traceback.format_exc()}
            # Audit failures are fatal, never counted as tolerated extraction errors.
            observer_failure=any(n in error['traceback'] for n in ('sidecar_observer.py','derived_d1.py','own_cycle.py'))
            if isinstance(exc,AssertionError) or observer_failure:
                write(out/'fatal'/f'{name}-{item["episode_id"]}.json',error);raise
            errors.append(error)
    validation={'rows':0,'perspectives':0,'illegal':0}
    if parts:
        p=out/f'{name}.npz';p.parent.mkdir(parents=True,exist_ok=True)
        write_parts(p,parts,summaries,template,{'extraction':'s122-inline-v3b','runtime_sha256':PIN['runtime']['sha256'],'unit':name})
        validation=validate(p);files[str(p.relative_to(out))]=sha(p)
        for kind,values in [('sidecar',sidecars),('audit',audits)]:
            if not values:continue
            merged={n:np.concatenate([v[n] for v in values]) for n in values[0]}
            p=out/kind/f'{name}.npz';p.parent.mkdir(parents=True,exist_ok=True);v5.save_npz_deterministic(p,merged);files[str(p.relative_to(out))]=sha(p)
        if events:
            p=out/'events'/f'{name}.json.gz';p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(gzip.compress(json.dumps(events,sort_keys=True).encode(),mtime=0));files[str(p.relative_to(out))]=sha(p)
    unchanged()
    result={'unit':name,'pins':PIN,'input_sha256':unit['sha256'],'excluded_cards':excluded,'attempted':len(items)-len(skipped),'skipped':skipped,'perspectives':len(summaries),'rows':validation['rows'],'illegal_labels':validation['illegal'],'errors':errors,'summaries':summaries,'stats':stats,'violations':[0]*5,'coverage':coverage.tolist(),'files':files,'wall_seconds':time.perf_counter()-start,'cpu_seconds':time.process_time()-cpu}
    write(receipt,result)
    return result

def processes():
    # Count all same-user Python and native Clasher workloads, including idle pool
    # children (spawn_main does not carry the parent's script name).
    output=subprocess.check_output(['ps','-u',str(os.getuid()),'-o','pid=,stat=,comm=,args='],text=True)
    found=[]
    for line in output.splitlines():
        words=line.strip().split(None,3)
        if len(words)!=4:continue
        pid,state,comm,args=words
        if int(pid)==os.getpid() or state.startswith('Z'):continue
        computational=comm.startswith('python') or comm.startswith('clasher') or '/engine-rs/target/' in args.split()[0]
        if computational and not any(s in args for s in ('resource_tracker','jupyterhub')):
            found.append({'pid':int(pid),'args':args})
    return found

def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['qa','repeat','baseline','production']);ap.add_argument('--workers',type=int,default=8);ap.add_argument('--partition',type=int,default=0);ap.add_argument('--partitions',type=int,default=1);args=ap.parse_args()
    assert socket.gethostname() in ('127x01','127x03')
    assert (DATA/'receipts/T1-PASS.json').exists() and read(DATA/'receipts/T9-PASS.json')['status']=='PASS'
    console=subprocess.check_output(['who'],text=True).strip();cap=16 if console else 80
    others=processes();workers=min(args.workers,cap-2)
    assert min(workers,cap-len(others)-2)>=1,('no worker capacity',others)
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    pin=pins()
    if args.mode=='production':
        qa=read(DATA/'receipts/T10-QA-PASS.json');assert qa['passed'] and qa['pins']==pin
        excluded=qa['excluded_new_cards'];plan=read(DATA/'inputs/production-plan.json')
        out=DATA/'recon/engine-v3-s122'
    else:
        excluded=[];plan=read(DATA/'inputs/qa-fast-plan.json');out=DATA/'qa'/('s122-'+args.mode)
    units=plan['units']
    if args.mode in ('repeat','baseline'):units=[u for u in units if u['keys'][0] in plan['determinism_keys']];assert len(units)==6
    units=units[args.partition::args.partitions];out.mkdir(parents=True,exist_ok=True)
    import fcntl
    lock=(out/f'partition-{args.partition}.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    launch={'pid':os.getpid(),'host':socket.gethostname(),'workers':workers,'requested_workers':args.workers,'other_processes':others,'console':console,'pins':pin,'units':len(units),'started_unix':time.time()}
    status=out/f'status-{socket.gethostname()}-{args.partition}.json';write(out/f'launch-{socket.gethostname()}-{args.partition}.json',launch)
    stop=False
    def stopping(*_):
        nonlocal stop
        stop=True
    signal.signal(signal.SIGTERM,stopping);signal.signal(signal.SIGINT,stopping)
    started=time.perf_counter();completed=attempted=failed=rows=0;cpu=0.;pending={};todo=iter(units);exhausted=False
    with concurrent.futures.ProcessPoolExecutor(workers,mp_context=multiprocessing.get_context('spawn'),initializer=initialize,initargs=(pin,)) as pool:
        while pending or not exhausted:
            current_cap=16 if subprocess.check_output(['who'],text=True).strip() else 80
            # Hold dispatch if another launch consumes the remaining allocation.
            active_other=len(processes())-len(pool._processes)
            # Reserve the announced C56 allocation until its full manifest exists,
            # even between its launches; grow this pool only after C56 completion.
            c56_done=any(read(p).get('passed') and read(p).get('perspectives')==82231 for p in DATA.glob('c56-sidecars*/manifest.json'))
            reserved=64 if args.mode=='production' and not c56_done else 0
            capacity=max(0,min(workers,current_cap-max(active_other,reserved)-2))
            while not stop and not exhausted and len(pending)<capacity:
                unit=next(todo,None)
                if unit is None:exhausted=True;break
                pending[pool.submit(run_unit,(unit,str(out),excluded,args.mode=='baseline'))]=unit
            if stop:exhausted=True
            ready,_=concurrent.futures.wait(pending,timeout=5,return_when=concurrent.futures.FIRST_COMPLETED)
            for future in ready:
                unit=pending.pop(future);v=future.result();completed+=1;attempted+=v['attempted'];failed+=len(v['errors']);rows+=v['rows'];cpu+=0 if v.get('reused') else v['cpu_seconds']
                print(json.dumps({k:v[k] for k in ('unit','perspectives','rows','violations','wall_seconds')}|{'errors':len(v['errors']),'reused':v.get('reused',False)}),flush=True)
                if failed and (args.mode!='production' or failed/attempted>=.005):stop=True
            write(status,{'host':socket.gethostname(),'pid':os.getpid(),'workers':len(pool._processes),'max_workers':workers,'capacity':capacity,'reserved_c56':reserved,'units':len(units),'completed':completed,'attempted':attempted,'errors':failed,'rows':rows,'wall_seconds':time.perf_counter()-started,'worker_cpu_seconds_this_run':cpu,'inflight':len(pending),'stopping':stop})
            if not pending and not exhausted:time.sleep(5)
    assert not stop,'stopped: inspect errors and resume; no automatic changes to frozen runtime'
    assert pins()==pin
    result=read(status)|{'complete':True,'pins':pin}
    write(out/f'complete-{socket.gethostname()}-{args.partition}.json',result)
if __name__=='__main__':main()
