"""Analyze all256 fixed games; incomplete input cannot produce a verdict."""
import hashlib
import json
from pathlib import Path
import numpy as np
from qualify import write
from evaluate import verify_manifest

HERE=Path(__file__).resolve().parent
manifest_path=HERE/'evaluation-manifest.json'
manifest=json.loads(manifest_path.read_text());verify_manifest(manifest)
manifest_sha=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
schedule=json.loads((HERE/'schedule.json').read_text())['pairs']
rows=[]
for ep in schedule:
    for seat in (0,1):
        path=HERE/'confirmation'/f"pair{ep['pair']:03d}-seat{seat}.json"
        row=json.loads(path.read_text());assert row['manifest']==manifest_sha
        for key in ('pair','seed','family','style'):assert row[key]==ep[key],(path,key)
        assert row['seat']==seat
        expected=[ep['planning_deck'],ep['opponent_deck']]
        if seat:expected.reverse()
        assert row['decks']==expected
        rows.append(row)
assert len(rows)==256

def cell(items):
    pairs={}
    for r in items:pairs.setdefault(r['pair'],[]).append(r['score'])
    assert all(len(v)==2 for v in pairs.values())
    means=np.asarray([np.mean(v) for _,v in sorted(pairs.items())])
    rng=np.random.default_rng(40404041)
    samples=means[rng.integers(len(means),size=(10000,len(means)))].mean(axis=1)
    low,high=np.quantile(samples,[.025,.975])
    score=float(np.mean(means))
    return dict(games=len(items),pairs=len(pairs),ability_accepted=sum(v['accepted'] for r in items for v in r['abilities'].values()),wins=sum(r['score']==1 for r in items),draws=sum(r['score']==.5 for r in items),score=score,ci=[float(low),float(high)],pass_gate=score>=.55 and low>.5)

pooled=cell(rows);styles={style:cell([r for r in rows if r['style']==style]) for style in ('balanced','pressure','defense')}
families={family:cell([r for r in rows if r['family']==family]) for family in dict.fromkeys(r['family'] for r in rows)}
timings=np.asarray([t for r in rows for t in r['wall_cpu_search']]);allwall=timings[:,0];searchwall=timings[timings[:,2]==1,0]
abilities={}
for row in rows:
    for name,values in row['abilities'].items():
        target=abilities.setdefault(name,dict(opportunities=0,attempts=0,accepted=0))
        for key,value in values.items():target[key]+=value
result=dict(complete=True,manifest=manifest_sha,pooled=pooled,styles=styles,families=families,
    statistical_pass=pooled['pass_gate'] and styles['defense']['pass_gate'],
    timing=dict(decisions=len(allwall),searches=len(searchwall),p99=float(np.quantile(allwall,.99)),max=float(max(allwall)),search_p99=float(np.quantile(searchwall,.99)),search_max=float(max(searchwall)),overruns=int(sum(allwall>.25)),pass_budget=bool(max(allwall)<=.25)),
    abilities=abilities,rejected=np.asarray([r['rejected'] for r in rows]).sum(axis=0).tolist(),
    derived_checks=sum(r['derived_checks'] for r in rows),hand_determined=sum(r['hand_determined'] for r in rows),cycle_determined=sum(r['cycle_determined'] for r in rows),
    receipts_sha256=hashlib.sha256(b''.join((HERE/'confirmation'/f"pair{r['pair']:03d}-seat{r['seat']}.json").read_bytes() for r in rows)).hexdigest())
write(HERE/'result.json',result)
print(json.dumps(result,indent=2))
