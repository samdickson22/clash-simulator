"""Pure AST/injected checks; no NumPy/Torch/native/model or scientific data."""
import ast,json,resource,subprocess,sys,time,types
from pathlib import Path

def run(root):
    source=(root/'eval-ops/pool_regret.py').read_text();tree=ast.parse(source)
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='finish_stage1' or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='WORKER_CORES' for t in n.targets)]
    calls=[];reductions=[];fake=types.ModuleType('reduce_stage1');fake.regret=lambda j:reductions.append(j);sys.modules['reduce_stage1']=fake
    env=dict(allowed=lambda j:True,frozen=lambda j:None,os=types.SimpleNamespace(sched_getaffinity=lambda _: {58}),record=lambda *a,**k:calls.append((a,k)))
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'pool orchestration','exec'),env)
    assert env['WORKER_CORES']==(56,57,58);count=1
    class Job:
        def __truediv__(self,other):return types.SimpleNamespace(exists=lambda:False)
    j=Job()
    for complete,failures,stopping in [(list(range(63)),[],False),(list(range(63))+[62],[],False),(list(range(64)),[{'exit_code':1}],False),(list(range(64)),[],True)]:
        try:env['finish_stage1'](j,complete,failures,stopping)
        except AssertionError:count+=1
        else:raise AssertionError('Incomplete/duplicate/failed/stopped replay reduced')
    assert not calls and not reductions
    env['finish_stage1'](j,list(range(64)),[],False);assert reductions==[j] and len(calls)==1;count+=1
    guard=ast.parse((root/'eval-ops/regret_admission.py').read_text());node=next(n for n in guard.body if isinstance(n,ast.FunctionDef) and n.name=='thread_ok')
    fake_path=types.SimpleNamespace(__truediv__=None)
    class Proc:
        def __truediv__(self,_):return self
        def iterdir(self):return [types.SimpleNamespace(name='1'),types.SimpleNamespace(name='2')]
    affinities={1:{56},2:{58}};os_stub=types.SimpleNamespace(sched_getaffinity=lambda pid:affinities[pid],getpriority=lambda *a:19,sched_getscheduler=lambda pid:0,PRIO_PROCESS=0)
    e=dict(Path=lambda _:Proc(),os=os_stub)
    exec(compile(ast.Module(body=[node],type_ignores=[]),'thread admission','exec'),e)
    assert e['thread_ok'](1,set(range(56,59)),19,0);count+=1
    affinities[2]={55};assert not e['thread_ok'](1,set(range(56,59)),19,0);count+=1
    affinities[2]={56,120};assert not e['thread_ok'](1,set(range(56,59)),19,0);count+=1
    os_stub.sched_getscheduler=lambda pid:5;affinities[2]={58};assert not e['thread_ok'](1,set(range(56,59)),19,0);count+=1
    # Dynamic admission is a receipt of the freeze; pinning its old bytes in
    # that same freeze causes a circular/stale pin. Bind it semantically instead.
    import tempfile,hashlib,copy
    node=next(n for n in guard.body if isinstance(n,ast.FunctionDef) and n.name=='frozen')
    with tempfile.TemporaryDirectory() as folder:
        job=Path(folder)
        digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        def put(name,value):(job/name).write_text(json.dumps(value))
        put('REGRET-SHARED-AUTHORITY.json',{'grant':'unchanged'})
        put('REGRET-CPU-EVIDENCE.json',{'drain':'unchanged'})
        put('payload.json',{'pinned':True})
        put('evaluation-freeze.json',{'files':{'payload.json':digest(job/'payload.json')},'regret_files':{}})
        put('evaluation-prelaunch.json',{'pushed':True,'secret_scan_passed':True,'evaluation_freeze_sha256':digest(job/'evaluation-freeze.json')})
        receipt=dict(evaluation_freeze_sha256=digest(job/'evaluation-freeze.json'),shared_authority_sha256=digest(job/'REGRET-SHARED-AUTHORITY.json'),evidence_sha256=digest(job/'REGRET-CPU-EVIDENCE.json'),host='127x03',physical_cores=[56,57,58],nice=19,scheduler='SCHED_OTHER',maximum_persistent_scientific_processes=4,manager_core=58,worker_cores=[56,57,58],explicit_release=True)
        e=dict(json=json,sha=digest);exec(compile(ast.Module(body=[node],type_ignores=[]),'freeze admission binding','exec'),e)
        put('REGRET-CPU-ADMITTED.json',receipt);e['frozen'](job);count+=1
        for key,bad in [('evaluation_freeze_sha256','stale'),('shared_authority_sha256','wrong'),('evidence_sha256','wrong'),('physical_cores',[0,1]),('nice',10),('maximum_persistent_scientific_processes',8),('worker_cores',[12,13,14]),('manager_core',59),('explicit_release',False)]:
            v=copy.deepcopy(receipt);v[key]=bad;put('REGRET-CPU-ADMITTED.json',v)
            try:e['frozen'](job)
            except AssertionError:count+=1
            else:raise AssertionError('Forged/stale admission accepted: '+key)
    node=next(n for n in guard.body if isinstance(n,ast.FunctionDef) and n.name=='validate_seal')
    with tempfile.TemporaryDirectory() as folder:
        job=Path(folder);(job/'regret').mkdir();p=job/'regret/game.json';stream=p.with_suffix('.jsonl');stream.write_text('sealed stream')
        r=dict(complete=True,command_exact=True,evaluation_freeze_sha256='old',jsonl_sha256=digest(stream));p.write_text(json.dumps(r))
        freeze=dict(retained_regret_seals={'regret/game.json':dict(evaluation_freeze_sha256='old',seal_sha256=digest(p),jsonl_sha256=digest(stream))})
        (job/'evaluation-freeze.json').write_text(json.dumps(freeze));e=dict(json=json,sha=digest);exec(compile(ast.Module(body=[node],type_ignores=[]),'retained complete seals','exec'),e)
        e['validate_seal'](job,p,r);count+=1
        stream.write_text('altered stream')
        try:e['validate_seal'](job,p,r)
        except AssertionError:count+=1
        else:raise AssertionError('Altered retained stream accepted')
        stream.write_text('sealed stream');p.write_text(json.dumps({**r,'complete':False}))
        try:e['validate_seal'](job,p,r)
        except AssertionError:count+=1
        else:raise AssertionError('Altered retained seal accepted')
        p.write_text(json.dumps(r));(job/'evaluation-freeze.json').write_text(json.dumps(dict(retained_regret_seals={})))
        try:e['validate_seal'](job,p,r)
        except KeyError:count+=1
        else:raise AssertionError('Unpinned old seal accepted')
    prior=ast.parse((root/'metadata/metadata-helper/prior-regret_admission.py').read_text())
    import copy
    original=copy.deepcopy(next(n for n in prior.body if isinstance(n,ast.FunctionDef) and n.name=='allowed'))
    instrumented=copy.deepcopy(next(n for n in guard.body if isinstance(n,ast.FunctionDef) and n.name=='allowed'))
    class RemoveDiagnostics(ast.NodeTransformer):
        def visit_Return(self,n):
            if isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='_deny':n.value=ast.Constant(value=False,kind=None)
            return n
        def visit_ExceptHandler(self,n):
            n.name=None;self.generic_visit(n);return n
    instrumented=RemoveDiagnostics().visit(instrumented)
    g_test=ast.parse("str(G)+'/' in cmd",mode='eval').body
    original_g=next(n for n in ast.walk(original) if isinstance(n,ast.If) and ast.dump(n.test)==ast.dump(g_test))
    amended_g=next(n for n in ast.walk(instrumented) if isinstance(n,ast.If) and ast.dump(n.test)==ast.dump(original_g.test))
    old_condition=original_g.body[0].test;condition=amended_g.body[0].test
    assert isinstance(condition,ast.BoolOp) and isinstance(condition.op,ast.Or) and len(condition.values)==2
    expected=ast.parse("not (pgid==a['g_pgid'] or known_g_metadata(raw,a))",mode='eval').body
    assert ast.dump(condition.values[0])==ast.dump(expected) and ast.dump(condition.values[1])==ast.dump(old_condition.values[1])
    expression=compile(ast.Expression(body=condition),'G metadata scope','eval')
    for recognized,thread_valid,group,denied in [(False,True,999,True),(True,False,999,True),(True,True,999,False),(False,False,1,True)]:
        e=dict(pgid=group,a={'g_pgid':1},raw=b'snapshot',pid=999,known_g_metadata=lambda *_:recognized,thread_ok=lambda *_:thread_valid,os=types.SimpleNamespace(SCHED_IDLE=5))
        assert eval(expression,e)==denied;count+=1
    amended_g.body[0].test=copy.deepcopy(old_condition)
    body=instrumented.body[1].body
    assert isinstance(body[-3],ast.Assign) and body[-3].targets[0].id=='valid'
    body[-3:]=[ast.Return(value=body[-3].value)]
    assert ast.dump(original,include_attributes=False)==ast.dump(instrumented,include_attributes=False),'Admission predicates changed';count+=1
    node=next(n for n in guard.body if isinstance(n,ast.FunctionDef) and n.name=='_deny')
    import os
    with tempfile.TemporaryDirectory() as folder:
        job=Path(folder);(job/'metadata').mkdir()
        e=dict(Path=Path,json=json,hashlib=__import__('hashlib'),os=os,time=time,subprocess=subprocess,_conflicts=[],context=lambda:dict(host='127x03',affinity=[58],nice=19,scheduler=0))
        exec(compile(ast.Module(body=[node],type_ignores=[]),'fail-closed diagnostics','exec'),e)
        assert e['_deny'](job,'injected pressure',dict(available=30*2**30,avg10=11)) is False
        receipts=list((job/'metadata/guard-failures').glob('*.json'));assert len(receipts)==1
        denial=json.loads(receipts[0].read_text());assert denial['reason']=='injected pressure' and denial['PSI_full_avg10']==11 and denial['diagnostic_only'] and not denial['scientific_data_read'];count+=1
        class Unwritable:
            def __new__(cls,*a,**kw):raise OSError('injected unavailable diagnostic')
        e['Path']=Unwritable;assert e['_deny'](job,'unwritable metadata',{}) is False;count+=1
    node=next(n for n in guard.body if isinstance(n,ast.FunctionDef) and n.name=='known_g_metadata')
    with tempfile.TemporaryDirectory() as folder:
        G=Path(folder);p=G/'utilization-remote.py';p.write_text('readonly snapshot fixture');raw=b'python3\0'+str(p).encode()+b'\0snapshot\0'
        e=dict(G=G,hashlib=__import__('hashlib'),sha=digest);exec(compile(ast.Module(body=[node],type_ignores=[]),'pinned snapshot helper','exec'),e)
        a=dict(g_metadata_snapshot=dict(source_relative='utilization-remote.py',source_sha256=digest(p),command_sha256=__import__('hashlib').sha256(raw).hexdigest()))
        assert e['known_g_metadata'](raw,a);count+=1
        assert not e['known_g_metadata'](raw.replace(b'snapshot',b'target'),a);count+=1
        p.write_text('altered helper');assert not e['known_g_metadata'](raw,a);count+=1
    return count

if __name__=='__main__':
    root=Path(sys.argv[1]);t=time.monotonic();count=0;passed=False
    try:count=run(root);passed=True
    finally:
        u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN)
        print(json.dumps(dict(passed=passed,checks=count,scientific_data_read=False,pid=__import__('os').getpid(),pgid=__import__('os').getpgrp(),cpu_seconds=u.ru_utime+u.ru_stime+v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-t,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip())))
