"""Local fixture/process mocks only. Never inspect or signal the running experiment."""
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

P = Path(__file__).parents[3]/'reports/bot/pretrain-v1/sweep/next_eval_expand_05.py'
spec = importlib.util.spec_from_file_location('next_expansion', P)
N = importlib.util.module_from_spec(spec)
spec.loader.exec_module(N)


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    root, snapshot = tmp_path/'root', tmp_path/'snapshot'
    put(snapshot/N.STORE/'MANIFEST.jsonl', {'fixture': '83 frozen batches'})
    put(snapshot/'input.json', {str(i): 'digest' for i in range(83)})
    monkeypatch.setattr(N, 'MANIFEST_SHA', N.X.sha(snapshot/N.STORE/'MANIFEST.jsonl'))
    ready = dict(batches=83, matches=41328, rows=8143577, store_name=N.STORE,
                 manifest_sha256=N.MANIFEST_SHA, input_sha256=N.X.sha(snapshot/'input.json'))
    put(snapshot/'STORE-READY.json', ready)
    put(root/'scaling-read.json', dict(runs={n: dict(status='complete') for n in
                                           ['S25','S50','S100','M25','M50','M100']}))
    put(root/'next-snapshot-bank.json', dict(cases=[dict(index=i) for i in range(1600)]))
    monkeypatch.setattr(N, 'BANK_SHA', N.X.sha(root/'next-snapshot-bank.json'))
    for size, phase, d in [('S100','next-S100',192), ('M','next-M100',320)]:
        anchor = root/'next-anchors'/size
        anchor.mkdir(parents=True)
        (anchor/'anchor.pt').write_bytes(b'weights-'+size.encode())
        selected = str(N.GPU_OUT/phase/'ep02.pt')
        put(anchor/'selection.json', dict(file='anchor.pt', admitted=True, smoke=False, eligible=3,
            sha256=N.X.sha(anchor/'anchor.pt'), selected=selected, seed=2026102001, ep=2,
            selection=dict(eligible=True, ckpt=selected, seed=2026102001, ep=2)))
        put(root/'next-run-receipts'/size/'run.json', dict(rows=8143577, store=str(snapshot/N.STORE),
            schema='clasher.pretrain_v1.bc-run.v1',
            code_sha256={n:N.X.read(P.with_name('next_eval_original.json'))['files']['bot/pretrain_v1/'+n]
                         for n in ('train_bc.py','model.py','featurize.py')},
            feature_hash='ce6e509ee43a2a4a8c484261b5341b9a3f1b0c71a1a77a2024de89a80fa4773d',
            seed=2026102001, cfg=N.registered_config(size),
            args=dict(train_frac=1.0, out=str(N.GPU_OUT/phase), store=str(snapshot/N.STORE),
                      device='cuda', threads=3, max_gpu_hours=64, dev_cap=400000, hog_share=0.5,
                      max_row_exposure=5.0, drop_ages=0.05, seed=2026102001, bs=512, patience=2,
                      epochs=8, eval_every=1, warmup_steps=0,
                      steps_per_epoch=0, lr=3e-4 if size=='S100' else 2e-4,
                      wd=1e-4 if size=='S100' else 0.01, amp='none' if size=='S100' else 'bf16',
                      **{k:v for k,v in N.registered_config(size).items() if k not in ('n_cards','n_bodies')})))
        put(root/'next-run-receipts'/size/'summary.json', dict(best_ep=2, dev_cal={'dev_cal/all/joint_nll':0.35,'dev_cal/all/ece':0.01,
                       'dev_cal/hog/joint_nll':0.3}, gate_bias=0, wall_h=2))
    return root, snapshot


def test_missing_then_atomic_publication(evidence):
    root, snapshot = evidence
    p = snapshot/'STORE-READY.json'
    staged = p.with_suffix('.incoming')
    p.rename(staged)
    assert N.gates(root, snapshot) is None
    staged.rename(p)
    assert set(N.gates(root, snapshot)['selected']) == {'S100', 'M'}
    sel = root/'next-anchors/M/selection.json'
    sel.rename(sel.with_suffix('.incoming'))
    assert N.gates(root, snapshot) is None
    sel.with_suffix('.incoming').rename(sel)
    assert N.gates(root, snapshot)


def test_missing_run_copy_waits(evidence):
    root, snapshot = evidence
    (root/'next-run-receipts/M/run.json').unlink()
    assert N.gates(root, snapshot) is None


@pytest.mark.parametrize('what', ['bank', 'checkpoint', 'provisional', 'snapshot', 'run'])
def test_present_mismatch_fails_closed(evidence, what):
    root, snapshot = evidence
    if what == 'bank':
        (root/'next-snapshot-bank.json').write_text('{}')
    elif what == 'checkpoint':
        (root/'next-anchors/S100/anchor.pt').write_bytes(b'changed')
    elif what == 'provisional':
        p = root/'next-anchors/M/selection.json'
        d = N.X.read(p); d['admitted'] = False; put(p, d)
    elif what == 'snapshot':
        p = snapshot/'STORE-READY.json'; d=N.X.read(p); d['matches']=19410; put(p,d)
    else:
        p=root/'next-run-receipts/M/run.json'; d=N.X.read(p); d['store']='/wrong';put(p,d)
    with pytest.raises(RuntimeError):
        N.gates(root, snapshot)


def test_bad_present_json_and_io_fail_closed(tmp_path, monkeypatch):
    p=tmp_path/'ready.json'; p.write_text('{')
    with pytest.raises(json.JSONDecodeError): N.published(p)
    monkeypatch.setattr(N.X, 'read', lambda p: (_ for _ in ()).throw(PermissionError('denied')))
    with pytest.raises(PermissionError): N.published(p)


def test_unique_exact_parent_and_full_spawn(monkeypatch, tmp_path):
    argv=N.evaluator_argv(tmp_path, tmp_path, 'S100')
    parent=dict(pid=10,ppid=5,argv=[a.encode() for a in argv],state='S',start='123')
    kids=[dict(pid=i+20, ppid=10, argv=parent['argv'],state='S') for i in range(24)]
    monkeypatch.setattr(N,'children',lambda p:[k['pid'] for k in kids])
    assert N.matching_parent([parent]+kids,argv,5) == parent
    for arg in ('--out','--arm','--ckpt','--bank'):
        wrong=argv.copy(); wrong[wrong.index(arg)+1]='wrong'
        assert N.matching_parent([parent]+kids,wrong,5) is None
    assert N.matching_parent([dict(parent,ppid=99)]+kids,argv,5) is None
    assert N.matching_parent([parent]+kids[:23],argv,5) is None
    with pytest.raises(RuntimeError,match='multiple'):
        N.matching_parent([parent,dict(parent,pid=11)]+kids,argv,5)
    # Helpers and shells merely containing the code/out tokens are never targets.
    assert N.matching_parent([dict(parent,argv=[b'bash']+parent['argv'])]+kids,argv,5) is None


def test_durable_intent_before_spawn(tmp_path,monkeypatch):
    ident=dict(pid=99,start='1',boot_id='boot',argv=['controller'])
    monkeypatch.setattr(N,'process_identity',lambda pid:dict(ident,pid=pid))
    events=[]
    real_sync=N.os.fsync
    monkeypatch.setattr(N.os,'fsync',lambda fd:(events.append('fsync'),real_sync(fd))[-1])
    def spawn(*a,**kw):
        assert N.X.read(tmp_path/'S100-intent.json')['binding']=={'frozen':True}
        assert events.count('fsync') >= 2
        assert kw['close_fds']
        events.append('spawn')
        return SimpleNamespace(pid=99,wait=lambda:0)
    monkeypatch.setattr(N.subprocess,'Popen',spawn)
    N.start_phase(tmp_path,'S100',{'frozen':True},{'pid':10},['controller'],tmp_path/'log')
    assert events.index('spawn') >= 2
    with pytest.raises(FileExistsError):
        N.start_phase(tmp_path,'S100',{'frozen':True},{'pid':10},['controller'],tmp_path/'log')
    assert events.count('spawn') == 1


def test_restart_with_surviving_phase_never_duplicates(tmp_path,monkeypatch):
    put(tmp_path/'M-intent.json',dict(binding={'bank':'frozen'},parent={'pid':10}))
    # Sealed rows do not authorize recovery from uncertain child/parent state.
    for complete in (False,True):
        with pytest.raises(RuntimeError,match='uncertain phase intent'):
            N.reuse_phase(tmp_path,'M',{'bank':'frozen'},complete,[])
    monkeypatch.setattr(N,'alive',lambda i:{'state':'S'})
    put(tmp_path/'M-complete.json',dict(binding={'bank':'frozen'},controller={'pid':11,'argv':['controller']},
        intent_sha256=N.X.sha(tmp_path/'M-intent.json')))
    with pytest.raises(RuntimeError,match='surviving controller'):
        N.reuse_phase(tmp_path,'M',{'bank':'frozen'},True,[])


def test_reuse_requires_resumed_parent_and_no_pool(tmp_path,monkeypatch):
    binding={'checkpoint':'hash'}
    put(tmp_path/'M-intent.json',dict(binding=binding,parent={'pid':10}))
    put(tmp_path/'M-complete.json',dict(binding=binding,controller={'pid':11,'argv':['controller']},
        intent_sha256=N.X.sha(tmp_path/'M-intent.json')))
    monkeypatch.setattr(N,'alive',lambda i: {'state':'T'} if i['pid']==10 else None)
    with pytest.raises(RuntimeError,match='parent still stopped'):
        N.reuse_phase(tmp_path,'M',binding,True,[])
    monkeypatch.setattr(N,'alive',lambda i:None)
    with pytest.raises(RuntimeError,match='surviving replacement'):
        N.reuse_phase(tmp_path,'M',binding,True,[dict(argv=[b'controller'])])
    assert N.reuse_phase(tmp_path,'M',binding,True,[])
    with pytest.raises(RuntimeError,match='binding mismatch'):
        N.reuse_phase(tmp_path,'M',{'checkpoint':'wrong'},True,[])


def test_waiter_lock_collision(tmp_path):
    with N.locked(tmp_path/'lock'):
        with pytest.raises(BlockingIOError):
            with N.locked(tmp_path/'lock'): pass


def test_surviving_pool_probe(tmp_path):
    with pytest.raises(RuntimeError,match='live expansion'):
        N.no_pool([dict(pid=42,argv=[b'python',b'/any/expand_eval_05.py'])],tmp_path)
    with pytest.raises(RuntimeError,match='another next-bank waiter'):
        N.no_pool([dict(pid=42,argv=[b'python',str(P).encode()])],tmp_path)


@pytest.mark.parametrize('size',['S100','M'])
def test_done_rows_validate_provenance(tmp_path,size):
    arm='pv1-'+size
    man=dict(arm=arm,ckpt_sha256='ckpt',bank_sha256='bank',runtime_pins={'pin':True})
    case=dict(index=1,id='case')
    ev=SimpleNamespace(same_case=lambda r,c:r['id']==c['id'],origins_valid=lambda o:(o=={'approved':True},None))
    row=dict(case,arm=arm,ckpt_sha256='ckpt',bank_sha256='bank',runtime_pins={'pin':True},
             module_origins_after={'approved':True})
    p=tmp_path/'rows'/f'0001-{arm}.json';put(p,row)
    assert N.rows_complete(tmp_path,man,[case],ev)
    put(p,dict(row,module_origins_after={}))
    with pytest.raises(RuntimeError,match='module provenance'):N.rows_complete(tmp_path,man,[case],ev)
    put(p,dict(row,ckpt_sha256='wrong'))
    with pytest.raises(RuntimeError,match='row provenance'):N.rows_complete(tmp_path,man,[case],ev)
    put(p,dict(row,error='interrupted attempt'))
    assert N.rows_complete(tmp_path,man,[case],ev)
    put(p.with_suffix('.attempt'),dict(pid=123))
    assert not N.rows_complete(tmp_path,man,[case],ev)


@pytest.mark.parametrize('field', ['d','layers','heads','ffn','drop','n_cards','n_bodies'])
def test_wrong_architecture_rejected(evidence,field):
    root,snapshot=evidence
    p=root/'next-run-receipts/S100/run.json'; d=N.X.read(p);d['cfg'][field] = -1;put(p,d)
    with pytest.raises(RuntimeError,match='architecture'): N.gates(root,snapshot)


@pytest.mark.parametrize('field', ['train_frac','bs','epochs','patience','lr','wd','amp','warmup_steps',
                                    'hog_share','max_row_exposure','drop_ages','dev_cap'])
def test_wrong_run_config_rejected(evidence,field):
    root,snapshot=evidence
    p=root/'next-run-receipts/M/run.json';d=N.X.read(p);d['args'][field] = 'wrong';put(p,d)
    with pytest.raises(RuntimeError,match='configuration'): N.gates(root,snapshot)


@pytest.mark.parametrize('what', ['run','selection','epoch_filename','selection_epoch'])
def test_unregistered_path_provenance_rejected(evidence,what):
    root,snapshot=evidence
    sel=root/'next-anchors/S100/selection.json';d=N.X.read(sel)
    if what=='run':
        p=root/'next-run-receipts/S100/run.json';r=N.X.read(p)
        r['args']['out']='/unrelated/run/next-S100';put(p,r)
    elif what=='selection':
        d['selected']='/unregistered/archive/next-S100/ep02.pt'
        d['selection']['ckpt']=d['selected'];put(sel,d)
    elif what=='epoch_filename':
        d['selected']=str(N.GPU_OUT/'next-S100/ep03.pt')
        d['selection']['ckpt']=d['selected'];put(sel,d)
    else:
        d['selection']['ep']=3;put(sel,d)
    with pytest.raises(RuntimeError): N.gates(root,snapshot)


@pytest.mark.parametrize('field,bad', [('best_ep',None),('best_ep',8),('best_ep',True),('wall_h',None),
    ('wall_h',0),('wall_h',float('nan')),('gate_bias',None),('gate_bias',float('inf')),
    ('dev_cal',None),('dev_cal',{}),('dev_cal',{'dev_cal/all/joint_nll':None})])
def test_incomplete_summary_rejected(evidence,field,bad):
    root,snapshot=evidence
    p=root/'next-run-receipts/M/summary.json'; d=N.X.read(p);d[field]=bad;put(p,d)
    with pytest.raises(RuntimeError): N.gates(root,snapshot)


def test_host_guard_is_not_a_waiter_or_controller(tmp_path):
    for script in (str(P),'/code/expand_eval_05.py'):
        guard=dict(pid=777,argv=[b'bash',b'/code/run_guarded.sh',b'/logs/log',b'--',b'/r2/run.sh',script.encode()])
        N.no_pool([guard],tmp_path)
    assert N.python_script([b'/bin/python',b'-B',b'-u',str(P).encode()]) == P.name
    assert N.python_script([b'python',b'-c',str(P).encode()]) is None


@pytest.mark.parametrize('field', ['ckpt','ckpt_sha256','bank_path','bank_sha256','code_sha256','assigned'])
def test_manifest_binding_mismatch_rejected(evidence,monkeypatch,field):
    root,snapshot=evidence;e=N.gates(root,snapshot);size='M';out=root/'next-snapshot/eval-M'
    man=dict(arm='pv1-M',ckpt=e['selected'][size]['checkpoint'],ckpt_sha256=e['selected'][size]['checkpoint_sha256'],
             bank_path=str(root/'next-snapshot-bank.json'),bank_sha256=N.BANK_SHA,code_sha256={'frozen':'source'},
             assigned=list(range(1600)))
    man[field]=[] if field=='assigned' else ('wrong' if field!='code_sha256' else {})
    put(out/'manifest.json',man)
    monkeypatch.setattr(N.X,'validate',lambda *a:(man,[dict(index=i) for i in range(1600)]))
    with pytest.raises(RuntimeError):N.check_manifest(root,root,size,e,{'frozen':'source'})


@pytest.mark.parametrize('expanded',[False,True])
def test_completed_restart_after_original_owner_exit(evidence,monkeypatch,expanded):
    root,snapshot=evidence
    monkeypatch.setattr(N,'ROOT',root);monkeypatch.setattr(N,'SNAPSHOT',snapshot)
    monkeypatch.setattr(N.os,'uname',lambda:SimpleNamespace(nodename='127x05'))
    monkeypatch.setattr(N.os,'getpriority',lambda *a:10)
    sources={'reviewed':'source'}
    monkeypatch.setattr(N,'verify_review',lambda r:sources)
    monkeypatch.setattr(N,'verify_source',lambda o:(root,{}))
    monkeypatch.setattr(N,'verify_original_owner',lambda o:(_ for _ in ()).throw(RuntimeError('owner exited')))
    monkeypatch.setattr(N,'processes',lambda:[])
    monkeypatch.setattr(N,'process_identity',lambda p:dict(pid=p,start='1',boot_id='boot',argv=['waiter']))
    monkeypatch.setattr(N,'alive',lambda i:None)
    reference=root/'reference.json';put(reference,dict(cases=[]))
    ev=SimpleNamespace(external_identity=lambda:{},control_pins=lambda c:{},bank_path=lambda:reference)
    monkeypatch.setattr(N,'load_evaluator',lambda c:ev)
    checked=[]
    def manifest(code,root,size,evidence,expected):
        checked.append(size)
        return dict(external_sha256={},runtime_pins={}),[dict(index=1)]
    monkeypatch.setattr(N,'check_manifest',manifest)
    monkeypatch.setattr(N,'rows_complete',lambda *a:True)
    monkeypatch.setattr(N.subprocess,'Popen',lambda *a,**k:(_ for _ in ()).throw(AssertionError('unexpected spawn')))
    state=root/'next-expansion';state.mkdir()
    for size in ('S100','M'):
        out=root/'next-snapshot'/f'eval-{size}';put(out/'manifest.json',{})
        if expanded:
            binding=N.phase_binding(size,N.gates(root,snapshot),out/'manifest.json',sources,'reviewed')
            put(state/f'{size}-intent.json',dict(binding=binding,parent={'pid':10}))
            put(state/f'{size}-complete.json',dict(binding=binding,controller={'pid':11,'argv':['controller']},
                intent_sha256=N.X.sha(state/f'{size}-intent.json')))
    N.run('reviewed')
    assert checked==['S100','M']


@pytest.mark.parametrize('epoch',[0,7])
def test_zero_based_epoch_boundaries_accepted(evidence,epoch):
    root,snapshot=evidence
    for size,phase in [('S100','next-S100'),('M','next-M100')]:
        p=root/'next-anchors'/size/'selection.json';d=N.X.read(p)
        d['ep']=d['selection']['ep']=epoch
        d['selected']=d['selection']['ckpt']=str(N.GPU_OUT/phase/f'ep{epoch:02d}.pt');put(p,d)
        p=root/'next-run-receipts'/size/'summary.json';d=N.X.read(p);d['best_ep']=epoch;put(p,d)
    assert N.gates(root,snapshot)


def test_impossible_epoch_eight_rejected(evidence):
    root,snapshot=evidence
    p=root/'next-anchors/S100/selection.json';d=N.X.read(p)
    d['ep']=d['selection']['ep']=8
    d['selected']=d['selection']['ckpt']=str(N.GPU_OUT/'next-S100/ep08.pt');put(p,d)
    with pytest.raises(RuntimeError,match='selection epoch'):N.gates(root,snapshot)


@pytest.mark.parametrize('field',['schema','code_sha256','feature_hash'])
def test_wrong_training_source_rejected(evidence,field):
    root,snapshot=evidence
    p=root/'next-run-receipts/M/run.json';d=N.X.read(p);d[field]={} if field=='code_sha256' else 'wrong';put(p,d)
    with pytest.raises(RuntimeError,match='training source'):N.gates(root,snapshot)


def test_control_pins_rechecked_after_final_controller(evidence,monkeypatch):
    root,snapshot=evidence
    monkeypatch.setattr(N,'ROOT',root);monkeypatch.setattr(N,'SNAPSHOT',snapshot)
    monkeypatch.setattr(N.os,'uname',lambda:SimpleNamespace(nodename='127x05'))
    monkeypatch.setattr(N.os,'getpriority',lambda *a:10)
    sources={'reviewed':'source'}
    monkeypatch.setattr(N,'verify_review',lambda r:sources)
    monkeypatch.setattr(N,'verify_source',lambda o:(root,{}))
    monkeypatch.setattr(N,'verify_original_owner',lambda o:{})
    monkeypatch.setattr(N,'processes',lambda:[])
    monkeypatch.setattr(N,'process_identity',lambda p:dict(pid=p,start='1',boot_id='boot',argv=['waiter']))
    monkeypatch.setattr(N,'matching_parent',lambda *a:dict(pid=10,start='1',state='S'))
    monkeypatch.setattr(N.X,'same_process',lambda i:{'state':'S'})
    reference=root/'reference.json';put(reference,dict(cases=[]))
    pins=[{}]
    ev=SimpleNamespace(external_identity=lambda:{},control_pins=lambda c:pins[0],bank_path=lambda:reference)
    monkeypatch.setattr(N,'load_evaluator',lambda c:ev)
    monkeypatch.setattr(N,'check_manifest',lambda *a:(dict(external_sha256={},runtime_pins={}),[dict(index=1)]))
    # Original S100 is complete; M still needs expansion.
    did_expand=[]
    monkeypatch.setattr(N,'rows_complete',lambda out,*a:out.name=='eval-S100' or bool(did_expand))
    for size in ('S100','M'):put(root/'next-snapshot'/f'eval-{size}'/'manifest.json',{})
    def expand(state,size,binding,parent,command,log):
        did_expand.append(size)
        pins[0]={'changed':True}
        put(root/'next-snapshot'/f'eval-{size}'/'expansion-complete.json',{})
        return dict(pid=11,start='1',boot_id='boot',argv=['controller'])
    monkeypatch.setattr(N,'start_phase',expand)
    with pytest.raises(RuntimeError,match='control runtime pins changed during expansion'):
        N.run('reviewed')
    assert did_expand==['M']
    assert not (root/'next-expansion/M-complete.json').exists()
