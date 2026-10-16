from pathlib import Path
import json,sys
from bot.deckopt2.run import game,install_compat,dump,source_hashes,utc
from bot.players.runtime import Runtime
from bot.players.royalesim_vocab import load
import instrument
root=Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2')
meta=json.loads((root/'manifest.json').read_text())
assert meta['source_sha256']==source_hashes()
ref=json.loads((root/'replay-reference.json').read_text())
case=next(c for c in json.loads((root/'screen/bank.json').read_text())['cases'] if c['id']==ref['id'])
rt=Runtime();install_compat(rt);instrument.install()
out=root/'replay-observed.json'
game(rt,load(rt),root,'screen',meta,case,ref['candidate'],ref['player'],out)
row=json.loads(out.read_text())
assert 'error'not in row and not row.get('issues'),row
keys=('command_sha256','state_hash','winner','ticks','crowns','towers')
result=dict(checked_utc=utc(),reference_host=ref['host'],replay_host=row['host'],instrumented=True,
            equal={k:ref['result'][k]==row['result'][k] for k in keys},
            reference_command_sha256=ref['result']['command_sha256'],replay_command_sha256=row['result']['command_sha256'],
            public_diagnostics=row['result']['public_diagnostics'])
dump(root/'cross-host-instrument-parity.json',result)
assert all(result['equal'].values()),result
print('Cross-host and passive-instrument parity passed:',result['equal'],flush=True)
