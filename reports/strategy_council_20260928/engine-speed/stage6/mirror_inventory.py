"""Inventory the oracle's actual Mirror acceptance without deploying or editing it."""
import json
from pathlib import Path
from c56_controller import CARDS
from differential import initial
from clasher.dynamic_spells import create_spell_from_json
from clasher.spells import SPELL_REGISTRY

s=Path(__file__).resolve().parent
scope=json.loads((s/'scope.json').read_text())
plan=json.loads((s/'human64-plan.json').read_text())
cards=sorted(set(CARDS)|set(plan['required_cards']))
b=initial(cards=('Mirror','Knight','Zap','Archers'))
rows=[]
for name in cards:
    if name=='Mirror': continue
    stats=b.card_loader.get_card(name)
    b.players[0].last_played_card=name
    b.players[0].last_played_card_cost=stats.mana_cost
    result=b.resolve_card_play(0,'Mirror')
    row=dict(card=name,accepted_resolution=result is not None)
    if result is None and name in SPELL_REGISTRY:
        try: create_spell_from_json(stats._raw_entry,level=12)
        except ValueError as error: row['reason']=str(error)
    rows.append(row)
path=s/'mirror-oracle-inventory.json';assert not path.exists()
path.write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(dict(total=len(rows),rejected=[r for r in rows if not r['accepted_resolution']])),flush=True)
