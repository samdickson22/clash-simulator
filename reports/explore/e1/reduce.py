"""Paired seed bootstrap and ledger reduction; no raw game records published."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from clasher.analysis.loss_review.summarize import bootstrap_matrix


def timing(values):
    a=np.asarray(values,dtype=float)
    return dict(decisions=len(a),p50_ms=float(np.quantile(a,.5)*1000),p95_ms=float(np.quantile(a,.95)*1000),
                p99_ms=float(np.quantile(a,.99)*1000),over200_fraction=float(np.mean(a>.2))) if len(a) else None


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--roots',nargs='+',type=Path,required=True)
    ap.add_argument('--config',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--arms',nargs='+');ap.add_argument('--smoke',action='store_true')
    a=ap.parse_args();cfg=json.loads(a.config.read_text());arms=a.arms or list(cfg['arms']);n=2 if a.smoke else cfg['paired_seeds']
    base=cfg['seed_ranges']['smoke' if a.smoke else 'reporting']['base'];seeds=list(range(base,base+n))
    rows={arm:{} for arm in arms};hashes=[]
    for root in a.roots:
        for path in sorted((root/'games').glob('*.json')):
            r=json.loads(path.read_text());arm=r['cohort'];seed=r['metadata']['seed']
            if arm not in arms: continue
            assert seed in seeds and seed not in rows[arm],(arm,seed)
            assert r['metadata']['terminal'] and r['role']=='exploration'
            assert r['metadata']['delay_ticks']==r['metadata']['opponent_delay']==27
            assert len(r['search_ab']['worker_affinity'])==1
            expected_polls=max(0,r['frames']-18)
            assert set(r['search_ab']['policy_polls'])=={'0','1'}
            assert all(v==expected_polls for v in r['search_ab']['policy_polls'].values()),(arm,seed,'policy cadence')
            assert r['metadata']['reserve_floor']==cfg['arms'][arm].get('reserve_floor',False)
            assert r['metadata']['deadline_seconds']==cfg['arms'][arm]['deadline_seconds']
            for k in ('channel','opponent_channel'):
                q=r['metadata'][k];assert q['submitted']==q['executed']+q['pending_at_end'] and q['peak_pending']<=1
            rows[arm][seed]=r;hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
    for arm in arms: assert set(rows[arm])==set(seeds),(arm,len(rows[arm]),n)
    for seed in seeds:
        meta=rows[arms[0]][seed]['metadata']
        for arm in arms[1:]:
            assert all(rows[arm][seed]['metadata'][k]==meta[k] for k in ('seed','seat','own_deck','opponent_deck'))
    if not a.smoke:
        counts=Counter((tuple(sorted(r['metadata']['own_deck'])),tuple(sorted(r['metadata']['opponent_deck'])),r['metadata']['seat']) for r in rows[arms[0]].values())
        assert len(counts)==50 and set(counts.values())=={12}
    metrics=['loss','win','draw','score','arrival_under4_fraction','no_affordable_defender_in_hand_fraction',
             'defender_not_in_hand_fraction','time_at_max_fraction','rejected_play_fraction',
             'deadline_hit','fallback','wall_overrun','opponent_deadline_hit','opponent_fallback','opponent_wall_overrun',
             'damage_risk_low','damage_risk_high','arrival_under4_in_losses','arrival_under4_in_nonlosses']
    matrix=np.zeros((n,len(arms)*len(metrics),2));mindex={m:i for i,m in enumerate(metrics)}
    seat_matrix=np.zeros((n,2*len(arms)*len(metrics),2))
    outcomes={};latencies={};counts={};throughput={};cpu_total=0.
    for ai,arm in enumerate(arms):
        wall=[];cpu=[];opponent_wall=[];warmed_cpu=[];wld=Counter();count=Counter();elapsed=0.
        for si,seed in enumerate(seeds):
            r=rows[arm][seed];meta=r['metadata'];ab=r['search_ab'];win=meta['winner']==meta['seat'];draw=meta['winner'] is None
            wld['wins']+=win;wld['draws']+=draw;wld['losses']+=r['loss']
            s=dict(r['stats']['all']);s.update(loss=[r['loss'],1],win=[win,1],draw=[draw,1],score=[float(win)+.5*draw,1])
            wall.extend(ab['latency_seconds']);cpu.extend(ab['cpu_latency_seconds']);opponent_wall.extend(ab['opponent_latency_seconds'])
            warmed_cpu.extend(ab['cpu_latency_seconds'][1:]);cpu_total+=r['cpu_seconds'];elapsed+=r['cpu_seconds']
            for prefix,key in (('', 'deadline_stats'),('opponent_', 'opponent_deadline_stats')):
                ds=ab[key]
                for metric,field in (('deadline_hit','hit'),('fallback','fallback'),('wall_overrun','wall_overrun')):
                    s[prefix+metric]=[sum(d[field] for d in ds),len(ds)]
                    count[prefix+metric]+=s[prefix+metric][0]
                count[prefix+'deadline_decisions']+=len(ds)
            count['floor_removed']+=ab['floor_removed']
            count['policy_polls_own']+=ab['policy_polls'][str(meta['seat'])]
            count['policy_polls_opponent']+=ab['policy_polls'][str(1-meta['seat'])]
            for key in ('channel','opponent_channel'):
                count[key+'_rejected']+=meta[key]['rejected'];count[key+'_submitted']+=meta[key]['submitted']
            pushes=r['pushes'];low=[p for p in pushes if p['elixir']<4];high=[p for p in pushes if p['elixir']>=4]
            s['damage_risk_low']=[sum(p['tower_damage']>0 for p in low),len(low)]
            s['damage_risk_high']=[sum(p['tower_damage']>0 for p in high),len(high)]
            s['arrival_under4_in_losses']=[len(low),len(pushes)] if r['loss'] else [0,0]
            s['arrival_under4_in_nonlosses']=[len(low),len(pushes)] if not r['loss'] else [0,0]
            for m,mi in mindex.items():
                values=s.get(m,[0,0]);matrix[si,ai*len(metrics)+mi]=values
                seat_matrix[si,(meta['seat']*len(arms)+ai)*len(metrics)+mi]=values
        outcomes[arm]={k:int(v) for k,v in wld.items()};outcomes[arm]['games']=n
        latencies[arm]=dict(wall=timing(wall),cpu=timing(cpu),opponent_wall=timing(opponent_wall))
        counts[arm]=dict(count)
        throughput[arm]=dict(warm_decisions=len(warmed_cpu),warm_decision_cpu_seconds=sum(warmed_cpu),
            decisions_per_core_second=len(warmed_cpu)/sum(warmed_cpu),game_cpu_seconds=elapsed,
            end_to_end_own_decisions_per_game_cpu_second=len(wall)/elapsed,all_own_decisions=len(wall),
            scope='own observation+v1 sample+belief+candidates+root+scoring+submission CPU; per-game first decision excluded; intermediate5tick policy maintenance excluded')
    point,boots,total=bootstrap_matrix(matrix,cfg['bootstrap']['seed'],cfg['bootstrap']['reps'])
    def estimate(p,b,t=None):
        good=b[np.isfinite(b)]
        row=dict(value=float(p) if np.isfinite(p) else None,ci95=np.quantile(good,[.025,.975]).tolist() if len(good) else None)
        if t is not None:row.update(numerator=float(t[0]),denominator=float(t[1]))
        return row
    seat_point,seat_boots,seat_total=bootstrap_matrix(seat_matrix,cfg['bootstrap']['seed'],cfg['bootstrap']['reps'])
    estimates_by_seat={}
    for seat in (0,1):
        estimates_by_seat[str(seat)]={}
        for ai,arm in enumerate(arms):
            estimates_by_seat[str(seat)][arm]={m:estimate(seat_point[(seat*len(arms)+ai)*len(metrics)+mi],
                seat_boots[:,(seat*len(arms)+ai)*len(metrics)+mi],seat_total[(seat*len(arms)+ai)*len(metrics)+mi]) for m,mi in mindex.items()}
    estimates={};contrasts={};associations={}
    for ai,arm in enumerate(arms):
        estimates[arm]={m:estimate(point[ai*len(metrics)+mi],boots[:,ai*len(metrics)+mi],total[ai*len(metrics)+mi]) for m,mi in mindex.items()}
        li=ai*len(metrics)+mindex['damage_risk_low'];hi=ai*len(metrics)+mindex['damage_risk_high']
        associations[arm]=dict(low_minus_high_damage_risk=estimate(point[li]-point[hi],boots[:,li]-boots[:,hi]))
    for left,right in [('aW','a0'),('bW','b0'),('bR','bW')]:
        if left not in arms or right not in arms:continue
        contrast={}
        for m,mi in mindex.items():
            l=arms.index(left)*len(metrics)+mi;r=arms.index(right)*len(metrics)+mi
            contrast[m]=estimate(point[l]-point[r],boots[:,l]-boots[:,r])
        contrasts[left+'_minus_'+right]=contrast
    causal='Pending reserve arm; no causal conclusion yet.'
    if 'bR_minus_bW' in contrasts:
        loss=contrasts['bR_minus_bW']['loss'];arr=contrasts['bR_minus_bW']['arrival_under4_fraction']
        if arr['ci95'] and arr['ci95'][1]<0:
            if loss['ci95'][1]<0:causal='The public reserve-floor intervention reduces under4 arrivals and losses; causal evidence supports this specific floor rule against v1.'
            elif loss['ci95'][0]>0:causal='The floor reduces under4 arrivals but increases losses; reducing the depleted-arrival metric is not the winning lever in this intervention.'
            else:causal='The floor reduces under4 arrivals without a demonstrated loss reduction; the metric is not established as the causal winning lever.'
        else:causal='The floor does not demonstrate a reduction in under4 arrivals; this intervention does not establish depleted arrivals as a cause of losses.'
    result=dict(config_sha256=hashlib.sha256(a.config.read_bytes()).hexdigest(),freeze_commit='bfb9b107',paired_seeds=n,
        arms=arms,terminal_games=n*len(arms),outcomes=outcomes,estimates=estimates,estimates_by_seat=estimates_by_seat,contrasts=contrasts,associations=associations,
        latency=latencies,deadline_counts=counts,throughput=throughput,game_cpu_seconds=cpu_total,
        bootstrap=cfg['bootstrap'],causality_finding=causal,
        input_game_hash_union_sha256=hashlib.sha256(''.join(sorted(hashes)).encode()).hexdigest(),
        smoke=a.smoke,full_schedule_and_single_core_audited=True,policy_cadence_audited=True)
    a.out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(games=result['terminal_games'],outcomes=outcomes,causality=causal)),flush=True)

if __name__=='__main__':main()
