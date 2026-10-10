"""Audit matched terminal schedules, then paired loss/retention bootstrap."""
import argparse,hashlib,json,subprocess
from collections import Counter
from pathlib import Path
import numpy as np

def timing(values):
    return dict(decisions=len(values),p50_ms=float(np.quantile(values,.5)*1000),p95_ms=float(np.quantile(values,.95)*1000),p99_ms=float(np.quantile(values,.99)*1000),over200_fraction=float(np.mean(np.asarray(values)>.2)))
def estimate(value,samples):
    finite=np.asarray(samples)[np.isfinite(samples)]
    return dict(value=float(value) if np.isfinite(value) else None,ci95=np.quantile(finite,[.025,.975]).tolist() if len(finite) else None,finite_resamples=len(finite))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--roots',nargs='+',type=Path,required=True);ap.add_argument('--config',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--smoke',action='store_true');a=ap.parse_args()
    cfg=json.loads(a.config.read_text());arms=list(cfg['arms']);n=cfg['seed_ranges']['smoke']['count'] if a.smoke else cfg['paired_seeds'];base=cfg['seed_ranges']['smoke' if a.smoke else 'reporting']['base'];seeds=list(range(base,base+n))
    rows={arm:{} for arm in arms};hashes=[];host_counts=Counter();minimum=1000.
    for root in a.roots:
        for path in sorted(root.glob('*/games/*.json')):
            raw=path.read_bytes();r=json.loads(raw);arm=r['cohort'];meta=r['metadata'];seed=meta['seed'];ab=r['search_ab'];spec=cfg['arms'][arm]
            assert seed in seeds and seed not in rows[arm],(arm,seed)
            assert meta['terminal'] and r['role']=='exploration'
            assert meta['delay_ticks']==meta['opponent_delay']==27 and meta['deadline_seconds']==spec['deadline_seconds'] and meta['opponent']=='v1-policy'
            assert len(ab['worker_affinity'])==(5 if spec['threads']==4 else 1)
            assert ab['host'] in ('127x03','127x01') and max(ab['worker_affinity'])<(60 if ab['host']=='127x03' else 40)
            assert set(ab['policy_polls'])=={'0','1'} and all(v==max(0,r['frames']-18) for v in ab['policy_polls'].values())
            for k in ('channel','opponent_channel'):
                q=meta[k];assert q['submitted']==q['executed']+q['pending_at_end'] and q['peak_pending']<=1
            ds=ab['deadline_stats'];wall=ab['latency_seconds']
            assert not ds if spec['deadline_seconds'] is None else len(ds)==len(wall)
            compact=dict(loss=r['loss'],win=meta['winner']==meta['seat'],draw=meta['winner'] is None,metadata=meta,
                wall=wall,cpu=ab['cpu_latency_seconds'],fallback=sum(x['fallback'] for x in ds),cutoff=sum(x['hit'] for x in ds),deadline_decisions=len(ds),game_cpu=r['cpu_seconds'],host=ab['host'])
            rows[arm][seed]=compact;hashes.append(hashlib.sha256(raw).hexdigest());host_counts[ab['host']+':'+arm]+=1
        for path in root.glob('*/supervisor-exit.json'):
            e=json.loads(path.read_text());assert e['returncode']==0;minimum=min(minimum,e['min_memavailable_GiB'])
    for arm in arms:assert set(rows[arm])==set(seeds),(arm,len(rows[arm]),n)
    for seed in seeds:
        first=rows[arms[0]][seed]
        for arm in arms[1:]:
            row=rows[arm][seed]
            assert all(row['metadata'][k]==first['metadata'][k] for k in ('seed','seat','own_deck','opponent_deck'))
            if not a.smoke:assert row['host']==first['host']
    if not a.smoke:
        schedule=Counter((tuple(sorted(r['metadata']['own_deck'])),tuple(sorted(r['metadata']['opponent_deck'])),r['metadata']['seat']) for r in rows['K0'].values())
        assert len(schedule)==50 and set(schedule.values())=={12}
    loss=np.array([[rows[arm][s]['loss'] for arm in arms] for s in seeds]);point=loss.mean(axis=0)
    idx=np.random.default_rng(cfg['bootstrap']['seed']).integers(n,size=(cfg['bootstrap']['reps'],n));boots=loss[idx].mean(axis=1)
    outcomes={};contrasts={};retention={};latency={};fallback={};cutoffs={};gamecpu={}
    control=arms.index('K0');ceiling=arms.index('KU');denom=point[control]-point[ceiling];bootdenom=boots[:,control]-boots[:,ceiling]
    for ai,arm in enumerate(arms):
        vals=[rows[arm][s] for s in seeds];outcomes[arm]=dict(wins=sum(v['win'] for v in vals),losses=int(sum(v['loss'] for v in vals)),draws=sum(v['draw'] for v in vals),loss=estimate(point[ai],boots[:,ai]))
        contrasts[arm]=estimate(point[ai]-point[control],boots[:,ai]-boots[:,control])
        with np.errstate(divide='ignore',invalid='ignore'):
            retention[arm]=estimate((point[control]-point[ai])/denom if denom else float('nan'),(boots[:,control]-boots[:,ai])/bootdenom)
        wall=[x for v in vals for x in v['wall']];cpu=[x for v in vals for x in v['cpu']];latency[arm]=dict(wall=timing(wall),cpu=timing(cpu));gamecpu[arm]=sum(v['game_cpu'] for v in vals)
        for field,target in [('fallback',fallback),('cutoff',cutoffs)]:
            nums=np.array([v[field] for v in vals]);dens=np.array([v['deadline_decisions'] for v in vals])
            # KU has no deadline/fallback path: use its decision calls as denominator.
            if cfg['arms'][arm]['deadline_seconds'] is None:dens=np.array([len(v['wall']) for v in vals])
            else:dens=np.array([v['deadline_decisions'] for v in vals])
            bootnum=nums[idx].sum(axis=1);bootdens=dens[idx].sum(axis=1)
            target[arm]=dict(**estimate(nums.sum()/dens.sum(),bootnum/bootdens),numerator=int(nums.sum()),denominator=int(dens.sum()))
    advance=[] if a.smoke else [arm for arm in cfg['decision_rules']['advance_arms'] if contrasts[arm]['ci95'][1]<=-.10]
    lo,hi=contrasts['K4']['ci95'];kill=None if a.smoke else lo<=0<=hi
    result=dict(reduced_at_utc=subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip(),freeze_commit='0f2a9ec8',plan_sha256=hashlib.sha256(a.config.read_bytes()).hexdigest(),paired_seeds=n,terminal_games=n*len(arms),smoke=a.smoke,outcomes=outcomes,loss_change_vs_K0=contrasts,retention=retention,fallback=fallback,cutoff=cutoffs,latency=latency,advance_arms=advance,kill_anytime_W=kill,bootstrap=cfg['bootstrap'],game_cpu_seconds=gamecpu,host_arm_counts=dict(host_counts),min_memavailable_GiB=minimum,raw_game_hash_union_sha256=hashlib.sha256(''.join(sorted(hashes)).encode()).hexdigest(),audits=dict(terminal=True,paired_decks_seats=True,policy_cadence=True,affinity=True,capacity_one=True,balanced_25matchups=not a.smoke,paired_same_host=not a.smoke))
    a.out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(terminal_games=result['terminal_games'],outcomes=outcomes,advance=advance,kill_anytime_W=kill)))
if __name__=='__main__':main()
