"""Pure AST/injected checks; no NumPy/Torch/native/model or scientific data."""
import ast,json,resource,subprocess,sys,time,types
from pathlib import Path

def run(root):
    source=(root/'eval-ops/pool_regret.py').read_text();tree=ast.parse(source)
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='finish_stage1' or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='WORKER_CORES' for t in n.targets)]
    calls=[];reductions=[];fake=types.ModuleType('reduce_stage1');fake.regret=lambda j:reductions.append(j);sys.modules['reduce_stage1']=fake
    env=dict(allowed=lambda j:True,frozen=lambda j:None,os=types.SimpleNamespace(sched_getaffinity=lambda _: {59}),record=lambda *a,**k:calls.append((a,k)))
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
    affinities={1:{56},2:{59}};os_stub=types.SimpleNamespace(sched_getaffinity=lambda pid:affinities[pid],getpriority=lambda *a:10,sched_getscheduler=lambda pid:0,PRIO_PROCESS=0)
    e=dict(Path=lambda _:Proc(),os=os_stub)
    exec(compile(ast.Module(body=[node],type_ignores=[]),'thread admission','exec'),e)
    assert e['thread_ok'](1,set(range(56,60)),10,0);count+=1
    affinities[2]={55};assert not e['thread_ok'](1,set(range(56,60)),10,0);count+=1
    affinities[2]={56,120};assert not e['thread_ok'](1,set(range(56,60)),10,0);count+=1
    os_stub.sched_getscheduler=lambda pid:5;affinities[2]={58};assert not e['thread_ok'](1,set(range(56,60)),10,0);count+=1
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
        receipt=dict(evaluation_freeze_sha256=digest(job/'evaluation-freeze.json'),shared_authority_sha256=digest(job/'REGRET-SHARED-AUTHORITY.json'),evidence_sha256=digest(job/'REGRET-CPU-EVIDENCE.json'),host='127x03',physical_cores=[56,57,58,59],nice=10,scheduler='SCHED_OTHER',maximum_persistent_scientific_processes=4,manager_core=59,worker_cores=[56,57,58],explicit_release=True)
        e=dict(json=json,sha=digest);exec(compile(ast.Module(body=[node],type_ignores=[]),'freeze admission binding','exec'),e)
        put('REGRET-CPU-ADMITTED.json',receipt);e['frozen'](job);count+=1
        for key,bad in [('evaluation_freeze_sha256','stale'),('shared_authority_sha256','wrong'),('evidence_sha256','wrong'),('physical_cores',[0,1]),('nice',19),('maximum_persistent_scientific_processes',8),('worker_cores',[12,13,14]),('explicit_release',False)]:
            v=copy.deepcopy(receipt);v[key]=bad;put('REGRET-CPU-ADMITTED.json',v)
            try:e['frozen'](job)
            except AssertionError:count+=1
            else:raise AssertionError('Forged/stale admission accepted: '+key)
    return count

if __name__=='__main__':
    root=Path(sys.argv[1]);t=time.monotonic();count=run(root);u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN)
    print(json.dumps(dict(passed=True,checks=count,scientific_data_read=False,pid=__import__('os').getpid(),pgid=__import__('os').getpgrp(),cpu_seconds=u.ru_utime+u.ru_stime+v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-t,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip())))
