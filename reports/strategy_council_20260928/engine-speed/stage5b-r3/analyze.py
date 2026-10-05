"""Require all fixed paired games and unchanged runtime before analysis."""
import hashlib
import json
from pathlib import Path
import numpy as np
from evaluate import verify_manifest
from qualify import write
HERE=Path(__file__).resolve().parent
manifest_path=HERE/'evaluation-manifest.json';manifest=json.loads(manifest_path.read_text());verify_manifest(manifest)
sha=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
for worker in range(3):
    assert (HERE/f'worker{worker}.exit').read_text().strip()=='0'
    done=json.loads((HERE/f'worker{worker}-done.json').read_text());assert done['complete'] and done['manifest']==sha
schedule=json.loads((HERE/'schedule.json').read_text())['pairs'];rows=[];receipt_hash=hashlib.sha256()
for ep in schedule:
    for seat in (0,1):
        p=HERE/'confirmation'/f"pair{ep['pair']:03d}-seat{seat}.json"
        receipt_hash.update(p.read_bytes());row=json.loads(p.read_text())
        assert row['manifest']==sha and row['seat']==seat
        for key in ('pair','seed','mode','family','style'):assert row[key]==ep[key]
        decks=[ep['planning_deck'],ep['opponent_deck']]
        if seat and ep['mode']=='scripts':decks.reverse()
        assert row['decks']==decks
        rows.append(row)
assert len(rows)==384

def cell(items):
    pairs={}
    for r in items:pairs.setdefault(r['pair'],[]).append(r['score'])
    assert all(len(v)==2 for v in pairs.values())
    means=np.asarray([np.mean(v) for _,v in sorted(pairs.items())]);rng=np.random.default_rng(40404043)
    samples=means[rng.integers(len(means),size=(10000,len(means)))].mean(axis=1)
    low,high=np.quantile(samples,[.025,.975]);score=float(means.mean())
    return dict(games=len(items),score=score,ci=[float(low),float(high)],wins=sum(r['score']==1 for r in items),draws=sum(r['score']==.5 for r in items),pass_strength=bool(score>=.47 and low>.42))

def timing(items,key='timings'):
    times=np.asarray([t for r in items for t in r[key]])
    walls=times[:,0];searched=times[times[:,2]==1,0]
    return dict(decisions=len(walls),p99=float(np.quantile(walls,.99)),max=float(walls.max()),search_p99=float(np.quantile(searched,.99)),overruns=int(sum(walls>.25)))
h2h=[r for r in rows if r['mode']=='head-to-head'];scripts=[r for r in rows if r['mode']=='scripts']
result=dict(complete=True,manifest=sha,head_to_head=cell(h2h),scripts=cell(scripts),timing=timing(rows),timing_h2h=timing(h2h),timing_scripts=timing(scripts),baseline_timing=timing(h2h,'baseline_timings'),
    truncations=sum(r['timing']['truncations'] for r in rows),fallbacks=sum(r['timing']['fallbacks'] for r in rows),rejected=np.asarray([r['rejected'] for r in rows]).sum(axis=0).tolist(),derived_checks=sum(r['derived_checks'] for r in rows),receipts_sha256=receipt_hash.hexdigest())
result['pass']=result['head_to_head']['pass_strength'] and result['timing']['overruns']==0
write(HERE/'result.json',result);print(json.dumps(result,indent=2))
