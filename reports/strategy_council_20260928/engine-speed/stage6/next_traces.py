"""Retain unchanged-source phase reductions for the next missing mechanics."""
import json
from pathlib import Path
from stage2 import focused_case,fingerprint
from differential import CARDS,config

folder=Path(__file__).resolve().parent
for card,tick in (('Bowler',240),('EliteArcher',104),('GoldenKnight',1948)):
    cfg=config((*CARDS,card));trace=focused_case(card,0,cfg,trace_tick=tick)
    path=folder/f'{card}-phase{tick}-r14.json'
    assert not path.exists();path.write_text(json.dumps(dict(source=fingerprint(),trace=trace),indent=2)+'\n')
    print(card,[(phase,scene['field_diff'][:6]) for phase,scene in trace.items()],flush=True)
