"""Offline development diagnostics; truth is consumed only after belief update."""
import bootstrap
from bootstrap import HERE
import gzip,json,time
from types import SimpleNamespace
import numpy as np
from tracker_v2 import TrackerV2
from cells import CELLS
from clasher.vision.l1_derived_v3 import OpponentPosterior
from evaluate import write

def run(index,round_name):
    cpu=time.process_time()
    with gzip.open(HERE/f'dev-traces/{index:03d}.json.gz','rt') as f:data=json.load(f)
    prior=json.loads((HERE/'runtime/support/human_deck_catalog.json').read_text())
    selection=json.loads((HERE/'runtime/support/selection.json').read_text())
    body_cards={int(k):tuple(tuple(x) for x in v) for k,v in data['body_cards'].items()}
    beliefs={};legacy={};samples={};seen={}
    for s in (0,1):
        for v in ('T2-N97','T2-N90','T2-N64'):
            key=(s,v);c=CELLS[v]
            beliefs[key]=TrackerV2(prior,data['costs'],recall=c['recall'],precision=c['precision'],body_cards=body_cards)
            legacy[key]=OpponentPosterior(data['costs'],particles=1024,missed_plays_per_second=selection['missed_rate'],seed=data['episode']['seed']+100002+s,calibration_residuals=selection['calibration_residuals'])
            samples[key]=[]
    for row in data['rows']:
        key=(row['seat'],row['variant']);b=beliefs[key];old=legacy[key];events=[SimpleNamespace(**e) for e in row['events']]
        b.update_public(row['tick'],events,row['bodies'])
        for e in events:
            if e.kind=='card':old.observe(max(old.tick,e.tick),[SimpleNamespace(player_id=0,card=e.name,event_id=e.event_id,confidence=selection['event_probabilities'].get(e.name,.5))])
        old.advance(row['tick'])
        if row['tick']%20!=10:continue
        d=b.distribution();lo,hi=d['elixir_interval_90'];truth=row['truth_elixir'];ld=old.distribution()
        audit=data['audits'][f'{key[0]}-{key[1]}']
        post=any(0<=row['tick']-(e['truth_tick'] if e['kind']=='missed' else e['arrival_tick'])<=1200 for e in audit if e['kind'] in ('missed','spurious','confused'))
        samples[key].append(dict(tick=row['tick'],truth=truth,mean=d['elixir_mean'],lo=lo,hi=hi,residual=max(lo-truth,truth-hi,0.),post_error=post,legacy=ld,hand90=d['hand90_mass']>=.9))
    out=HERE/f'dev-{round_name}';out.mkdir(exist_ok=True)
    write(out/f'{index:03d}.json',dict(index=index,cpu_seconds=time.process_time()-cpu,samples={f'{s}-{v}':x for (s,v),x in samples.items()},metrics={f'{s}-{v}':dict(b.metrics) for (s,v),b in beliefs.items()}))
    print(json.dumps(dict(index=index,complete=True,cpu_seconds=time.process_time()-cpu)),flush=True)
