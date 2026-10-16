"""Preflight the strong opponent's scoped C56 belief with a true log deck."""
from collections import Counter
import json
import fullpool_eval as fp
from fullpool_worker import configure
from bot.players.royalesim_match import play_match
from bot.search.lopp import FAILURES
D=fp.JOB
fp.MODEL_ROOT=D/'models';fp.FAST=f'student:{fp.MODEL_ROOT}/fits/f1a2/step-001200.pt'
fp.OLD_FAST=f'student:{fp.MODEL_ROOT}/students/it5s2-step001200.pt@0.5375'
config=json.loads((D/'player-config.json').read_text());case=json.loads((D/'smoke-case.json').read_text())
rt=fp.runtime(fp.BELIEF);other=fp.runtime('c56')
for r in (rt,other):fp.install_placement(r)
vocab=json.loads((D/'vocab-combined.json').read_text())
ps=fp.players(rt,fp.LIVE,'LIVE-K4CW-r16',0,strong_rt=other)
configure(ps,0,config['players'][0],config)
before=Counter(FAILURES)
result=play_match(rt,ps,seed=case['seed'],decks=case['decks'],vocab=vocab,client='16.402',levels=case['levels'],tower_levels=[6,6],verbose=True)
diag={str(side):fp.diagnostics(p,result) for side,p in ps.items()}
errors={str(side):[d for d in getattr(p.rec.inner,'decisions',[]) if 'error' in d or d.get('native_failures')] for side,p in ps.items()}
failures=dict(Counter(FAILURES)-before)
unmapped={k:v for k,v in result['translator'].items() if v and ('unmapped' in k or 'missing' in k)}
result.pop('command_events',None)
row=dict(utc=fp.utc(),preflight_only=True,result=result,diagnostics=diag,errors=errors,failures=failures,unmapped=unmapped)
fp.dump(D/'strong-smoke-result.json',row)
assert result['terminal'] and result['channels'][0]['rejected']==0 and not any(errors.values()) and not failures and not unmapped,row
assert diag['0']['cutoff_hits']==0
print('STRONG_SCOPED_SMOKE_PASSED',fp.utc(),flush=True)
