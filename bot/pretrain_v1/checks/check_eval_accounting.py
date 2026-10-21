"""Fixture for Sol R4 #1: 4 assigned cases, only case 0 ran (a win). ITT must keep n=4; complete pairs undefined when a
controller stratum has no valid pair; the run is declared incomplete."""
import json, hashlib, sys, types
from pathlib import Path
sys.path.insert(0, '/mpac/sdicks02/repos/clasher-pretrain-v1/bot/pretrain_v1')
import eval_rsim as E
R2 = E.R2
bank = json.loads((R2/'evaluation/bank.json').read_text())
out = Path('/tmp/pv1-fixture'); (out/'rows').mkdir(parents=True, exist_ok=True)
man = dict(arm='fx', ckpt='x', ckpt_sha256='c'*64, bank_sha256=hashlib.sha256((R2/'evaluation/bank.json').read_bytes()).hexdigest(),
           rows=['HOG26-acct'], feature_hash='f', code_sha256={}, assigned=[0, 1, 200, 201], runtime_pins=E.control_pins([bank['cases'][i] for i in (0,1,200,201)]), external_sha256=E.external_identity())
(out/'manifest.json').write_text(json.dumps(man))
case = bank['cases'][0]
E.setup()
origins = E.module_origins()
row = dict(case, arm='fx', ckpt_sha256=man['ckpt_sha256'], bank_sha256=man['bank_sha256'], score=1.0,
           result=dict(terminal=True), invalid=[], runtime_pins=man['runtime_pins'], module_origins_after=origins)
(out/'rows'/'0000-fx.json').write_text(json.dumps(row))
E.summarise(types.SimpleNamespace(out=str(out), arm='fx'))
s = json.loads((out/'summary-fx.json').read_text())
print('assigned', s['assigned'], 'ran', s['ran'], 'complete', s['complete'], 'not_run', s['candidate_not_run'])
print('itt_lower', s['itt_lower']['n'], s['itt_lower']['delta'], 'complete_pairs', s['complete_pairs'].get('delta'), s['complete_pairs'].get('note'))
assert s['itt_lower']['n'] == 4 and not s['complete'] and s['complete_pairs']['delta'] is None
# negative: a candidate row without runtime pins must abort the summary
bad = dict(row); bad.pop('runtime_pins')
(out/'rows'/'0000-fx.json').write_text(json.dumps(bad))
try:
    E.summarise(types.SimpleNamespace(out=str(out), arm='fx'))
    raise AssertionError('accepted a row without runtime pins')
except SystemExit as ex:
    print('pins check ok:', str(ex)[:80])
# negative: tampered origin evidence (a module outside r2) must abort the summary
bad = dict(row, module_origins_after=dict(origins, **{'bot.players.base': dict(file='/outside/unapproved/bot.py', paths=[])}))
(out/'rows'/'0000-fx.json').write_text(json.dumps(bad))
try:
    E.summarise(types.SimpleNamespace(out=str(out), arm='fx'))
    raise AssertionError('accepted tampered origin evidence')
except SystemExit as ex:
    print('origin check ok:', str(ex)[:90])
# negative: incomplete evidence (a harness module missing) must abort
inc = dict(row, module_origins_after={k: v for k, v in origins.items() if k != 'bot.players.base'})
(out/'rows'/'0000-fx.json').write_text(json.dumps(inc))
try:
    E.summarise(types.SimpleNamespace(out=str(out), arm='fx'))
    raise AssertionError('accepted incomplete origin evidence')
except SystemExit as ex:
    print('completeness check ok:', str(ex)[:90])
