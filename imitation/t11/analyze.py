"""C56/S122 cohort gates from sealed statistics only; never runs a policy."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from imitation.model.evaluate import summarize
from imitation.t5.analyze import read_statistics,paired_intervals
from imitation.t5.guards import sha,write_once

SEED=2026100825
METRICS=('joint_nll','play_wait_nll','card_nll','tile_nll')


def analyze(directory,manifest,p16):
    data,receipt=read_statistics(directory)
    assert receipt['T11_manifest']==sha(manifest)
    m=json.loads(Path(manifest).read_text())
    meta_path=Path(directory)/'slice-metadata.json';assert sha(meta_path)==receipt['slice_metadata_sha256']
    metadata=json.loads(meta_path.read_text())['perspectives'];results={}
    for corpus in ('c56','s122'):
        use=data['corpus_s122'].astype(bool)==(corpus=='s122');d={k:v[use] for k,v in data.items()}
        meta={pid:v for pid,v in metadata.items() if v['corpus']==corpus}
        ordered=sorted(meta,key=lambda k:meta[k]['identity']);rank={int(pid):i for i,pid in enumerate(ordered)}
        raw,inverse=np.unique(d['perspective'],return_inverse=True)
        assert set(map(int,meta))==set(map(int,raw)), 'perspective universe missing rows'
        clusters=np.array([rank[int(pid)] for pid in raw])[inverse]
        before={k.split('__')[1]:v for k,v in d.items() if k.startswith('before__')}
        rows={k.split('__')[1]:v for k,v in d.items() if k.startswith('after__')}
        frequency={k.split('__')[1]:v for k,v in d.items() if k.startswith('frequency__')}
        scope=m['card_scope_'+corpus];delta={}
        for key in METRICS:
            assert np.array_equal(np.isfinite(rows[key]),np.isfinite(frequency[key]))
            delta['A1_'+key]=rows[key]-frequency[key]
        for card in scope:delta['A3_'+str(card)]=np.where(rows['label_card']==card,rows['tile_nll']-frequency['tile_nll'],np.nan)
        intervals=paired_intervals(delta,clusters,resamples=10000,seed=SEED)
        a1={k:intervals['A1_'+k] for k in METRICS};cards={str(c):intervals['A3_'+str(c)] for c in scope}
        for item in cards.values():item['significantly_worse']=item['ci95'] is not None and item['ci95'][0]>0
        selected=d['p16'].astype(bool)
        a2=dict(applicable=bool(selected.any()),pass_=None,reason='empty structural P16 slice',details={})
        if selected.any():
            assert corpus=='c56' and p16 is not None
            assert p16['role']==receipt['role'] and p16['release_sha256']==receipt['release_sha256']
            identities=sorted(v['identity'] for v in meta.values() if v['p16'])
            assert identities==p16['identities'] and len(identities)==p16['perspectives']
            expected=p16['metrics']
            for metric,count in [('joint_nll','rows'),('tile_nll','play_rows'),('play_wait_nll','playable_rows')]:
                assert int(np.isfinite(rows[metric][selected]).sum())==int(expected[count])
            for key in ('card_nll','tile_nll'):
                value=float(np.nanmean(rows[key][selected],dtype=np.float64))
                a2['details'][key]=dict(model=value,baseline=expected[key],delta=value-expected[key],pass_=value<=expected[key]+.05)
            a2.update(pass_=all(v['pass_'] for v in a2['details'].values()),reason=None,checkpoint_sha256=p16['checkpoint_sha256'])
        summary=summarize(rows,clusters,resamples=10000,seed=SEED)
        gates=dict(A1=dict(pass_=all(v['ci95'] is not None and v['ci95'][1]<0 for v in a1.values()),details=a1),A2=a2,
            A3=dict(pass_=all(v['n'] and not v['significantly_worse'] for v in cards.values()),
                    passing_cards=sum(bool(v['n'] and not v['significantly_worse']) for v in cards.values()),
                    assessed_cards=sum(bool(v['n']) for v in cards.values()),scoped_cards=len(cards),cards=cards),
            A4=dict(pass_=summary['gate_ece']['ece'] is not None and summary['gate_ece']['ece']<=.01,**summary['gate_ece']))
        def describe(selector):return summarize({k:np.where(selector,v,np.nan) for k,v in rows.items()},clusters,resamples=0,seed=SEED)
        slices={'card':{str(c):describe(rows['label_card']==c) for c in scope},'arena':{}}
        for arena in sorted({m['card_arenas'][str(c)] for c in scope}):
            members=[c for c in scope if m['card_arenas'][str(c)]==arena]
            slices['arena'][arena]=describe(np.isin(rows['label_card'],members))
        for flag in ('battle_healer','mirror'):
            flagged=np.array([meta[str(int(pid))]['flags'][flag] for pid in raw])[inverse]
            slices[flag]={'true':describe(flagged),'false':describe(~flagged)}
        identity=[meta[pid]['identity'] for pid in ordered]
        results[corpus]=dict(perspectives=len(ordered),stored_rows=len(clusters),
            identity_sha256=hashlib.sha256(json.dumps(identity,separators=(',',':')).encode()).hexdigest(),
            before=summarize(before,clusters,resamples=0,seed=SEED),after=summary,gates=gates,slices=slices,
            applicable_gate_pass=all(g['pass_'] is True for k,g in gates.items() if k!='A2' or g['applicable']),
            frequency_means={k:float(np.nanmean(v,dtype=np.float64)) for k,v in frequency.items()})
    all_rows={k.split('__')[1]:v for k,v in data.items() if k.startswith('after__')}
    pooled=summarize(all_rows,data['perspective'],resamples=0,seed=SEED)
    return dict(run=receipt['run'],role=receipt['role'],checkpoint_sha256=receipt['checkpoint_sha256'],
                manifest_sha256=receipt['T11_manifest'],statistics_complete_sha256=sha(Path(directory)/'complete.json'),
                bootstrap=dict(resamples=10000,seed=SEED,rng='PCG64',quantile='linear'),cohorts=results,
                pooled_descriptive=pooled,both_cohorts_pass=all(r['applicable_gate_pass'] for r in results.values()))


def main():
    p=argparse.ArgumentParser();p.add_argument('--statistics',required=True);p.add_argument('--manifest',required=True)
    p.add_argument('--p16');p.add_argument('--output',required=True);a=p.parse_args()
    from .train import frozen
    frozen(Path(__file__).resolve().parents[2],a.manifest)
    baseline=json.loads(Path(a.p16).read_text()) if a.p16 else None
    write_once(a.output,analyze(a.statistics,a.manifest,baseline))


if __name__=='__main__':main()
