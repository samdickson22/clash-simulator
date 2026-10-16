"""Bytes of json.dumps(R.config[key]) per top-level key (and the biggest side-table entries) for the selected pins."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from bot.players.runtime import Runtime
rt = Runtime()
C = rt.R.config
sizes = {k: len(json.dumps(v)) for k, v in C.items()}
print(json.dumps(dict(scope=getattr(rt.R, 'card_scope', 'c56'), total=len(json.dumps(C)),
                      non_cards=sum(v for k, v in sizes.items() if k != 'cards'), keys=sizes)))
for k, v in C.items():
    if k != 'cards' and isinstance(v, dict):
        top = sorted(((len(json.dumps(x)), n) for n, x in v.items()), reverse=True)[:6]
        print(k, len(v), top)
