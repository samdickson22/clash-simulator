"""Pure AST/mock validation for the future probe; no engine/native execution."""
import ast
import copy
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace


PROBE = Path(__file__).with_name('probe_shared_troop.py')
TREE = ast.parse(PROBE.read_text())


def extract(name, namespace):
    node = next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name==name)
    exec(compile(ast.Module(body=[copy.deepcopy(node)],type_ignores=[]),str(PROBE),'exec'),namespace)
    return namespace[name]


def reject(function):
    try:
        function()
    except AssertionError:
        return
    raise AssertionError('unreached/incorrect witness accepted')


def main():
    witness = extract('require_witness',{})
    def result(*actors):
        return dict(frames=[dict(actor=actor) for actor in actors])
    positive = dict(spirit=True,entity_kind=2,stats=dict(ordinary=False,projectile_slow_multiplier=0.7))
    witness('spirit/uniform',0,result(positive,None))
    reject(lambda:witness('spirit/uniform',0,result(dict(positive,spirit=False),None)))
    reject(lambda:witness('spirit/uniform',0,result(dict(positive,stats=dict(positive['stats'],projectile_slow_multiplier=1)),None)))
    reject(lambda:witness('spirit/uniform',0,result(positive,positive)))
    heading=dict(target=7,facing=[0,-1000])
    witness('heading/coincident',0,result(heading))
    reject(lambda:witness('heading/coincident',0,result(dict(heading,target=None))))
    reject(lambda:witness('heading/coincident',0,result(dict(heading,facing=[0,0]))))
    cleanup=dict(spirit=True,target=None,clock=dict(finish=1))
    witness('cleanup/positive_not_started',0,result(cleanup,None))
    reject(lambda:witness('cleanup/positive_not_started',0,result(dict(cleanup,target=7),None)))
    reject(lambda:witness('cleanup/positive_not_started',0,result(dict(cleanup,clock=dict(finish=0)),None)))
    zap=dict(stun=0.45,frozen_moving=True,route=[1,2,3],dash=dict(phase='travel'))
    witness('zap/frozen',0,result(zap,dict(zap,route=[2,3])))
    reject(lambda:witness('zap/frozen',0,result(dict(zap,stun=0),dict(zap,stun=0,route=[2,3]))))
    reject(lambda:witness('zap/frozen',0,result(zap,zap)))

    class Python:
        tick=0
        def clone(self): return Python()
        def step(self): self.tick+=1

    class Native:
        def __init__(self,raw): self.raw=raw
        def clone(self): return Native(self.raw)
        def snapshot(self): return self.raw
        def step(self,_): raise RuntimeError('synthetic-native-step-error')

    def snapshot(python,*_): return json.dumps(dict(tick=python.tick,entities=[]))
    contract=SimpleNamespace(differences=lambda *args:[])
    namespace=dict(json=json,snapshot=snapshot,D=SimpleNamespace(
        clasher_core=SimpleNamespace(BattleState=Native),battle_digest=lambda python:str(python.tick)))
    continuation=extract('continuation',namespace)
    record={}
    try:
        continuation('synthetic',Python(),{},contract,2,record=record)
    except RuntimeError as error:
        assert str(error)=='synthetic-native-step-error'
    else:
        raise AssertionError('synthetic step did not fail')
    assert record['initial']==dict(tick=0,entities=[])
    assert record['last_before']['python']==dict(tick=0,entities=[])
    assert record['last_before']['native']==dict(tick=0,entities=[])
    assert record['frames']==[] and record['differences']==[]

    # The guard precedes differential import, so this child cannot import/run it.
    opt=subprocess.run([sys.executable,'-O','-B',str(PROBE)],capture_output=True,text=True)
    assert opt.returncode!=0 and 'unoptimized Python is required' in opt.stderr
    assert 'No module named' not in opt.stderr
    print('PASS: source AST/mock witness rejection, partial-failure roots and optimized-Python guard; no actual native/engine run')


if __name__=='__main__':
    main()
