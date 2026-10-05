"""Seal final private-build receipts without admitting an incomplete controller roster."""
import argparse
import hashlib
import json
from pathlib import Path
import re

import clasher_core
from controller import CONTROLLER_CARDS, BLOCKED_CONTROLLER_CARDS
from stage2 import fingerprint


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--human',required=True)
    parser.add_argument('--planner',required=True)
    parser.add_argument('--controls',required=True)
    parser.add_argument('--build',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    f=Path(__file__).resolve().parent;root=f.parents[3]
    files=[f/(args.human+'.json'),f/(args.planner+'.json')]
    human,planner=[json.loads(p.read_text()) for p in files]
    native=Path(clasher_core.__file__).resolve();assert native.parent==f/'native'
    pins=dict(source=fingerprint(),native=sha(native))
    for data in (human,planner):
        assert all(data['pins'][k]==v for k,v in pins.items())
        assert all(row['ok'] for row in data['results'].values())
    assert human['gate']['passed']
    assert len(planner['results'])==100
    assert all(len(r['candidates'])>1 for r in planner['results'].values())
    labels=[args.human,args.planner,args.controls,'final-r42-tests','c56-final-r42','earlier-final-r42','skeleton-reduced-r42','skeleton-edges-r42c','planner-suite-r42c']
    for label in labels:
        p=f/(label+'.exit');assert p.read_text().strip()=='0',label;files.append(p)
    controls=f/(args.controls+'.log');text=controls.read_text()
    counts=[int(n) for n in re.findall(r'Ran (\d+) tests? in ',text)]
    assert counts==[60,88,47],counts
    files.append(controls)
    reference=json.loads((f/'entry.json').read_text())['sha256'];checked=0
    for name,value in reference.items():
        if (name.startswith('src/clasher/') and not name.startswith('src/clasher/vision/')) or name in ('gamedata.json','engine-rs/clasher_core.abi3.so'):
            assert sha(root/name)==value,name;checked+=1
    archive=f/args.build;frozen=json.loads((archive/'pins.json').read_text())
    for name,value in frozen.items():
        if name=='private_native':assert value==pins['native']
        else:assert sha(root/name)==sha(archive/name)==value,name
    cards=[r['canonical'] for r in json.loads((f/'scope.json').read_text())['remaining']]
    blockers=sorted(set(cards)&BLOCKED_CONTROLLER_CARDS)
    assert len(cards)==66 and len(CONTROLLER_CARDS)==65
    files.extend([archive/'pins.json',f/'controller.py',f/'test_ranking.py',f/'test_skeleton_ability.py',f/'test_skeleton_edges.py',f/'final_planner_gate.sh',f/'python-issues.json',Path(__file__)])
    out=dict(status='Private core gates passed; full Stage6 admission blocked by unchanged Python controller exception',
             final_s122_admitted=False,pins=pins,cards=cards,reference_preserved=True,reference_files=checked,
             human=human['gate'],planner_calls=100,planner_candidates=sum(len(r['candidates']) for r in planner['results'].values()),
             planner_cards=sorted({r['card'] for r in planner['results'].values()}),
             regression_methods=dict(stage6=counts[0],c56=counts[1],earlier=counts[2]),
             controller_new_cards=len(CONTROLLER_CARDS),controller_blockers=blockers,
             receipts={str(p.relative_to(f)):sha(p) for p in files})
    assert not args.output.exists();args.output.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k!='receipts'},indent=2))


if __name__=='__main__':main()
