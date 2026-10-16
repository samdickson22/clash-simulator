"""Source-only D1/D2/D3 regression controls; stdlib mocks, never real engines."""
import ast
from collections import deque
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent


def extract(path,name,namespace):
    node=next(node for node in ast.parse(path.read_text()).body if isinstance(node,ast.FunctionDef) and node.name==name)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),namespace)
    return namespace[name]


def reject(call):
    try: call()
    except (AssertionError,KeyError,TypeError): return
    raise AssertionError('invalid causal control accepted')


def first_update_controls():
    path=HERE/'probe_first_update_diagnostic.py'
    namespace=dict(json=json,hashlib=hashlib,traceback=traceback)
    for name in ('control_case','validate_pair','one'): extract(path,name,namespace)
    class Battle:
        def __init__(self,broken=False):
            self.tick=0;self.entities={};self.kill_at=None;self.broken=broken
            self.players=[SimpleNamespace(elixir=10,hand=[],cycle_queue=deque()) for _ in (0,1)]
        def deploy_card(self,side,card,point):
            if card=='Rocket': self.kill_at=4
            else: self.entities[7]=SimpleNamespace(id=7,player_id=side,card_stats=SimpleNamespace(name=card),
                position=point,hitpoints=1000,is_alive=True)
            return True
        def step(self):
            self.tick+=1
            if self.broken and self.tick==2: raise AssertionError('synthetic control step failure')
            if self.kill_at is not None and self.tick==self.kill_at:
                for entity in self.entities.values(): entity.hitpoints=0;entity.is_alive=False
    current={};broken=[False]
    def initial(*args,**kwargs):
        current['battle']=Battle(broken[0]);return current['battle']
    class Native:
        def __init__(self,raw): pass
        def apply_action(self,*args): return True
        def step(self,*args): pass
        def digest(self): return str(current['battle'].tick)
        def snapshot(self): return snapshot(current['battle'],{})
    def snapshot(b,cfg): return json.dumps(dict(tick=b.tick,entities=[dict(id=e.id,hp=e.hitpoints) for e in b.entities.values()]))
    namespace['D']=SimpleNamespace(initial=initial,config=lambda *args:{},
        Position=lambda x,y:SimpleNamespace(x=x,y=y),clasher_core=SimpleNamespace(BattleState=Native),
        snapshot=snapshot,battle_digest=lambda b:str(b.tick),entity=lambda e:dict(stats=dict(name=e.card_stats.name)))
    namespace['A']=SimpleNamespace(FILL=('Knight','Archers'),find=lambda b,side,name:[e for e in b.entities.values()
        if e.is_alive and e.player_id==side and e.card_stats.name==name])
    case=dict(victim=(0,'Tombstone'),setup=[],script=[(0,0,'Tombstone',(4.5,10.5)),(2,1,'Rocket',(4.5,10.5))],end=8)
    with tempfile.TemporaryDirectory(prefix='c1-control-regression-') as temp:
        prefix=Path(temp)/'real'
        real=namespace['one']('script-born/blue',case,prefix)
        good=namespace['one']('script-born/blue',namespace['control_case'](case),prefix.with_name('control'),True)
        assert real['victim_death']==3 and real['victim_observations'][0]['observed_tick']==0
        assert good['victim_death'] is None and good['status']=='CONTROL_COMPLETE'
        pair=dict(real,control=good);namespace['validate_pair'](pair)
        broken[0]=True
        bad=namespace['one']('script-born/blue',namespace['control_case'](case),prefix.with_name('broken-control'),True)
        assert bad['status']=='ERROR' and 'synthetic control step failure' in bad['error']
        reject(lambda:namespace['validate_pair'](dict(real,control=bad)))
        for key,value in (('status','ERROR'),('error','failed'),('completed_ticks',1),('case','other/red'),
                          ('victim',[1,'Tombstone']),('victim_observations',[])):
            altered=copy.deepcopy(good);altered[key]=value
            reject(lambda:namespace['validate_pair'](dict(real,control=altered)))
        for key,value in (('owner',1),('name','Other'),('x',0),('observed_tick',5),('hp',900),('stats_sha256','wrong')):
            altered=copy.deepcopy(good);altered['victim_observations'][0][key]=value
            reject(lambda:namespace['validate_pair'](dict(real,control=altered)))
        altered=copy.deepcopy(good);del altered['victim_death']
        reject(lambda:namespace['validate_pair'](dict(real,control=altered)))


def after_import_controls():
    worker=HERE/'diagnostic_worker.py'
    with tempfile.TemporaryDirectory(prefix='c1-after-import-regression-') as temp:
        job=Path(temp);(job/'output').mkdir()
        expected={'differential':'src/engine-cards/differential.py',
            'clasher.battle':'src/engine-cards/py/src/clasher/battle.py',
            'clasher.entities':'src/engine-cards/py/src/clasher/entities.py',
            'clasher_core':'native/clasher_core.abi3.so',
            'es_common':'src/reports/strategy_council_20260928/engine-speed/es_common.py'}
        for relative in [*expected.values(),'root/gamedata.json','src/probe.py']:
            path=job/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('synthetic module fixture\n')
        file_sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
        manifest=dict(commit='a'*40,files={'engine-cards/py/gamedata.json':file_sha(job/'root/gamedata.json'),'probe.py':file_sha(job/'src/probe.py')})
        (job/'manifest.json').write_text(json.dumps(manifest))
        build=dict(commit=manifest['commit'],manifest_sha256=file_sha(job/'manifest.json'),native_sha256=file_sha(job/expected['clasher_core']))
        (job/'output/build.json').write_text(json.dumps(build))
        def save(path,value):
            with path.open('x') as stream: json.dump(value,stream)
        fake=SimpleNamespace(validate=lambda job:manifest,sha=file_sha,save=save,utc=lambda:'synthetic-utc')
        modules={name:SimpleNamespace(__file__=str(job/relative)) for name,relative in expected.items()}
        original={name:sys.modules.get(name) for name in (*modules,'diagnostic_job')}
        old_argv=sys.argv[:];old_path=sys.path[:];old_env={key:os.environ.get(key) for key in ('C1_DIAG_MANIFEST_SHA256','C1_DIAG_BUILD_SHA256')}
        sys.modules.update(modules);sys.modules['diagnostic_job']=fake
        os.environ['C1_DIAG_MANIFEST_SHA256']=file_sha(job/'manifest.json');os.environ['C1_DIAG_BUILD_SHA256']=file_sha(job/'output/build.json')
        try:
            for index,mode in enumerate(('semantic_fail','partial_result','inventory_error')):
                label='shared'; output=job/'output/shared.json'
                def probe(*args,**kwargs):
                    output.write_text(json.dumps(dict(native_sha256=build['native_sha256'],results=[],status='FOCUSED_FAIL')))
                    raise SystemExit(1)
                checks=[0]
                def validate(job):
                    checks[0]+=1
                    if mode=='inventory_error' and checks[0]>1: raise AssertionError('synthetic source drift')
                    return manifest
                fake.validate=validate
                if mode=='partial_result':
                    def probe(*args,**kwargs):
                        output.write_text('[]');raise AssertionError('synthetic focused partial failure')
                namespace=dict(__file__=str(worker),sys=sys,os=os,Path=Path,json=json,traceback=traceback,runpy=SimpleNamespace(run_path=probe))
                main=extract(worker,'main',namespace)
                sys.argv=[str(worker),str(job),label,str(job/'src/probe.py')]
                assert main()==1
                after=json.loads((job/'output/shared-imports-after.json').read_text())
                result=json.loads((job/'output/shared-worker.json').read_text())
                assert 'clasher_core' in after['modules'] and 'clasher.entities' in after['modules']
                assert result['exit']==1 and result['error']
                if mode=='inventory_error': assert after['identity_errors'] and result['after_identity_errors']
                else: assert not after['identity_errors'],after['identity_errors']
                # Preserve each mock case in its own local temporary subdirectory.
                archive=job/('observed-'+str(index));archive.mkdir()
                for path in (job/'output').glob('shared*'): path.rename(archive/path.name)
        finally:
            for name,value in original.items():
                if value is None: sys.modules.pop(name,None)
                else: sys.modules[name]=value
            sys.argv=old_argv;sys.path[:]=old_path
            for key,value in old_env.items():
                if value is None: os.environ.pop(key,None)
                else: os.environ[key]=value


def main():
    source=HERE.parents[3]/'engine-cards/src'
    definitions=[path for path in source.glob('*.rs') if 'fn recover_ground(' in path.read_text()]
    assert definitions==[source/'dash.rs'],'duplicate recovery definition remains'
    first_update_controls();after_import_controls()
    print('PASS: one shared recovery definition; script-born victims/full causal-control error/identity negatives; failed/partial/drifted probes always retain after-import evidence; AST/stdlib/mocks only')


if __name__=='__main__': main()
