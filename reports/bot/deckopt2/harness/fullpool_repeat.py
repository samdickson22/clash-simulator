"""Replay the same preflight case twice with the approved serial configuration."""
from collections import Counter
import json
import fullpool_eval as fp
from fullpool_worker import configure
from bot.players.royalesim_match import play_match
from bot.search.lopp import FAILURES

D=fp.JOB
fp.MODEL_ROOT=D/'models'
fp.FAST=f'student:{fp.MODEL_ROOT}/fits/f1a2/step-001200.pt'
fp.OLD_FAST=f'student:{fp.MODEL_ROOT}/students/it5s2-step001200.pt@0.5375'
config=json.loads((D/'player-config.json').read_text())
case=json.loads((D/'smoke-case.json').read_text())
rt=fp.runtime(fp.BELIEF);fp.install_placement(rt)
vocab=json.loads((D/'vocab-combined.json').read_text())
results=[]
for repeat in range(2):
    ps=fp.players(rt,fp.LIVE+'-res','R3a',0)
    configure(ps,0,config['players'][1],config)
    before=Counter(FAILURES)
    result=play_match(rt,ps,seed=case['seed'],decks=case['decks'],vocab=vocab,
                      client='16.402',levels=case['levels'],tower_levels=case['tower_levels'],verbose=True)
    errors={str(side):[d for d in getattr(p.rec.inner,'decisions',[]) if 'error' in d or d.get('native_failures')] for side,p in ps.items()}
    failures=dict(Counter(FAILURES)-before)
    unmapped={k:v for k,v in result['translator'].items() if v and ('unmapped' in k or 'missing' in k)}
    diag={str(side):fp.diagnostics(p,result) for side,p in ps.items()}
    result.pop('command_events',None)
    row=dict(utc=fp.utc(),repeat=repeat,result=result,diagnostics=diag,failures=failures,errors=errors,unmapped=unmapped)
    fp.dump(D/f'repeat-{repeat}.json',row)
    assert result['terminal'] and result['channels'][0]['rejected']==0 and not failures and not any(errors.values()) and not unmapped,row
    assert diag['0']['cutoff_hits']==0,diag
    results.append(result)
keys=('command_sha256','state_hash','winner','ticks','crowns','tower_hp')
keys=[k for k in keys if k in results[0]]
assert all(results[0][k]==results[1][k] for k in keys),[(k,results[0][k],results[1][k]) for k in keys]
proof=dict(passed=True,utc=fp.utc(),case_sha256=fp.sha(D/'smoke-case.json'),
           player_config_sha256=fp.sha(D/'player-config.json'),adapter_sha256=fp.sha(fp.ROOT/'fullpool_eval.py'),
           worker_sha256=fp.sha(fp.ROOT/'fullpool_worker.py'),compared_keys=keys,
           command_sha256=results[0]['command_sha256'],runtime_pins=rt.pins,
           row_sha256=[fp.sha(D/f'repeat-{i}.json') for i in range(2)])
fp.dump(D/'repeat-proof.json',proof)
print('SERIAL_REPEAT_PASSED',json.dumps(proof),flush=True)
