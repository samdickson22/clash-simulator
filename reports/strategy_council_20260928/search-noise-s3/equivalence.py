"""Preflight S2 anchor equivalence, with all outcomes suppressed."""
import bootstrap
from bootstrap import HERE
import json
from evaluate import Resources,game,write
from dev_trace import schedule
from derived_public_state import DerivedPublicState
from cells import CELLS
r=Resources();prior=json.loads((HERE/'runtime/support/human_deck_catalog.json').read_text());r.initial_belief=DerivedPublicState(prior,r.costs)
s=schedule()[0];ep=dict(pair=-1,seed=s['seed'],noise_seed=s['noise_seed'],planning_deck=s['decks'][0],opponent_deck=s['decks'][1],mode='scripts',family=s['family'],style=s['style'])
# In-memory import of sealed S2 Player only; S3 owns the wrapper and cells.
import importlib.util
spec=importlib.util.spec_from_file_location('s2_reference_player',HERE.parent/'search-noise-s2/player.py');ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
import evaluate
original=evaluate.Player;out=[]
for cell in ('Full-N97','R-derived','ELT-N97'):
 evaluate.Player=original;a=game(r,prior,ep,0,cell,trace_enabled=False)
 evaluate.Player=ref.Player;b=game(r,prior,ep,0,cell,trace_enabled=False)
 for key in ('action_sha256','action_count','ticks'):assert a[key]==b[key],(cell,key)
 out.append(dict(cell=cell,passed=True,action_sha256=a['action_sha256'],cpu_seconds=a['cpu_seconds']+b['cpu_seconds']))
write(HERE/'equivalence.json',dict(passed=True,cells=out));print('anchor equivalence passed',flush=True)
