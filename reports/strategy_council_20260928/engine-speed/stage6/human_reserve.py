"""Append the frozen reserve only after every original64+32 game passes."""
import argparse
import hashlib
import json
from pathlib import Path
import traceback
from collections import Counter

import clasher_core
from clasher.rl.contract_v5 import ContractV5ObservationBuilder
from differential import config
from human_cases import game
from stage2 import fingerprint


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prior', type=Path, required=True)
    args=parser.parse_args()
    folder=Path(__file__).resolve().parent
    plan_path=folder/'human64-plan.json'
    plan=json.loads(plan_path.read_text())
    supplement_path=folder/'human128-reserve.json'
    supplement=json.loads(supplement_path.read_text())
    assert supplement['base_plan_sha256']==sha(plan_path)
    for name, expected in plan['sources'].items():
        assert sha(Path(name))==expected, name
    native=Path(clasher_core.__file__).resolve()
    assert native.parent==folder/'native'
    pins=dict(source=fingerprint(),native=sha(native),plan=sha(plan_path),supplement=sha(supplement_path),
              drivers={name:sha(folder/name) for name in ('human_reserve.py','human_cases.py')})
    prior=json.loads(args.prior.read_text())
    assert prior['pins']['source']==pins['source'] and prior['pins']['native']==pins['native']
    assert prior['pins']['plan']==pins['plan']
    assert prior['pins']['drivers']['human_cases.py']==pins['drivers']['human_cases.py']
    assert len(prior['results'])==96 and all(r['ok'] and r['terminal'] for r in prior['results'].values())
    pins['prior_sha256']=sha(args.prior)
    out=dict(pins=pins,required_cards=plan['required_cards'],required_games=64,
             required_imports=1000,required_placements=4000,results=prior['results'])
    if args.output.exists():
        old=json.loads(args.output.read_text())
        assert old['pins']==pins
        out=old
    cards=sorted({card for ep in plan['episodes'] for deck in ep['decks'] for card in deck})
    cfg=config(cards)
    builder=ContractV5ObservationBuilder()
    for ep in supplement['episodes']:
        if ep['id']>=64 and ep['id']%2==0:
            accepted=Counter()
            imports=0
            for row in out['results'].values():
                if row.get('ok'):
                    accepted.update(row['accepted']);imports+=len(row['imports'])
            if imports>=1000 and sum(accepted.values())>=4000 and all(accepted[c]>0 for c in plan['required_cards']):
                break
        key=str(ep['id'])
        if out['results'].get(key,{}).get('ok'): continue
        try:
            result=game(ep,plan['required_cards'],cfg,builder)
        except Exception:
            result=dict(ok=False,kind='exception',episode=ep,traceback=traceback.format_exc())
        assert fingerprint()==pins['source'] and sha(native)==pins['native']
        out['results'][key]=result
        tmp=args.output.with_suffix('.tmp')
        tmp.write_text(json.dumps(out,indent=2)+'\n');tmp.replace(args.output)
        print(key,{k:v for k,v in result.items() if k not in ('actions','python','rust','field_diff','episode','imports')},flush=True)
        if not result['ok']: raise SystemExit(1)
    rows=list(out['results'].values());accepted=Counter()
    for row in rows: accepted.update(row['accepted'])
    imports=sum(len(row['imports']) for row in rows)
    speed=sum(row['python_cpu'] for row in rows)/sum(row['rust_cpu'] for row in rows)
    clone=max(item['clone_us'] for row in rows for item in row['imports'])
    gate=dict(terminal_games=len(rows),imports=imports,placements=sum(accepted.values()),
              missing_cards=[c for c in plan['required_cards'] if not accepted[c]],
              stepping_speedup=speed,clone_us_max=clone)
    gate['passed']=(len(rows)>=64 and imports>=1000 and gate['placements']>=4000
                    and not gate['missing_cards'] and speed>=30 and clone<20)
    out['gate']=gate
    tmp=args.output.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2)+'\n');tmp.replace(args.output)
    print(json.dumps(gate),flush=True)
    if not gate['passed']: raise SystemExit(1)


if __name__=='__main__': main()
