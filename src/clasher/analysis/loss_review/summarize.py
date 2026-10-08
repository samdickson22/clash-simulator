"""Game-cluster percentile bootstrap; paired d27-d0 and human contrasts.

Resampling unit is the original match ID, including both human perspectives.
All estimates are descriptive ratios of summed numerators / opportunities.
"""
import argparse
from collections import defaultdict,Counter
from concurrent.futures import ProcessPoolExecutor
import hashlib,json,multiprocessing,time
from pathlib import Path
import numpy as np
from .human import write
DATA=None;REPS=1000


def bootstrap_matrix(matrix,seed,reps):
    """Exact multinomial game bootstrap, reusing draws for every metric."""
    # matrix: [clusters, metrics, numerator/denominator]
    n=len(matrix);total=matrix.sum(axis=0)
    point=np.divide(total[:,0],total[:,1],out=np.full(len(total),np.nan),where=total[:,1]>0)
    rng=np.random.default_rng(seed);boot=np.empty((reps,matrix.shape[1]))
    for start in range(0,reps,32):
        weights=rng.multinomial(n,np.full(n,1/n),size=min(32,reps-start))
        values=(weights @ matrix.reshape(n,-1)).reshape(len(weights),-1,2)
        boot[start:start+len(weights)]=np.divide(values[:,:,0],values[:,:,1],
            out=np.full(values.shape[:2],np.nan),where=values[:,:,1]>0)
    return point,boot,total


def scope_result(scope):
    metrics=sorted({m for cohort in DATA for rows in DATA[cohort].get(scope,{}).values() for m in rows})
    estimates={};boots={};counts={};support={}
    for cohort,scopes in DATA.items():
        clusters=scopes.get(scope,{})
        if not clusters:continue
        matrix=np.array([[row.get(m,[0.,0.]) for m in metrics] for _,row in sorted(clusters.items())])
        seed=int(hashlib.sha256((scope+cohort).encode()).hexdigest()[:8],16)
        point,boot,total=bootstrap_matrix(matrix,seed,REPS)
        boots[cohort]=boot;counts[cohort]=len(clusters);support[cohort]=(matrix[:,:,1]>0).sum(axis=0)
        estimates[cohort]={}
        for j,m in enumerate(metrics):
            valid=boot[:,j][np.isfinite(boot[:,j])]
            if not np.isfinite(point[j]):continue
            ci=np.quantile(valid,[.025,.975]).tolist() if len(valid) and support[cohort][j]>=2 else None
            estimates[cohort][m]=dict(value=float(point[j]),ci95=ci,clusters=int(support[cohort][j]),
                                      denominator=float(total[j,1]))
    contrasts={}
    for sim,baseline in [(s,h) for s in ('search_d0','search_d27') for h in ('human','human_c56','human_c56_base')]:
        if sim not in boots or baseline not in boots:continue
        contrasts[sim+'-'+baseline]={}
        for j,m in enumerate(metrics):
            if m not in estimates[sim] or m not in estimates[baseline]:continue
            diff=boots[sim][:,j]-boots[baseline][:,j];valid=diff[np.isfinite(diff)]
            contrasts[sim+'-'+baseline][m]=dict(difference=estimates[sim][m]['value']-estimates[baseline][m]['value'],
                ci95=np.quantile(valid,[.025,.975]).tolist() if len(valid) and min(support[sim][j],support[baseline][j])>=2 else None)
    # Paired delay effect: same seed/decks/opponent, both arms in one cluster.
    if all(c in DATA and scope in DATA[c] for c in ('search_d0','search_d27')):
        a=DATA['search_d0'][scope];b=DATA['search_d27'][scope];keys=sorted(a.keys()&b.keys())
        if keys:
            matrix=np.array([[a[k].get(m,[0.,0.]) for m in metrics]+[b[k].get(m,[0.,0.]) for m in metrics] for k in keys])
            point,boot,_=bootstrap_matrix(matrix,76403,REPS);width=len(metrics)
            contrasts['search_d27-search_d0_paired']={}
            for j,m in enumerate(metrics):
                v=boot[:,j+width]-boot[:,j];v=v[np.isfinite(v)]
                if not np.isfinite(point[j+width]-point[j]):continue
                contrasts['search_d27-search_d0_paired'][m]=dict(difference=float(point[j+width]-point[j]),
                    ci95=np.quantile(v,[.025,.975]).tolist() if len(v) and len(keys)>=2 else None,clusters=len(keys))
    return scope,dict(cohorts=estimates,contrasts=contrasts,clusters=counts)


def ingest(paths):
    data=defaultdict(lambda:defaultdict(lambda:defaultdict(dict)));coverage=defaultdict(Counter)
    push_association=defaultdict(lambda:defaultdict(lambda:np.zeros((2,2))))
    seen=set()
    for path in paths:
        paths2=sorted(path.glob('*.json')) if path.is_dir() else [path]
        for file in paths2:
            with file.open() as stream:
                rows=map(json.loads,stream) if file.suffix=='.jsonl' else [json.load(stream)]
                for r in rows:
                    if r['role'] not in ('train','dev','exploration'):raise ValueError('forbidden input role')
                    identity=(r['cohort'],r['identity'])
                    if identity in seen:raise ValueError('duplicate perspective')
                    seen.add(identity)
                    cohort=r['cohort'];coverage[cohort]['perspectives']+=1;coverage[cohort]['frames']+=r['frames']
                    coverage[cohort]['seconds']+=r['duration_seconds'];coverage[cohort]['role:'+r['role']]+=1
                    meta=r.get('metadata',{});coverage[cohort]['cut:'+str(meta.get('cut_reason','terminal' if meta.get('terminal') else 'horizon'))]+=1
                    if r.get('loss') is not None:
                        r['stats']['all']['game_loss_fraction']=[r['loss'],1.]
                    for scope,metrics in r['stats'].items():
                        target=data[cohort][scope][r['cluster']]
                        for m,pair in metrics.items():
                            previous=target.setdefault(m,[0.,0.]);previous[0]+=pair[0];previous[1]+=pair[1]
                    if cohort=='human':
                        for flag in ('c56','c56_base'):
                            if not meta.get(flag):continue
                            subset='human_'+flag
                            coverage[subset]['perspectives']+=1
                            coverage[subset]['frames']+=r['frames']
                            for scope,metrics in r['stats'].items():
                                target=data[subset][scope][r['cluster']]
                                for m,pair in metrics.items():
                                    previous=target.setdefault(m,[0.,0.]);previous[0]+=pair[0];previous[1]+=pair[1]
                    for push in r.get('pushes',[]):
                        row=push_association[cohort][r['cluster']][int(push['elixir']<4)]
                        row[0]+=float(push['tower_damage']>0);row[1]+=1
    return {c:{s:dict(v) for s,v in scopes.items()} for c,scopes in data.items()}, {c:dict(v) for c,v in coverage.items()},push_association


def main():
    global DATA,REPS
    ap=argparse.ArgumentParser();ap.add_argument('--inputs',type=Path,nargs='+',required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--workers',type=int,default=32);ap.add_argument('--bootstrap',type=int,default=1000)
    args=ap.parse_args();start=time.monotonic();REPS=args.bootstrap
    DATA,coverage,push=ingest(args.inputs);scopes=sorted({s for c in DATA.values() for s in c})
    with ProcessPoolExecutor(args.workers,mp_context=multiprocessing.get_context('fork')) as pool:
        results=dict(pool.map(scope_result,scopes))
    associations={}
    for cohort,clusters in push.items():
        matrix=np.stack(list(clusters.values()))
        point,boot,total=bootstrap_matrix(matrix,4231,REPS)
        d=boot[:,1]-boot[:,0];d=d[np.isfinite(d)]
        if np.isfinite(point).all():associations[cohort]=dict(low_elixir_tower_damage_risk_difference=float(point[1]-point[0]),
            ci95=np.quantile(d,[.025,.975]).tolist() if len(d) else None,clusters=len(clusters),
            label='between-push association; game-cluster bootstrap; not causal or within-match adjusted')
    write(args.out,dict(schema='clasher.loss-review.v1',lane='exploration',bootstrap_reps=REPS,
        resampling_unit='original game; both human perspectives clustered; d27/d0 paired by seed',
        coverage=coverage,scopes=results,push_associations=associations,wall_seconds=time.monotonic()-start,
        unavailable=dict(actual_spell_hits='no damage-source attribution in packed store',
             actual_spell_elixir_trade='geometry is not realized damage or a trade',
             strategic_cycle_error='no oracle optimal card/cycle labels; availability proxy only',
             identified_survivor_counterpush='packed store has no persistent entity IDs; pressure conversion proxy',
             pro_baseline='human corpus is not individually pro-qualified'),
        caveats=['No causal win-rate uplift inferred.','Pointwise CIs; no multiplicity correction.',
            'Human reconstructed states and scripted simulator opponents differ in population, balance, levels and decks.',
            'Lane incursion onset, not tracking every unit crossing; 2-second reset; direct deployments included.',
            '8-second complete response window; capped latency includes non-response; preemptive proxy separate.']))

if __name__=='__main__':main()
