"""Real unmodified E4 pooling over explicitly synthetic committed health fixtures."""
import importlib.util,json,os,shutil,subprocess,time
from pathlib import Path
from common import sha,write
import release_reference as R
import check_reference as C


def make_packet(base):
    source_repo=Path(os.environ.get('T1_E4_REVIEWED_SOURCE_ROOT',Path(__file__).resolve().parents[3]))
    relative='reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3'
    e4=source_repo/relative
    # Require tests to exercise committed E4 bytes, not another owner's draft edits.
    names=[p.name for p in e4.iterdir() if p.suffix in ('.py','.sh') or p.name=='spec-pins.json']
    for name in names:
        assert subprocess.check_output(['git','-C',str(source_repo),'show','HEAD:'+relative+'/'+name])==(e4/name).read_bytes()
    spec=importlib.util.spec_from_file_location('t1_e4_fixture',e4/'tests/test_fleet_contract.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    hosts=['127x01','127x03','127x08']
    bundle,context,plan,end=module.end_fixture(base,hosts=hosts)
    repo=base/'source-repo'
    def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.DEVNULL,text=True).strip()
    git('config','user.name','Synthetic T1 reference test');git('config','user.email','test@example.invalid')
    def commit():
        paths=[str(p.relative_to(repo)) for p in repo.rglob('*') if p.is_file() and '.git' not in p.parts]
        git('add','--',*paths);git('commit','-qm','Synthetic public reference evidence');return git('rev-parse','HEAD')
    def binding(name,revision):return dict(path=name,commit=revision,sha256=sha(repo/name))
    def seal(root,scope):
        files={str(p.relative_to(repo/root)):sha(p) for p in (repo/root).rglob('*') if p.is_file() and p!=repo/root/'receipt-manifest.json'}
        write(repo/root/'receipt-manifest.json',dict(scope=scope,status='complete',files=files))
    first=git('rev-parse','HEAD')
    shutil.copyfile(bundle/'end.json',repo/'end.json')
    amendment=repo/R.AMENDMENT_PATH;amendment.parent.mkdir(parents=True);shutil.copyfile(source_repo/R.AMENDMENT_PATH,amendment)
    checker=repo/'reports/explore/t1/check_reference.py';checker.parent.mkdir(parents=True);shutil.copyfile(Path(__file__).with_name('check_reference.py'),checker)
    measurement=repo/relative;measurement.mkdir(parents=True)
    for name in names:shutil.copyfile(e4/name,measurement/name)
    measurement_files={name:sha(measurement/name) for name in names}
    roots={host:str(repo/'attempts'/host) for host in hosts}
    for path in roots.values():Path(path).mkdir(parents=True)
    write(repo/'attempt-roots.json',dict(schema='clasher.t1.reference-attempt-roots.v1',hosts=roots))
    write(repo/'summary.json',dict(synthetic=True))
    root_commit=commit()
    write(bundle/'corpora.json',dict(synthetic=True))
    context['files']['corpora.json']=sha(bundle/'corpora.json');write(bundle/'tiers-pins.json',context)
    entries=[]
    for host in hosts:
        data=module.host_rows([1.]*3,states=300);directory=Path(roots[host])/'r0';store=module.ReceiptStore(directory,'FLEET-REFERENCE');sets={t:[str(i) for i in range(300)] for t in module.TIERS}
        store.write('fleet-identity.json',dict(host=host,sets=dict(speed=sets),specification=json.loads((measurement/'spec-pins.json').read_text()),
            input_files={'states.pkl':context['files']['states.pkl'],'v1.pt':module.V1_SHA,'R3a.pt':module.STUDENT_SHA,'R3a-calibration.json':module.CALIBRATION_SHA},native_sha256=module.NATIVE_SHA,runtime_files={},measurement_files=measurement_files,
            load_profile=dict(context['reference_load_profile'],host=host),search_cpus=list(range(5)),background_masks=[list(range(5,10))],utc=time.time(),end_kind='counted-reporting',end_evidence_sha256=end['sha256'],counted_hosts=hosts,
            deadline_replay_semantics='committed-copy',nice=10,reporting_plan_sha256=sha(bundle/'plan.json'),corpus_receipt_sha256=sha(bundle/'corpora.json')))
        store.write('fleet-complete.json',dict(repeats=3,completed=True,reporting_load_profile=True,outcome_access=False,live_actions=False,poolable=True,exactness_class='EXACT'))
        store.write('reference-warmup.json',dict(seconds=300.,all_slots_active=True,all_background_slots=1,reference_slot_work={t:300 for t in module.TIERS}))
        store.write('exactness-tiers.json',dict(passes=True,states=125,records=[dict(id=str(i),workers_equal=True,zero_budget_immutable=True,max_relative_difference={t:0. for t in ('K0c','K1','K2','K4')}) for i in range(125)]))
        store.write('belief-exactness.json',dict(passes=True,histories=125,posterior_weights_cumulative_ledger_samples_rng_exact=True,records=[dict(id=str(i),deadline_on=on,exact=True,max_relative_difference=0.) for i in range(125) for on in (False,True)]))
        census=[dict(phase='reference-speed',cpu_clock_mhz_by_processor={str(c):2000. for c in range(10)},per_cpu_idle={str(c):.1 for c in range(10)},reporting_guard=dict(passes=True,rules=module.GUARD_RULES,ssh_family_sample=dict(stop=False))) for _ in range(2)]
        for row in census:store.append('capacity.jsonl',row)
        store.write('guard-admission.json',dict(reporting_guard=dict(passes=True,rules=module.GUARD_RULES,console=dict(positive=False),memavailable_bytes=30*2**30,foreign_compute=[],foreign_active=[],ssh_family_sample=dict(stop=False))))
        for row in module.guard_rows():store.append('guard-blocks.jsonl',row)
        store.write('reporting-mhz-comparison.json',module.compare_mhz(module.host_reporting(end,dict(context['reference_load_profile'],host=host),plan),census,list(range(10)),2))
        forwards={'S':dict(gate=.6,legal=[1],ranks={'1':1.}),'K0c':dict(sample=1,top8=[1],probabilities=[.5],log_probabilities=[-.7]),'K2':None,'K4':None}
        store.write('speed-reference.json',{t:{i:dict(result=dict(action=1,candidates=[1],scores=[1.]),forward=forwards[t],wall_seconds=1.) for i in ids} for t,ids in sets.items()})
        for row in data['speed']:store.append('speed-reference-raw.jsonl',row)
        for row in data['deadlines']:store.append('deadline-reference-raw.jsonl',row)
        store.seal('complete');entries.append(dict(host=host,attempts=[dict(directory=str(directory),manifest_sha256=sha(directory/'receipt-manifest.json'))]))
    write(repo/'descriptor.json',dict(schema='clasher.e4v3.fleet-pool.v2',hosts=entries,context=dict(bundle=str(bundle),manifest_sha256=sha(bundle/'tiers-pins.json'))))
    env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    subprocess.run(C.pool_command(measurement,repo/'descriptor.json',repo/'pool'),env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,check=True)
    check=C.check(repo/'descriptor.json',repo/'pool',measurement,repo/'pool-check.json')
    fleet=json.loads((repo/'pool/fleet_reference.json').read_text());packet=repo/'packet';packet.mkdir()
    for name in ('speed-reference.json','deadline-reference.json'):shutil.copyfile(repo/'pool'/name,packet/name)
    for name in ('golden.json','belief-reference.json','student-reference.json'):write(packet/name,dict(synthetic=True))
    shutil.copyfile(bundle/'corpora.json',packet/'corpus.json')
    registration=dict(fleet_reference=fleet,pooled_reference_manifest_sha256=check['pool_manifest_sha256'],pool_check_sha256=sha(repo/'pool-check.json'),deadline_replay_semantics='committed-copy',corpus_receipt='corpus.json',sets=dict(speed=sets),source_receipts={})
    for entry in entries:
        host=entry['host'];shutil.copytree(Path(entry['attempts'][0]['directory']),packet/'sources'/host)
        registration['source_receipts'][host]=[dict(path=f'sources/{host}/receipt-manifest.json',manifest_sha256=entry['attempts'][0]['manifest_sha256'])]
    write(packet/'registration.json',registration);seal('packet','T1-REGISTRATION')
    final=commit()
    pre=dict(schema='clasher.t1.amendment1-prerelease.v1',amendment=binding(R.AMENDMENT_PATH,root_commit),completion=binding('completion.json',first),end_evidence=binding('end.json',final),descriptor=binding('descriptor.json',final),pool_manifest=binding('pool/receipt-manifest.json',final),registration_manifest=binding('packet/receipt-manifest.json',final),pool_check=binding('pool-check.json',final),attempt_roots=binding('attempt-roots.json',root_commit),measurement_source=dict(commit=final,files=measurement_files))
    release=dict(coordinator_thread='0523ae6f-baa3-4d4e-b233-b392671670db',authorized_at_utc='2026-10-24T12:00:00Z',authorization_message_id='synthetic-only',reason='committed_mac_summary',amendment_1_prerelease=pre,mac_summary_path='summary.json',commit=final,mac_summary_sha256=sha(repo/'summary.json'),reporting_completion_path='completion.json',reporting_completion_sha256=pre['completion']['sha256'],completion_commit=first)
    def recommit(name,value):write(repo/name,value);return binding(name,commit())
    return repo,release,recommit
