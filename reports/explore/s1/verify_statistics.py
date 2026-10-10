"""Independent integer-count verification of the frozen paired loss bootstrap.

Read-only: never replaces the frozen reducer or selects outcomes. Authored while
reporting outcomes remain closed; execute only after all 600 blocks pass.
"""
import argparse,hashlib,json,subprocess
from pathlib import Path
import numpy as np

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--games',type=Path,required=True)
    ap.add_argument('--results',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();cfg=json.loads((Path(__file__).parent/'plan.json').read_text())
    result=json.loads(a.results.read_text());n=cfg['paired_seeds'];base=cfg['seed_ranges']['reporting']['base']
    assert n==600 and result['paired_seeds']==n and result['checks']['games']==3000
    assert not result['smoke_excluded'] and len(list((a.games.parent/'blocks').glob('*.json')))==n
    losses={arm:{} for arm in cfg['arms']}
    for p in a.games.glob('*.json'):
        assert hashlib.sha256(p.read_bytes()).hexdigest()==result['file_shas'][p.name]
        r=json.loads(p.read_text());m=r['metadata'];arm=m['arm'];seed=m['seed']
        assert m['terminal'] and seed not in losses[arm]
        losses[arm][seed]=int(m['winner'] is not None and m['winner']!=m['seat'])
    assert all(sorted(rows)==list(range(base,base+n)) for rows in losses.values())
    arrays={arm:np.array([rows[s] for s in range(base,base+n)],dtype=np.int64) for arm,rows in losses.items()}
    idx=np.random.default_rng(cfg['bootstrap']['seed']).integers(0,n,size=(cfg['bootstrap']['reps'],n))
    counts={arm:x[idx].sum(1,dtype=np.int64) for arm,x in arrays.items()}
    arms={};contrasts={};max_difference=0.
    def check(actual,expected):
        nonlocal max_difference
        delta=float(np.max(np.abs(np.asarray(actual)-np.asarray(expected))))
        max_difference=max(max_difference,delta);assert delta<1e-9,(actual,expected,delta)
    for arm,x in arrays.items():
        point=float(int(x.sum())*100/n)
        interval=(np.percentile(counts[arm],[2.5,97.5])*100/n).tolist()
        assert int(x.sum())==result['arms'][arm]['losses']
        check(point,result['arms'][arm]['loss_pct']);check(interval,result['arms'][arm]['loss_ci_pct'])
        arms[arm]=dict(loss_pct=point,ci95_pct=interval)
    for label,r in result['contrasts'].items():
        left,right=label.split(' minus ')
        point=float(int((arrays[left]-arrays[right]).sum())*100/n)
        interval=(np.percentile(counts[left]-counts[right],[2.5,97.5])*100/n).tolist()
        check(point,r['loss_change_pp']);check(interval,r['ci95_pp'])
        contrasts[label]=dict(loss_change_pp=point,ci95_pp=interval)
    components=[contrasts['S-200 minus K0c-200']['ci95_pp'][1]<=-10,
                contrasts['S-200 minus K2-200']['ci95_pp'][1]<=5]
    consistent=components==result['decision']['component_passes'] and all(components)==result['decision']['viable']
    out=dict(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),
             results_sha256=hashlib.sha256(a.results.read_bytes()).hexdigest(),
             verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             method='Integer paired loss counts; same frozen 5000 resamples/seed/percentiles; scale only after percentile',
             tolerance_pp=1e-9,max_difference_pp=max_difference,arms=arms,contrasts=contrasts,
             mathematical_component_passes=components,decision_consistent=consistent,
             frozen_results_unchanged=True,all_games_sha_verified=True)
    a.out.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k not in ('arms','contrasts')}))
    assert consistent,'Exact inclusive threshold disagrees with frozen floating computation; investigate, never silently relabel'
if __name__=='__main__':main()
