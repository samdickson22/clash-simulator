"""Shared seed bootstrap of outcomes, pooled tempo metrics and decision timings."""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'src'))
from clasher.analysis.loss_review.summarize import bootstrap_matrix


def timing(values):
    x=np.asarray(values)
    return dict(decisions=len(x),p50_ms=float(np.quantile(x,.5)*1000),
        p95_ms=float(np.quantile(x,.95)*1000),p99_ms=float(np.quantile(x,.99)*1000),
        over200_fraction=float(np.mean(x>.2)))


def reduce(root,config,out,smoke=False):
    cfg=json.loads(config.read_text());arms=cfg['arms'];count=2 if smoke else cfg['paired_seeds']
    rows={a:{} for a in arms+['WW']}
    for path in (root/'games').glob('*.json'):
        row=json.loads(path.read_text());arm=row['cohort'];seed=row['metadata']['seed']
        assert arm in rows and seed not in rows[arm] and row['role']=='exploration'
        assert row['metadata']['terminal'], ('nonterminal',str(path))
        assert row['metadata']['delay_ticks']==27 and row['metadata']['opponent_delay']==27
        rows[arm][seed]=row
    for arm in arms:
        assert len(rows[arm])==count and rows[arm].keys()==rows['0'].keys(), (arm,len(rows[arm]))
    assert len(rows['WW'])==(0 if smoke else cfg['ww_pairs'])
    seeds=sorted(rows['0']);base=cfg['seed_ranges']['smoke' if smoke else 'reporting']['base']
    assert seeds==list(range(base,base+count))
    for seed in seeds:
        ref=rows['0'][seed]['metadata']
        for arm in arms+(['WW'] if seed in rows['WW'] else []):
            meta=rows[arm][seed]['metadata']
            assert all(meta[k]==ref[k] for k in ('seed','seat','style','own_deck','opponent_deck','delay_ticks','opponent_delay'))
            for key in ('channel','opponent_channel'):
                q=meta[key]
                assert q['submitted']==q['executed']+q['pending_at_end'] and q['peak_pending']<=1
                assert q['rejected']==0, (seed,arm,key,q)
    common=set().union(*(r['stats']['all'].keys() for r in rows['0'].values()))
    metrics=['game_loss_fraction','game_win_fraction','game_draw_fraction',
        'arrival_under4_fraction','defender_not_in_hand_fraction','no_affordable_defender_in_hand_fraction',
        'time_at_max_fraction','leaked_elixir_lower_bound_per_minute']
    metrics=[m for m in metrics if m.startswith('game_') or m in common]
    metrics+=sorted(m for m in common if ('cap' in m or 'time_at_max' in m) and m not in metrics)
    cards=['Xbow','Giant','Rocket','Fireball','Log']
    metrics+=['card_per_deck_minute:'+c for c in cards]+['affordable_hand_fraction:'+c for c in cards]
    metrics+=['selected_given_offered_fraction:'+c for c in cards]
    metrics+=['mean_wall_decision_ms','mean_cpu_decision_ms','wall_over200_fraction']
    matrix=np.zeros((count,len(arms)*len(metrics),2))
    latencies={};attrs={};outcomes={};waits={};cpu_total=0;rejections={}
    def fill(arm,seed):
        r=rows[arm][seed];meta=r['metadata'];ab=r['search_ab'];s=dict(r['stats']['all'])
        loss=r['loss'];win=meta['winner']==meta['seat'];draw=meta['winner'] is None
        s.update(game_loss_fraction=[loss,1],game_win_fraction=[win,1],game_draw_fraction=[draw,1])
        wall=ab['latency_seconds'];cpu=ab['cpu_latency_seconds']
        s.update(mean_wall_decision_ms=[1000*sum(wall),len(wall)],mean_cpu_decision_ms=[1000*sum(cpu),len(cpu)],
                 wall_over200_fraction=[sum(x>.2 for x in wall),len(wall)])
        for card in cards:
            attr=ab['attrition'].get(card,{})
            s['affordable_hand_fraction:'+card]=[attr.get('affordable',0),attr.get('in_hand',0)]
            s['selected_given_offered_fraction:'+card]=[attr.get('selected',0),attr.get('scored_opportunities',0)]
        return s
    for ai,arm in enumerate(arms+(['WW'] if not smoke else [])):
        wall=[];cpu=[];attr=defaultdict(Counter);wait=Counter();win=loss=draw=0
        for si,seed in enumerate(sorted(rows[arm])):
            r=rows[arm][seed];ab=r['search_ab'];meta=r['metadata']
            loss+=r['loss'];win+=meta['winner']==meta['seat'];draw+=meta['winner'] is None
            cpu_total+=r['cpu_seconds'];wall+=ab['latency_seconds'];cpu+=ab['cpu_latency_seconds'];wait.update(ab['wait_counts'])
            for card,counts in ab['attrition'].items():attr[card].update(counts)
            if arm!='WW':
                s=fill(arm,seed)
                for mi,m in enumerate(metrics):matrix[si,ai*len(metrics)+mi]=s.get(m,[0,0])
        latencies[arm]=dict(wall=timing(wall),cpu=timing(cpu));attrs[arm]=dict(attr);waits[arm]=dict(wait)
        outcomes[arm]=dict(wins=int(win),losses=int(loss),draws=int(draw),games=len(rows[arm]))
    point,boots,total=bootstrap_matrix(matrix,cfg['bootstrap']['seed'],cfg['bootstrap']['reps'])
    estimates={};contrasts={}
    for ai,arm in enumerate(arms):
        estimates[arm]={}
        for mi,m in enumerate(metrics):
            k=ai*len(metrics)+mi;good=boots[:,k][np.isfinite(boots[:,k])]
            estimates[arm][m]=dict(value=float(point[k]) if np.isfinite(point[k]) else None,
                ci95=np.quantile(good,[.025,.975]).tolist() if len(good) else None,
                numerator=float(total[k,0]),denominator=float(total[k,1]))
        if ai:
            contrasts[arm]={}
            for mi,m in enumerate(metrics):
                k=ai*len(metrics)+mi;diff=boots[:,k]-boots[:,mi];good=diff[np.isfinite(diff)]
                contrasts[arm][m]=dict(difference=float(point[k]-point[mi]) if np.isfinite(point[k]-point[mi]) else None,
                                      ci95=np.quantile(good,[.025,.975]).tolist() if len(good) else None)
    ww_estimates={}
    if rows['WW']:
        ww_matrix=np.zeros((len(rows['WW']),len(metrics),2))
        for si,seed in enumerate(sorted(rows['WW'])):
            s=fill('WW',seed)
            for mi,m in enumerate(metrics):ww_matrix[si,mi]=s.get(m,[0,0])
        wp,wb,wt=bootstrap_matrix(ww_matrix,cfg['bootstrap']['seed'],cfg['bootstrap']['reps'])
        for mi,m in enumerate(metrics):
            good=wb[:,mi][np.isfinite(wb[:,mi])]
            ww_estimates[m]=dict(value=float(wp[mi]) if np.isfinite(wp[mi]) else None,
                ci95=np.quantile(good,[.025,.975]).tolist() if len(good) else None,
                numerator=float(wt[mi,0]),denominator=float(wt[mi,1]))
        estimates['WW']=ww_estimates
    result=dict(paired_seeds=count,seed_range=[seeds[0],seeds[-1]],arms=arms,
        config_sha256=hashlib.sha256(config.read_bytes()).hexdigest(),bootstrap=cfg['bootstrap'],
        outcomes=outcomes,estimates=estimates,paired_contrasts=contrasts,latency=latencies,
        attrition=attrs,wait_counts=waits,completed_game_cpu_seconds=cpu_total,
        supplementary_WW=dict(paired_seeds=len(rows['WW']),descriptive=True),
        validation=dict(all_terminal=True,matching_seed_seat_shuffled_decks=True,
                        both_channels_delay27_capacity1=True,no_rejected_commands=True),
        limitations=['fixed-work simulation, public reconstruction and scripted rollout futures',
                     'bootstrap CIs pointwise and unadjusted','loaded SCHED_IDLE wall timing is not live qualification'])
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(outcomes=outcomes,loss_contrasts={k:v['game_loss_fraction'] for k,v in contrasts.items()})),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--smoke',action='store_true');a=p.parse_args();reduce(a.root,a.config,a.out,a.smoke)
