"""Synthetic receipt-only admission regressions; retains every test fixture."""
import argparse,hashlib,json
from pathlib import Path
import formal_guard as guard


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value)+'\n')


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    docs=a.output/'registration';docs.mkdir()
    for name in ('PREREG','PREREG-AMENDMENT-01','PREREG-AMENDMENT-02','PREREG-AMENDMENT-03'):
        q=docs/(name+'.md');q.write_text('Synthetic test registration, not the actual frozen document.\n')
        (docs/(name+'.sha256')).write_text(guard.digest(q)+'\n')
    state=a.output/'state.json';exit_path=a.output/'exit.json'
    write(state,dict(stage='complete',time=2));write(exit_path,dict(code=0,time=1))
    def case(name,n,events,seconds):
        root=a.output/name;source=root/'matches';split=root/'split.json'
        members=[dict(seed=i,split='heldout',decks=[['Knight'],['Zap']]) for i in range(n)]
        write(split,dict(matches=members));guard.SPLIT_SHA=guard.digest(split)
        for row in members:write(source/str(row['seed'])/'receipt.json',dict(row,accepted_opponent_events=events,elapsed_emulator_seconds=seconds/n))
        write(source/'stage-inventory.json',dict(complete_population=True,receipt_sha256={},
              heldout_receipt_sha256={str(row['seed']):guard.digest(source/str(row['seed'])/'receipt.json') for row in members}))
        return lambda:guard.admit(state,exit_path,source,split,docs)
    covered=case('covered',20,75,1000)();assert covered['coverage_gate']=='PASS'
    capped=case('capped',1,1,129300)();assert capped['coverage_gate']=='FAIL' and capped['cap_reached']
    fail=case('neither',1,1,1000)
    try:fail()
    except ValueError as e:assert 'Neither' in str(e)
    else:raise AssertionError('Premature completion admitted')
    write(state,dict(stage='phase-a',time=2))
    try:fail()
    except ValueError as e:assert 'not completed' in str(e)
    else:raise AssertionError('Running producer admitted')
    assert covered['heldout_payloads_opened'] is False and capped['heldout_payloads_opened'] is False
    result=dict(pass_=True,checks=5,fixtures=str(a.output),actual_prereg_modified=False,heldout_payloads_opened=False)
    (a.output/'complete.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)


if __name__=='__main__':main()
