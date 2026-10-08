"""Fail-closed formal admission. Counts receipts; never opens heldout payloads."""
import argparse
import hashlib
import json
from pathlib import Path

SPLIT_SHA='3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def admit(state_path,exit_path,source,split_path,registration):
    state=json.loads(state_path.read_text());exit_receipt=json.loads(exit_path.read_text())
    if state.get('stage')!='complete' or exit_receipt.get('code')!=0:raise ValueError('T1 has not completed Phase A successfully')
    if state.get('time',0)<exit_receipt.get('time',1):raise ValueError('T1 completion predates phase exit')
    if digest(split_path)!=SPLIT_SHA:raise ValueError('Frozen split changed')
    if 'clasher-lease' in source.parts:
        staged=json.loads((source/'stage-inventory.json').read_text())
        if staged.get('complete_population') is not True:raise ValueError('Leased source is not the full Phase A population')
        for group in ('receipt_sha256','heldout_receipt_sha256'):
            for episode,expected in staged[group].items():
                if digest(source/episode/'receipt.json')!=expected:raise ValueError('Staged receipt changed')
    seals={}
    for name in ('PREREG','PREREG-AMENDMENT-01','PREREG-AMENDMENT-02','PREREG-AMENDMENT-03'):
        doc=registration/(name+'.md');expected=(registration/(name+'.sha256')).read_text().split()[0]
        if digest(doc)!=expected:raise ValueError('Registration changed after freeze')
        seals[name]=expected
    split=json.loads(split_path.read_text());members={r['seed']:r for r in split['matches']}
    heldout=0;events=0;seen=set();receipts={};emulator_seconds=0.
    for path in sorted(source.glob('*/receipt.json')):
        r=json.loads(path.read_text())
        if r.get('split')=='smoke':continue
        member=members[r['seed']]
        if r['seed'] in seen:raise ValueError('Duplicate completed seed')
        seen.add(r['seed'])
        if (r['split'],r['decks'])!=(member['split'],member['decks']):raise ValueError('Split membership mismatch')
        receipts[str(path)]=digest(path)
        emulator_seconds+=r.get('elapsed_emulator_seconds',0.)
        if r['split']=='heldout':heldout+=1;events+=r['accepted_opponent_events']
    coverage_met=heldout>=20 and events>=1500
    cap_reached=emulator_seconds>=36*3600-380
    if not coverage_met and not cap_reached:raise ValueError('Neither registered collection stopping rule is evidenced')
    return dict(admitted=True,phase_state_sha256=digest(state_path),phase_exit_sha256=digest(exit_path),
                prereg_hashes=seals,split_sha256=SPLIT_SHA,receipts=receipts,heldout_matches=heldout,
                heldout_opponent_event_count=events,heldout_payloads_opened=False,
                emulator_seconds=emulator_seconds,cap_reached=cap_reached,coverage_gate='PASS' if coverage_met else 'FAIL',
                admission_scope='training only; no heldout opening or evaluation gate certification')


def main():
    p=argparse.ArgumentParser();p.add_argument('--phase-state',type=Path,required=True);p.add_argument('--phase-exit',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--split',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=admit(a.phase_state,a.phase_exit,a.source,a.split,Path(__file__).parent)
    with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')

if __name__=='__main__':main()
