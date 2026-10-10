"""Pair-preserving seed bootstrap plus exhaustive game/latency checks."""
import argparse,hashlib,json,math,subprocess
from collections import Counter
from pathlib import Path
import numpy as np
ARMS=('K0c-200','S-200','K0c-160','S-160','K2-200')

def utc():return subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip()
def quant(x):
    return dict(zip(('p50','p95','p99','max'),map(float,np.percentile(x,[50,95,99,100])))) if len(x) else dict.fromkeys(('p50','p95','p99','max'),0.)
def ci(x):return [float(v) for v in np.percentile(x,[2.5,97.5])]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--games',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--smoke',action='store_true');a=ap.parse_args()
    cfg=json.loads((Path(__file__).parent/'plan.json').read_text());count=8 if a.smoke else 600
    base=cfg['seed_ranges']['smoke' if a.smoke else 'reporting']['base'];rows={arm:{} for arm in ARMS};checks=Counter();file_shas={}
    for p in sorted(a.games.glob('*.json')):
        r=json.loads(p.read_text());arm=r['cohort'];m=r['metadata'];s=r['search_ab'];seed=m['seed'];spec=cfg['arms'][arm]
        assert seed not in rows[arm] and base<=seed<base+count
        assert m['arm']==arm and m['terminal'] and m['opponent']=='v1-policy'
        assert m['threads']==spec['threads'] and m['coarse_horizon']==160 and m['honest_lateness']
        assert m['deadline_seconds']==spec['deadline_seconds'] and m['delay_ticks']==m['opponent_delay']==27
        assert r['loss']==float(m['winner'] is not None and m['winner']!=m['seat'])
        assert m['channel']['peak_pending']<=1 and m['opponent_channel']['peak_pending']<=1
        affinity=s['worker_affinity'];assert len(affinity)==cfg['compute']['game_physical_cores'][arm] and set(affinity)<=set(range(39))
        assert s['nice']==10 and s['scheduler']==0 and s['host']=='127x01'
        assert all(not e['during_decision'] for e in s.get('gc_maintenance',[]))
        if spec['policy']!='v1-unmodified':
            assert s['policy_cache_counts']['forward']==s['policy_cache_counts']['fallback']==s['policy_polls'][str(m['seat'])]
            assert m['checkpoint_sha256']==(cfg['student']['checkpoint_sha256'] if spec['policy']=='R3a-cached' else cfg['policy']['checkpoint_sha256'])
        assert m['kernel']==spec['kernel']
        lat=s['latency_seconds'];stats=s['deadline_stats'];assert len(lat)==len(stats)
        for wall,d in zip(lat,stats):
            expected=max(0.,wall-spec['deadline_seconds']);assert d['wall_seconds']==wall
            assert d['overrun_seconds']==expected and d['wall_overrun']==(expected>0)
            assert d['delayed_ticks']==math.ceil(expected*20)
            checks['decisions']+=1;checks['overruns']+=expected>0
        rows[arm][seed]=r;checks['games']+=1;file_shas[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
    seeds=list(range(base,base+count));assert all(sorted(rows[arm])==seeds for arm in ARMS)
    if not a.smoke:
        assert Counter((rows['K0c-200'][seed]['metadata']['seat'],(seed-base)%5,((seed-base)//5)%5) for seed in seeds)==Counter({(seat,own,other):12 for seat in (0,1) for own in range(5) for other in range(5)})
    for seed in seeds:
        metas=[rows[arm][seed]['metadata'] for arm in ARMS]
        assert all((m['own_deck'],m['opponent_deck'],m['seat'])==(metas[0]['own_deck'],metas[0]['opponent_deck'],metas[0]['seat']) for m in metas)
    block_dir=a.games.parent/'blocks'
    assert len(list(block_dir.glob('*.json')))==count
    for index,seed in enumerate(seeds):
        proof=json.loads((block_dir/f'{index:04d}.json').read_text())
        order=list(ARMS);shift=index%len(order);order=order[shift:]+order[:shift]
        assert proof['index']==index and proof['seed']==seed and proof['order']==order
        assert len(proof['slot_cores'])==3 and set(proof['slot_cores'])<=set(range(39))
        metas=[rows[arm][seed]['search_ab'] for arm in ARMS]
        for arm,m in zip(ARMS,metas):
            assert m['worker_pid']==proof['worker_pid'] and m['worker_pgid']==proof['worker_pgid']
            assert m['worker_affinity']==proof['slot_cores'][:cfg['compute']['game_physical_cores'][arm]]
        assert len(proof['games'])==5
        for name,h in proof['games'].items():assert file_shas[name]==h
    rng=np.random.default_rng(cfg['bootstrap']['seed']);idx=rng.integers(0,count,size=(cfg['bootstrap']['reps'],count))
    losses={arm:np.array([rows[arm][seed]['loss'] for seed in seeds]) for arm in ARMS};resamples={arm:v[idx].mean(1) for arm,v in losses.items()};anchor=losses['K0c-200']
    out=dict(utc=utc(),smoke_excluded=a.smoke,plan_sha256=hashlib.sha256((Path(__file__).parent/'plan.json').read_bytes()).hexdigest(),paired_seeds=count,checks=dict(checks),bootstrap=cfg['bootstrap'],arms={},file_shas=file_shas)
    for arm in ARMS:
        rs=[rows[arm][seed] for seed in seeds];ds=[r['search_ab']['deadline_stats'] for r in rs];walls=[x for r in rs for x in r['search_ab']['latency_seconds']];over=[d['overrun_seconds'] for game in ds for d in game if d['wall_overrun']];cutwalls=[d['wall_seconds'] for game in ds for d in game if d['hit']]
        ns=np.array([len(g) for g in ds]);cut=np.array([sum(d['hit'] for d in g) for g in ds]);late=np.array([sum(d['wall_overrun'] for d in g) for g in ds])
        fall=np.array([sum(d['fallback'] for d in g) for g in ds])
        cutoff=100*cut[idx].sum(1)/ns[idx].sum(1);overrun=100*late[idx].sum(1)/ns[idx].sum(1)
        gc_pauses=[e['seconds'] for r in rs for e in r['search_ab'].get('gc_maintenance',[])]
        deadline=cfg['arms'][arm]['deadline_seconds']
        out['arms'][arm]=dict(wins=sum(r['metadata']['winner']==r['metadata']['seat'] for r in rs),losses=int(losses[arm].sum()),draws=sum(r['metadata']['winner'] is None for r in rs),loss_pct=100*losses[arm].mean(),loss_ci_pct=ci(100*resamples[arm]),loss_change_pp=100*(losses[arm]-anchor).mean(),loss_change_ci_pp=ci(100*(resamples[arm]-resamples['K0c-200'])),fallback_pct=100*fall.sum()/ns.sum(),fallback_ci_pct=ci(100*fall[idx].sum(1)/ns[idx].sum(1)),fallback_count=int(fall.sum()),cutoff_pct=100*cut.sum()/ns.sum(),cutoff_ci_pct=ci(cutoff),decisions=int(ns.sum()),overrun_count=len(over),overrun_pct=100*late.sum()/ns.sum(),overrun_ci_pct=ci(overrun),positive_overrun_ms=quant(np.array(over)*1000),wall_ms=quant(np.array(walls)*1000),cut_wall_ms=quant(np.array(cutwalls)*1000),cut_past_deadline_count=sum(w>deadline for w in cutwalls),cut_past_deadline_plus_reserve_count=sum(w>deadline+.008 for w in cutwalls),gc_maintenance_seconds=sum(gc_pauses),gc_maintenance_ms=quant(np.array(gc_pauses)*1000),gc_maintenance_count=len(gc_pauses),preparation_cutoffs=dict(Counter(d.get('preparation_cutoff','scoring_or_none') for game in ds for d in game)),overrun_ticks_hist=dict(Counter(str(d['delayed_ticks']) for game in ds for d in game if d['wall_overrun'])),game_cpu_hours=sum(r['cpu_seconds'] for r in rs)/3600,worker_masks=dict(Counter(','.join(map(str,r['search_ab']['worker_affinity'])) for r in rs)))
    out['contrasts']={}
    for left,right in [('S-200','K0c-200'),('S-160','K0c-160'),('S-200','K2-200'),('S-160','S-200'),('K0c-160','K0c-200')]:
        out['contrasts'][left+' minus '+right]=dict(loss_change_pp=float(100*(losses[left]-losses[right]).mean()),ci95_pp=ci(100*(resamples[left]-resamples[right])))
    checks_viable=[out['contrasts']['S-200 minus K0c-200']['ci95_pp'][1]<=-10,out['contrasts']['S-200 minus K2-200']['ci95_pp'][1]<=5]
    out['decision']=dict(rule=cfg['decision_rules']['viable'],component_passes=checks_viable,viable=all(checks_viable) if not a.smoke else None,conclusion=('1-core student tier viable' if all(checks_viable) else 'descriptive only') if not a.smoke else 'excluded smoke only')
    a.out.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k not in ('file_shas','arms')},indent=2))
if __name__=='__main__':main()
