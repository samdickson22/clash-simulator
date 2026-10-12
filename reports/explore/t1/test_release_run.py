"""Offline synthetic fixtures only. No canonical checkout or real game access."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import release_run as driver


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='t1-release-driver-synthetic-')
        self.base = Path(self.temp.name)
        self.ledger = self.base / 'blind.json'
        self.ledger.write_text('{"events": []}')
        self.sidecar = {'utc': 'old', 'schema': 'synthetic', 'blocks': [{'id': 'synthetic-0'}]}
        self.calls = []
        self.directory = self.base / 'private'

    def tearDown(self):
        if self.directory.exists():
            os.chmod(self.directory, 0o700)
        self.temp.cleanup()

    def health(self, root, events, digest):
        self.calls.append('health')
        self.assertEqual(root, self.base)
        self.assertEqual(events, [])
        self.assertEqual(digest, driver.sha(self.ledger))
        return {**self.sidecar, 'utc': 'new'}

    def barrier(self):
        self.calls.append('barrier')

    def reducer(self, output, out, err):
        self.calls.append('reducer')
        # Deliberately sensitive synthetic output, never printed by the wrapper.
        print('SYNTHETIC SECRET stdout')
        emitted = output.with_name(output.name + '.ssh-sensitivity-ledger.json')
        emitted.write_text(json.dumps({**self.sidecar, 'utc': 'newer'}))
        digest = driver.sha(emitted)
        result = {key: {'ledger_sha256': digest} for key in
                  ('ssh_sensitivity', 'apt_sensitivity', 'ssh_or_apt_sensitivity')}
        result['synthetic_secret'] = 'SYNTHETIC SECRET result'
        output.write_text(json.dumps(result))
        return 0

    def run_guard(self, health=None, barrier=None, reducer=None):
        return driver.execute_guarded(self.base, self.ledger, self.sidecar, self.directory,
                                      health or self.health, barrier or self.barrier, reducer or self.reducer)

    def test_matching_except_utc_orders_barrier_before_reducer_and_hides_output(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            record = self.run_guard()
        self.assertEqual(self.calls, ['health', 'barrier', 'reducer'])
        self.assertTrue(record['passes'])
        self.assertNotIn('SECRET', json.dumps(record))
        self.assertEqual(stdout.getvalue(), '')
        self.assertIn('SECRET stdout', (self.directory / 'reducer.stdout').read_text())
        self.assertEqual(self.directory.stat().st_mode & 0o777, 0o700)

    def test_preguard_mismatch_never_invokes_barrier_or_reducer(self):
        with self.assertRaises(driver.ReleaseFailure) as caught:
            self.run_guard(health=lambda *a: {**self.sidecar, 'blocks': []})
        self.assertEqual(self.calls, [])
        self.assertFalse(self.directory.exists())
        self.assertEqual(caught.exception.health['stage'], 'pre_guard')

    def test_health_exception_aborts_before_output_or_game_reader(self):
        def broken(*args):
            raise RuntimeError('SECRET never disclose')
        with self.assertRaises(driver.ReleaseFailure) as caught:
            self.run_guard(health=broken)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.directory.exists())
        self.assertNotIn('SECRET', json.dumps(caught.exception.health))

    def test_barrier_failure_prevents_reducer_and_locks(self):
        def broken():
            self.calls.append('barrier')
            raise ValueError('SECRET')
        self.assert_locked_failure(barrier=broken, stage='barrier')
        self.assertEqual(self.calls, ['health', 'barrier'])

    def assert_locked_failure(self, stage='post_check', **kwargs):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), self.assertRaises(driver.ReleaseFailure) as caught:
            self.run_guard(**kwargs)
        self.assertEqual(stdout.getvalue(), '')
        self.assertEqual(self.directory.stat().st_mode & 0o777, 0)
        self.assertTrue(caught.exception.health['outputs_locked'])
        self.assertEqual(caught.exception.health['stage'], stage)
        self.assertNotIn('SECRET', json.dumps(caught.exception.health))

    def test_reducer_nonzero_locks_stdout_and_output(self):
        def bad(*args):
            self.reducer(*args)
            return 23
        self.assert_locked_failure(reducer=bad, stage='reducer')

    def test_reducer_exception_locks_and_hides_exception_text(self):
        def bad(*args):
            self.reducer(*args)
            raise RuntimeError('SECRET')
        self.assert_locked_failure(reducer=bad, stage='reducer')

    def test_emitted_ledger_difference_locks(self):
        def bad(output, *rest):
            self.reducer(output, *rest)
            output.with_name(output.name + '.ssh-sensitivity-ledger.json').write_text('{"blocks": []}')
            return 0
        self.assert_locked_failure(reducer=bad)

    def test_each_sensitivity_binding_checked(self):
        for key in ('ssh_sensitivity', 'apt_sensitivity', 'ssh_or_apt_sensitivity'):
            with self.subTest(key=key):
                def bad(output, *rest):
                    self.reducer(output, *rest)
                    value=json.loads(output.read_text());value[key]['ledger_sha256']='wrong'
                    output.write_text(json.dumps(value));return 0
                self.assert_locked_failure(reducer=bad)
                os.chmod(self.directory, 0o700)
                # Each subcase has a fresh exclusive destination.
                self.directory = self.base / (key + '-next')

    def test_missing_apt_and_union_both_rejected(self):
        for key in ('apt_sensitivity', 'ssh_or_apt_sensitivity'):
            with self.subTest(key=key):
                def bad(output, *rest):
                    self.reducer(output, *rest)
                    value=json.loads(output.read_text());del value[key]
                    output.write_text(json.dumps(value));return 0
                self.assert_locked_failure(reducer=bad)
                os.chmod(self.directory, 0o700)
                self.directory = self.base / (key + '-next')

    def test_existing_output_directory_is_not_overwritten(self):
        self.directory.mkdir();(self.directory / 'sentinel').write_text('keep')
        with self.assertRaises(driver.ReleaseFailure):
            self.run_guard()
        self.assertEqual((self.directory / 'sentinel').read_text(), 'keep')
        self.assertEqual(self.calls, ['health'])

    def test_real_health_function_reads_only_synthetic_metadata(self):
        from ssh_sensitivity import health_ledger
        block = self.base / 'synthetic-0'
        (block / 'games').mkdir(parents=True)
        (block / 'games/not-json').write_bytes(b'synthetic opaque bytes')
        (block / 'interference.json').write_text('{}')
        (block / 'hub-ack.json').write_text('{}')
        (block / 'complete.json').write_text(json.dumps(dict(
            host='127x08', descriptor=dict(id='synthetic-0', population='primary', cell=0),
            interference={}, interference_sha256=driver.sha(block / 'interference.json'))))
        opened = []
        original = Path.open
        def guarded_open(path, *args, **kwargs):
            self.assertNotIn('games', path.parts)
            opened.append(path)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', guarded_open):
            health = health_ledger(self.base, [], driver.sha(self.ledger))
        self.assertEqual(health['blocks'][0]['id'], 'synthetic-0')
        self.assertIn(block / 'interference.json', opened)
        self.assertIn(block / 'complete.json', opened)


class StrongGuardTests(GuardTests):
    def setUp(self):
        super().setUp()
        self.sidecar.update(sealed=True, blind_ledger_sha256='synthetic-blind', flag_counts={'ssh': 0})
        self.sidecar['blocks'][0]['utc'] = 'nested-fixed'

    def test_all_top_level_keys_and_nested_utc_are_compared_pre_and_post(self):
        for key in ('schema', 'sealed', 'blind_ledger_sha256', 'flag_counts', 'blocks', 'nested_utc'):
            for phase in ('pre', 'post'):
                with self.subTest(key=key, phase=phase):
                    changed=json.loads(json.dumps(self.sidecar))
                    if key=='nested_utc':changed['blocks'][0]['utc']='changed'
                    else:changed[key]='different'
                    if phase=='pre':
                        with self.assertRaises(driver.ReleaseFailure):
                            self.run_guard(health=lambda *a:changed)
                        self.assertFalse(self.directory.exists())
                    else:
                        def bad(output,*rest):
                            self.reducer(output,*rest)
                            emitted=output.with_name(output.name+'.ssh-sensitivity-ledger.json')
                            emitted.write_text(json.dumps(changed))
                            result=json.loads(output.read_text())
                            for k in ('ssh_sensitivity','apt_sensitivity','ssh_or_apt_sensitivity'):
                                result[k]['ledger_sha256']=driver.sha(emitted)
                            output.write_text(json.dumps(result));return 0
                        self.assert_locked_failure(reducer=bad)
                        os.chmod(self.directory,0o700)
                        self.directory=self.base/(key+'-'+phase)

    def test_json_types_are_exact(self):
        with self.assertRaises(driver.ReleaseFailure):
            self.run_guard(health=lambda *a:{**self.sidecar,'sealed':1})

    def test_keyboard_interrupt_locks(self):
        def bad(*args):raise KeyboardInterrupt('SECRET')
        self.assert_locked_failure(reducer=bad,stage='reducer')

    def test_termination_signals_lock(self):
        import signal
        for signum in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):
            with self.subTest(signum=signum):
                def bad(*args):os.kill(os.getpid(),signum)
                self.assert_locked_failure(reducer=bad,stage='reducer')
                os.chmod(self.directory,0o700)
                self.directory=self.base/('signal-'+str(signum))

    def test_symlink_health_proof_refuses_before_health_callback(self):
        block=self.base/'s0';block.mkdir();target=self.base/'target';target.write_text('{}')
        (block/'complete.json').symlink_to(target)
        with self.assertRaises(driver.ReleaseFailure):self.run_guard()
        self.assertEqual(self.calls,[]);self.assertFalse(self.directory.exists())

    def test_interference_symlink_refuses_before_health_callback(self):
        block=self.base/'s0';block.mkdir();(block/'complete.json').write_text('{}')
        target=self.base/'target';target.write_text('{}');(block/'interference.json').symlink_to(target)
        with self.assertRaises(driver.ReleaseFailure):self.run_guard()
        self.assertEqual(self.calls,[]);self.assertFalse(self.directory.exists())

    def test_signal_handlers_restored(self):
        import signal
        previous={s:signal.getsignal(s) for s in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT)}
        def sentinel(*a):pass
        try:
            for s in previous:signal.signal(s,sentinel)
            with driver.terminating_signals():
                self.assertIs(signal.getsignal(signal.SIGTERM),driver.raise_on_signal)
            for s in previous:self.assertIs(signal.getsignal(s),sentinel)
        finally:
            for s,h in previous.items():signal.signal(s,h)

    def test_failure_handler_blocks_signals_before_lock(self):
        import signal
        original=os.chmod
        def checked_chmod(path,mode):
            if mode==0:
                mask=signal.pthread_sigmask(signal.SIG_BLOCK,set())
                self.assertTrue({signal.SIGTERM,signal.SIGHUP,signal.SIGINT} <= mask)
            return original(path,mode)
        with patch.object(os,'chmod',checked_chmod):
            self.assert_locked_failure(reducer=lambda *a:23,stage='reducer')


def synthetic_main_worker(base_string, scenario, reason, pipe):
    """Fork-isolated main tests: all git state, receipts, modules and data synthetic."""
    import subprocess,sys,types,hashlib
    from unittest.mock import patch
    base=Path(base_string);repo=base/'repo';here=repo/'reports/explore/t1'
    here.mkdir(parents=True);(here/'receipts/PC4').mkdir(parents=True)
    root=base/'blocks';root.mkdir();private=base/'outputs';private.mkdir(mode=0o700)
    scratch=base/'scratch';scratch.mkdir()
    (root/'games').mkdir();(root/'games/x').write_text('opaque synthetic sentinel')
    for name in driver.PINS:(here/name).write_text('synthetic '+name)
    (repo/'rename-source').write_text('{"synthetic":"rename"}')
    pins={name:driver.sha(here/name) for name in driver.PINS}
    ledger=here/'receipts/blind-ledger-final-op7-r3.json';ledger.write_text('{"events":[]}')
    side={'utc':'old','schema':'synthetic','sealed':True,'blocks':[{'id':'s0'}]}
    sidepath=here/'receipts/PC4/ssh-sensitivity-pc4-landed.json';sidepath.write_text(json.dumps(side))
    release=base/'release.json';release.write_text(json.dumps({'reason':reason,'mac_summary_path':'summary.json','amendment_1_prerelease':{'synthetic':True}}))
    r5=base/'r5.json';r5.write_text(json.dumps({'amendment_1_prerelease':{'synthetic':True}}))
    cp=base/'copy.json';cp.write_text(json.dumps(dict(destination=str(root),exit_code=0,complete_proofs=3072,verified_game_files=24576,verified_hub_ack=1100,game_parse_or_summary=False,complete_proof_set_sha256='d0f010695064c0b5d397ce8f24afede30a679a571a989daa4e058c1571c23fe0')))
    macsummary=repo/driver.MAC_SUMMARY_PATH;macsummary.parent.mkdir(parents=True)
    macsummary.write_text(json.dumps({'dry_run':False,'feasibility':{t:{'feasible':True} for t in ('K0c','S','K2','K4')}}))
    macseal=repo/driver.MAC_MANIFEST_PATH;macseal.write_text(json.dumps({'status':'complete','files':{'tiers-summary.json':driver.sha(macsummary)}}))
    a3p=repo/driver.MAC_A3P_PATH;a3p.write_text(json.dumps({'outcomes_read':False,'receipt_manifest_sha256':driver.sha(macseal),'tiers':{t:dict(frozen_feasible=True,feasible_after_a3p=True,a3p_passes=True) for t in ('K0c','S','K2','K4')}}))
    if scenario=='a3p_reject':
        value=json.loads(a3p.read_text());value['tiers']['S'].update(feasible_after_a3p=False,a3p_passes=False);a3p.write_text(json.dumps(value))
    if scenario=='a3p_seal_mismatch':
        value=json.loads(a3p.read_text());value['receipt_manifest_sha256']='0'*64;a3p.write_text(json.dumps(value))
    if scenario=='manifest_binding_sha':
        value=json.loads(a3p.read_text());value['receipt_manifest_sha256']='0'*64;a3p.write_text(json.dumps(value))
    if scenario=='summary_other_path':(repo/'alternate-summary.json').write_bytes(macsummary.read_bytes())
    subprocess.run(['git','init','-q',str(repo)],check=True)
    subprocess.run(['git','-C',str(repo),'add','.'],check=True)
    subprocess.run(['git','-C',str(repo),'-c','user.name=Synthetic','-c','user.email=synthetic@example.invalid','commit','-qm','synthetic fixture'],check=True)
    commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    subprocess.run(['git','-C',str(repo),'update-ref',driver.PRIVATE_REF,commit],check=True)
    release.write_text(json.dumps(dict(reason=reason,mac_summary_path=driver.MAC_SUMMARY_PATH,commit=commit,mac_summary_sha256=driver.sha(macsummary),a3p_poll_check=dict(path=driver.MAC_A3P_PATH,commit=commit,sha256=driver.sha(a3p)),mac_receipt_manifest=dict(path=driver.MAC_MANIFEST_PATH,commit=commit,sha256=driver.sha(macseal)),amendment_1_prerelease={'synthetic':True})))
    if scenario in ('a3p_binding_sha','a3p_binding_commit','a3p_binding_path','manifest_binding_sha','summary_other_path'):
        value=json.loads(release.read_text())
        if scenario=='a3p_binding_sha':value['a3p_poll_check']['sha256']='0'*64
        if scenario=='a3p_binding_commit':value['a3p_poll_check']['commit']='0'*40
        if scenario=='a3p_binding_path':value['a3p_poll_check']['path']='other.json'
        if scenario=='manifest_binding_sha':value['mac_receipt_manifest']['sha256']='0'*64
        if scenario=='summary_other_path':value['mac_summary_path']='alternate-summary.json'
        release.write_text(json.dumps(value))
    release_sha=driver.sha(release)
    original_run=subprocess.run;original_git=driver.git;original_popen=subprocess.Popen;original_write=driver.write;original_chmod=os.chmod
    cwd=here
    opts=dict(CANONICAL=repo,BLOCK_ROOT=root,PRIVATE=private,PYTHON=sys.executable,PRIVATE_COMMIT=commit,PINS=pins,BLIND_SHA=driver.sha(ledger),SIDECAR_SHA=driver.sha(sidepath),R5_SHA=driver.sha(r5),COPY_SHA=driver.sha(cp),SCRATCH=scratch)
    checks=[];calls=[]
    def makecheck(tag):
        d=scratch/('t1-release-recheck-'+tag);d.mkdir();(d/'check.json').write_text('{}');checks.append(str(d))
    def health(*args):
        calls.append('health')
        if scenario=='audit':(root/'games/x').read_bytes()
        if scenario=='audit_other':(root/'other.bin').read_bytes()
        if scenario=='audit_alias':(base/'alias').read_bytes()
        return {**side,'utc':'new'}
    def barrier(*args):calls.append('barrier');makecheck('parent')
    def mocked_run(argv,**kw):
        if scenario=='ancestry' and argv[0]=='git' and '--is-ancestor' in argv:
            raise subprocess.CalledProcessError(1,argv)
        if len(argv)>2 and str(argv[2]).endswith('/reduce.py'):
            calls.append('reducer')
            output=private/'once/reduce.json'
            expected=[sys.executable,'-B',str(here/'reduce.py'),'--root',str(root),'--release',str(release),'--ledger',str(ledger),'--out',str(output)]
            if reason=='committed_mac_summary':expected+=['--mac-summary',str(macsummary)]
            if argv!=expected:raise AssertionError('literal reducer argv differs')
            if kw.get('start_new_session') is not True:raise AssertionError('missing child session')
            if any(k.startswith('PYTHON') for k in kw['env']):raise AssertionError('Python environment leaked')
            emitted=output.with_name(output.name+'.ssh-sensitivity-ledger.json');emitted.write_text(json.dumps(side))
            value={k:{'ledger_sha256':driver.sha(emitted)} for k in ('ssh_sensitivity','apt_sensitivity','ssh_or_apt_sensitivity')}
            output.write_text(json.dumps(value));kw['stdout'].write('SYNTHETIC SECRET')
            if scenario!='fresh':makecheck('child')
            return types.SimpleNamespace(returncode=0)
        return original_run(argv,**kw)
    def mocked_popen(argv,**kw):
        if len(argv)>2 and str(argv[2]).endswith('/reduce.py'):
            result=mocked_run(argv,**kw)
            class Fake:
                pid=987654
                def wait(self):return result.returncode
                def __enter__(self):return self
                def __exit__(self,*a):return False
            return Fake()
        return original_popen(argv,**kw)
    def signal_write(path,value):
        import signal
        if str(scenario).startswith('record_signal_') and Path(path).name=='release-health-receipt.json':
            os.kill(os.getpid(),getattr(signal,scenario.removeprefix('record_signal_')))
        return original_write(path,value)
    def checked_chmod(path,mode):
        import signal
        if mode==0:
            mask=signal.pthread_sigmask(signal.SIG_BLOCK,set())
            if not {signal.SIGTERM,signal.SIGHUP,signal.SIGINT} <= mask:
                raise AssertionError('failure handler did not mask signals')
        return original_chmod(path,mode)
    def special_git(*args):
        if scenario=='code_pin' and args[0] in ('status','diff'):return ''
        if scenario=='private_ref' and args==('rev-parse',driver.PRIVATE_REF):return 'wrong'
        if scenario=='remote' and args[0]=='for-each-ref':return 'refs/remotes/synthetic'
        if scenario=='remote_HEAD' and args[0]=='for-each-ref' and args[2]!=commit:return 'refs/remotes/synthetic'
        if scenario=='record_dirty' and args[0]=='status' and 'reducer' in calls:return 'dirty'
        return original_git(*args)
    if scenario=='dirty':(repo/'dirty').write_text('synthetic')
    if scenario=='ignored':
        (repo/'.git/info/exclude').write_text('ignored\n');(repo/'ignored').write_text('synthetic')
    if scenario=='descendant':
        (repo/'new-unapproved').write_text('x');original_run(['git','-C',str(repo),'add','.'],check=True)
        original_run(['git','-C',str(repo),'-c','user.name=Synthetic','-c','user.email=synthetic@example.invalid','commit','-qm','forbidden descendant'],check=True)
    if scenario=='remote_HEAD':
        path=repo/driver.MAC_DIRECTORY/'preconditions.json';path.write_text('{}')
        original_run(['git','-C',str(repo),'add','.'],check=True)
        original_run(['git','-C',str(repo),'-c','user.name=Synthetic','-c','user.email=synthetic@example.invalid','commit','-qm','allowed descendant'],check=True)
    if scenario in ('rename_descendant','unlisted_mac_descendant','failure_mac_descendant'):
        if scenario=='rename_descendant':
            (repo/'rename-source').rename(repo/driver.MAC_DIRECTORY/'preconditions.json')
            original_run(['git','-C',str(repo),'config','diff.renames','true'],check=True)
        else:
            name='classification/unknown.json' if scenario=='unlisted_mac_descendant' else 'sealed/failure.json'
            p=repo/driver.MAC_DIRECTORY/name;p.parent.mkdir(exist_ok=True);p.write_text('{}')
        original_run(['git','-C',str(repo),'add','.'],check=True)
        original_run(['git','-C',str(repo),'-c','user.name=Synthetic','-c','user.email=synthetic@example.invalid','commit','-qm','synthetic route check'],check=True)
    if scenario=='code_pin':(here/'barrier.py').write_text('changed synthetic barrier')
    if scenario=='release_pin':release.write_text('{"bad":true}')
    if scenario=='r5_pin':r5.write_text('{"bad":true}')
    if scenario=='blind_pin':ledger.write_text('{"events":[{}]}')
    if scenario=='sidecar_pin':sidepath.write_text('{}')
    if scenario=='copy_pin':cp.write_text('{}')
    if scenario=='c2_destination':
        value=json.loads(cp.read_text());value['destination']='wrong';cp.write_text(json.dumps(value));opts['COPY_SHA']=driver.sha(cp)
    if scenario=='c2_root':root.rmdir() if not list(root.iterdir()) else None;opts['BLOCK_ROOT']=base/'absent'
    if scenario=='private_mode':os.chmod(private,0o755)
    if scenario=='executable':opts['PYTHON']='not-the-interpreter'
    if scenario=='root_import':modules_root=base
    else:modules_root=repo
    if scenario=='r5_envelope':
        r5.write_text('{"amendment_1_prerelease":{}}');opts['R5_SHA']=driver.sha(r5)
    if scenario=='cwd':cwd=base
    if scenario=='version':version=(3,12,11)
    else:version=sys.version_info
    options=[sys.executable,'-B',str(here/'driver.py')]
    if scenario=='no_B':options=[sys.executable,str(here/'driver.py')]
    argv=[str(here/'driver.py'),'--release',str(release),'--release-sha256',release_sha,'--r5',str(r5),'--copy-receipt',str(cp),'--private-name','once']
    if scenario=='private_name':argv[-1]='../unsafe'
    if scenario=='early_audit':
        (root/'games/x').write_bytes(release.read_bytes())
        argv[argv.index('--release')+1]=str(root/'games/x')
        argv[argv.index('--release-sha256')+1]=driver.sha(root/'games/x')
    if scenario=='audit_other':(root/'other.bin').write_text('synthetic')
    if scenario=='audit_alias':(base/'alias').symlink_to(root/'games/x')
    modules={n:types.ModuleType(n) for n in ('common','ssh_sensitivity','barrier')}
    modules['common'].ROOT=modules_root;modules['ssh_sensitivity'].health_ledger=health;modules['barrier'].outcome_release=barrier
    stdout=io.StringIO();os.chdir(cwd)
    original_flags=sys.flags
    class FlagsProxy:
        def __getattr__(self,name):
            if name=='dont_write_bytecode' and scenario=='no_flags':return 0
            return getattr(original_flags,name)
    with patch.multiple(driver,**opts),patch.dict(sys.modules,modules),patch.object(os,'chmod',checked_chmod),patch.object(driver,'write',signal_write),patch.object(driver,'git',special_git),patch.object(sys,'argv',argv),patch.object(sys,'orig_argv',options),patch.object(sys,'flags',FlagsProxy()),patch.object(sys,'version_info',version),patch.object(driver.importlib.metadata,'version',return_value='wrong' if scenario=='numpy' else '2.2.6'),patch.object(subprocess,'run',mocked_run),patch.object(subprocess,'Popen',mocked_popen),patch.dict(os.environ,{'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':'synthetic-shadow','PYTHONWARNINGS':'error'}),contextlib.redirect_stdout(stdout):
        rc=driver.main()
    mode=(private/'once').stat().st_mode&0o777 if (private/'once').exists() else None
    pipe.send(dict(rc=rc,stdout=stdout.getvalue(),mode=mode,calls=calls,checks=checks))
    if mode==0:os.chmod(private/'once',0o700)
    pipe.close()


class MainTests(unittest.TestCase):
    def case(self,scenario='success',reason='committed_mac_summary'):
        import multiprocessing
        with tempfile.TemporaryDirectory(prefix='t1-c1-main-synthetic-') as tmp:
            context=multiprocessing.get_context('fork');parent,child=context.Pipe(False)
            process=context.Process(target=synthetic_main_worker,args=(tmp,scenario,reason,child));process.start();child.close()
            self.assertTrue(parent.poll(15),'synthetic main process did not finish')
            result=parent.recv();process.join(2);self.assertEqual(process.exitcode,0)
            health=json.loads(result['stdout']) # rejects extra repr/secret output
            self.assertIn('driver_sha256',health)
            self.assertNotIn('SECRET',result['stdout'])
            return result,health

    def test_main_success_both_routes_literal_argv_scrubbed_environment_detached_child(self):
        for reason in ('committed_mac_summary','fourteen_day_escape'):
            with self.subTest(reason=reason):
                result,health=self.case(reason=reason)
                self.assertEqual(result['rc'],0);self.assertTrue(health['passes'])
                self.assertEqual(result['calls'],['health','barrier','reducer'])
                self.assertEqual(result['mode'],0o700)

    def test_main_preflight_failures_have_no_output_directory(self):
        for scenario in ('version','no_B','no_flags','executable','numpy','cwd','dirty','ignored','private_ref','ancestry','remote','remote_HEAD','descendant','code_pin','release_pin','r5_pin','r5_envelope','blind_pin','sidecar_pin','copy_pin','c2_destination','c2_root','root_import','private_mode','private_name','early_audit'):
            with self.subTest(scenario=scenario):
                result,health=self.case(scenario)
                self.assertEqual(result['rc'],1);self.assertFalse(health['passes'])
                self.assertIsNone(result['mode']);self.assertNotIn('reducer',result['calls'])
                self.assertEqual(set(health),{'passes','stage','exception_type','no_result_reported','driver_sha256','outputs_locked'})

    def test_main_audit_rejects_synthetic_game_read_before_barrier(self):
        for scenario in ('audit','audit_other','audit_alias'):
            with self.subTest(scenario=scenario):
                result,health=self.case(scenario)
                self.assertEqual(result['rc'],1);self.assertEqual(result['calls'],['health']);self.assertIsNone(result['mode'])
                self.assertEqual(health['stage'],'pre_guard')

    def test_main_record_signals_lock_and_report_health_only(self):
        for sig in ('SIGTERM','SIGHUP','SIGINT'):
            with self.subTest(signal=sig):
                result,health=self.case('record_signal_'+sig)
                self.assertEqual(result['rc'],1);self.assertEqual(result['mode'],0)
                self.assertTrue(health['outputs_locked']);self.assertEqual(health['exception_type'],'TerminationSignal')

    def test_mac_a3p_failure_or_seal_mismatch_stops_before_health_and_reducer(self):
        for scenario in ('a3p_reject','a3p_seal_mismatch'):
            result,health=self.case(scenario)
            self.assertEqual(result['rc'],1);self.assertIsNone(result['mode']);self.assertEqual(result['calls'],[])
            if scenario=='a3p_reject':self.assertEqual(health['exception_type'],'A3PRequiresRuling')

    def test_real_binding_paths_in_main_cannot_be_ignored(self):
        for scenario in ('a3p_binding_sha','a3p_binding_commit','a3p_binding_path','manifest_binding_sha','summary_other_path'):
            with self.subTest(scenario=scenario):
                result,health=self.case(scenario)
                self.assertEqual(result['rc'],1);self.assertEqual(result['calls'],[]);self.assertIsNone(result['mode'])

    def test_main_record_failures_lock_owned_outputs(self):
        for scenario in ('fresh','record_dirty'):
            with self.subTest(scenario=scenario):
                result,health=self.case(scenario)
                self.assertEqual(result['rc'],1);self.assertEqual(result['mode'],0)
                self.assertTrue(health['outputs_locked']);self.assertEqual(health['stage'],'preflight_or_record')

    def test_mac_descendants_cannot_hide_rename_unlisted_path_or_failure(self):
        for scenario in ('rename_descendant','unlisted_mac_descendant','failure_mac_descendant'):
            with self.subTest(scenario=scenario):
                result,health=self.case(scenario)
                self.assertEqual(result['rc'],1);self.assertIsNone(result['mode']);self.assertEqual(result['calls'],[])

    def test_exact_execution_pin_names_and_empty_allowlist(self):
        names='apt_budget barrier check_reference common cpu_accounting host_audit idle_services owned_supervisor parent_source_seed perception_confirmation reduce release_reference schedule ssh_budget ssh_sensitivity ssh_transport system_bus'.split()
        self.assertEqual(set(driver.PINS),{n+'.py' for n in names}|{'plan.json'})
        self.assertTrue(all(len(value)==64 for value in driver.PINS.values()))
        self.assertEqual(len(driver.DESCENDANT_ALLOWLIST),18)
        self.assertIn(driver.MAC_SUMMARY_PATH,driver.DESCENDANT_ALLOWLIST)
        self.assertTrue(all(p.startswith(driver.MAC_DIRECTORY+'/') and '*' not in p for p in driver.DESCENDANT_ALLOWLIST))


class ReducerSessionTests(unittest.TestCase):
    def test_termination_kills_entire_owned_process_group_and_reaps(self):
        import signal,types
        calls=[]
        class Child:
            pid=123456
            count=0
            def __enter__(self):return self
            def __exit__(self,*a):return False
            def wait(self):
                self.count+=1
                if self.count==1:raise driver.TerminationSignal(signal.SIGTERM)
                calls.append('reaped');return -9
        with driver.terminating_signals(),patch.object(driver.subprocess,'Popen',return_value=Child()) as spawn,patch.object(driver.os,'killpg',side_effect=lambda p,s:calls.append((p,s))):
            with self.assertRaises(driver.TerminationSignal):driver.run_reducer(['synthetic'],Path('/tmp'),io.StringIO(),io.StringIO())
        self.assertEqual(calls,[(123456,signal.SIGKILL),'reaped'])
        self.assertTrue(spawn.call_args.kwargs['start_new_session'])

    def test_second_signal_during_group_kill_does_not_skip_kill_and_reap(self):
        import signal
        calls=[];old=signal.getsignal(signal.SIGTERM)
        class Child:
            pid=123456;count=0
            def __enter__(self):return self
            def __exit__(self,*a):return False
            def wait(self):
                self.count+=1
                if self.count==1:raise driver.TerminationSignal(signal.SIGTERM)
                calls.append('reaped');return -9
        def killpg(pid,sig):
            os.kill(os.getpid(),signal.SIGTERM)
            calls.append((pid,sig))
        try:
            signal.signal(signal.SIGTERM,lambda *a:None)
            with driver.terminating_signals(),patch.object(driver.subprocess,'Popen',return_value=Child()),patch.object(driver.os,'killpg',side_effect=killpg):
                with self.assertRaises(driver.TerminationSignal):driver.run_reducer(['synthetic'],Path('/tmp'),io.StringIO(),io.StringIO())
            self.assertEqual(calls,[(123456,signal.SIGKILL),'reaped'])
        finally:signal.signal(signal.SIGTERM,old)

    def test_real_synthetic_child_and_grandchild_are_killed_together(self):
        import signal,sys,time
        with tempfile.TemporaryDirectory(prefix='t1-child-session-synthetic-') as tmp:
            pidfile=Path(tmp)/'pid'
            code="import subprocess,sys,os,signal,time; p=subprocess.Popen([sys.executable,'-B','-c','import time; time.sleep(20)']); open(sys.argv[1],'w').write(str(p.pid)); os.kill(os.getppid(),signal.SIGTERM); time.sleep(20)"
            with driver.terminating_signals(),(Path(tmp)/'stdout').open('w') as out,(Path(tmp)/'stderr').open('w') as err:
                with self.assertRaises(driver.TerminationSignal):
                    driver.run_reducer([sys.executable,'-B','-c',code,str(pidfile)],Path(tmp),out,err)
            pid=int(pidfile.read_text());statpath=Path('/proc')/str(pid)/'stat'
            end=time.monotonic()+2
            while statpath.exists() and statpath.read_text().split()[2]!='Z' and time.monotonic()<end:time.sleep(.01)
            dead=not statpath.exists() or statpath.read_text().split()[2]=='Z'
            if not dead:os.kill(pid,signal.SIGKILL) # Clean up even deliberately broken mutants.
            self.assertTrue(dead)


class DescendantTests(unittest.TestCase):
    def test_narrow_tree_preserves_both_ancestries_and_rejects_rename_source_escape(self):
        import subprocess
        import prepare_release_descendant as builder
        with tempfile.TemporaryDirectory(prefix='t1-descendant-synthetic-') as tmp:
            repo=Path(tmp)/'repo';repo.mkdir()
            def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()
            git('init','-q');git('config','user.name','Synthetic');git('config','user.email','synthetic@example.invalid')
            (repo/'protected').write_text('unchanged');git('add','.');git('commit','-qm','base');base=git('rev-parse','HEAD')
            git('update-ref',builder.PRIVATE_REF,base)
            (repo/'protected').rename(repo/'renamed-public')
            mac=repo/driver.MAC_SUMMARY_PATH;mac.parent.mkdir(parents=True);mac.write_text('{"synthetic":true}')
            (repo/'unrelated').write_text('public unrelated');git('add','-A');git('commit','-qm','source');source=git('rev-parse','HEAD')
            original_index=(repo/'.git/index').read_bytes()
            with patch.object(builder,'PRIVATE_COMMIT',base):
                result=builder.build_descendant(repo,source,'refs/private/synthetic-release')
            self.assertEqual(result['changed_paths'],[driver.MAC_SUMMARY_PATH])
            self.assertEqual(git('show',result['commit']+':protected'),'unchanged')
            for ancestor in (base,source):git('merge-base','--is-ancestor',ancestor,result['commit'])
            self.assertEqual(git('rev-parse','HEAD'),source)
            self.assertEqual((repo/'.git/index').read_bytes(),original_index)
            self.assertEqual(git('status','--porcelain'),'')
            extra=repo/driver.MAC_DIRECTORY/'classification/unknown.json';extra.parent.mkdir();extra.write_text('{}')
            git('add','.');git('commit','-qm','unlisted classification');bad=git('rev-parse','HEAD')
            with patch.object(builder,'PRIVATE_COMMIT',base),self.assertRaises(ValueError):
                builder.build_descendant(repo,bad,'refs/private/refused')



class MacGateContractTests(unittest.TestCase):
    def invoke(self, change=None):
        import hashlib,copy
        with tempfile.TemporaryDirectory(prefix='t1-mac-gate-synthetic-') as tmp:
            repo=Path(tmp)
            summary={'dry_run':False,'feasibility':{t:{'feasible':True} for t in ('K0c','S','K2','K4')}}
            a3p={'outcomes_read':False,'tiers':{t:dict(frozen_feasible=True,feasible_after_a3p=True,a3p_passes=True) for t in ('K0c','S','K2','K4')}}
            seal={'status':'complete','files':{}}
            if change:change(summary,a3p,seal)
            rawsummary=json.dumps(summary).encode();summary_sha=hashlib.sha256(rawsummary).hexdigest()
            seal['files'].setdefault('tiers-summary.json',summary_sha)
            rawseal=json.dumps(seal).encode();seal_sha=hashlib.sha256(rawseal).hexdigest()
            a3p['receipt_manifest_sha256']=seal_sha
            data={driver.MAC_SUMMARY_PATH:summary,driver.MAC_A3P_PATH:a3p,driver.MAC_MANIFEST_PATH:seal}
            commits={driver.MAC_SUMMARY_PATH:'1'*40,driver.MAC_A3P_PATH:'2'*40,driver.MAC_MANIFEST_PATH:'3'*40}
            bindings={}
            for name,value in data.items():
                p=repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))
                bindings[name]=dict(path=name,commit=commits[name],sha256=driver.sha(p))
            release=dict(mac_summary_path=driver.MAC_SUMMARY_PATH,commit='1'*40,mac_summary_sha256=summary_sha,a3p_poll_check=bindings[driver.MAC_A3P_PATH],mac_receipt_manifest=bindings[driver.MAC_MANIFEST_PATH])
            calls=[]
            def bound(binding,expected):
                self.assertEqual(binding,bindings[expected]);calls.append(expected)
                return data[expected]
            with patch.object(driver,'CANONICAL',repo),patch.object(driver,'bound_mac_json',side_effect=bound):
                driver.check_mac_a3p(release)
            self.assertEqual(calls,[driver.MAC_SUMMARY_PATH,driver.MAC_A3P_PATH,driver.MAC_MANIFEST_PATH])

    def test_every_mac_artifact_is_commit_and_sha_bound_including_later_a3p_commit(self):
        self.invoke()

    def test_seal_scope_coverage_types_and_consistency_fail_independently(self):
        mutations={
            'manifest_status':lambda s,a,m:m.update(status='failed'),
            'summary_seal_entry':lambda s,a,m:m['files'].update({'tiers-summary.json':'0'*64}),
            'dry_run':lambda s,a,m:s.update(dry_run=True),
            'outcomes_read':lambda s,a,m:a.update(outcomes_read=True),
            'extra_tier':lambda s,a,m:a['tiers'].update(EXTRA=dict(frozen_feasible=True,feasible_after_a3p=True,a3p_passes=True)),
            'summary_extra_tier':lambda s,a,m:s['feasibility'].update(EXTRA={'feasible':True}),
            'frozen_not_bound':lambda s,a,m:a['tiers']['S'].update(frozen_feasible=False),
            'after_not_bound':lambda s,a,m:(s['feasibility']['S'].update(feasible=False),a['tiers']['S'].update(frozen_feasible=False,feasible_after_a3p=True)),
            'frozen_integer':lambda s,a,m:s['feasibility']['S'].update(feasible=1),
            'row_frozen_integer':lambda s,a,m:a['tiers']['S'].update(frozen_feasible=1),
            'row_after_integer':lambda s,a,m:a['tiers']['S'].update(feasible_after_a3p=1),
            'row_passes_integer':lambda s,a,m:a['tiers']['S'].update(a3p_passes=1),
        }
        for name,change in mutations.items():
            with self.subTest(name=name),self.assertRaises(ValueError):self.invoke(change)


class MacBindingTests(unittest.TestCase):
    def invoke(self, scenario):
        import hashlib,types,subprocess
        with tempfile.TemporaryDirectory(prefix='t1-mac-binding-synthetic-') as tmp:
            root=Path(tmp);expected=driver.MAC_A3P_PATH;p=root/expected;p.parent.mkdir(parents=True)
            raw=b'{"synthetic":true}';p.write_bytes(raw)
            binding=dict(path=expected,commit='2'*40,sha256=hashlib.sha256(raw).hexdigest())
            if scenario=='path':binding['path']='other.json'
            if scenario=='commit_format':binding['commit']='synthetic-ref'
            if scenario=='sha':binding['sha256']='0'*64
            if scenario=='worktree':p.write_bytes(b'{"synthetic":false}')
            if scenario=='symlink':
                target=root/'target';target.write_bytes(raw);p.unlink();p.symlink_to(target)
            def run(argv,**kwargs):
                if scenario=='ancestry':raise subprocess.CalledProcessError(1,argv)
                self.assertTrue(kwargs['check']);return types.SimpleNamespace(returncode=0)
            with patch.object(driver,'CANONICAL',root),patch.object(driver.subprocess,'run',side_effect=run),patch.object(driver.subprocess,'check_output',return_value=raw):
                return driver.bound_mac_json(binding,expected)

    def test_bound_mac_json_positive(self):self.assertEqual(self.invoke('success'),{'synthetic':True})
    def test_binding_rejects_every_independent_boundary(self):
        import subprocess
        for scenario in ('path','commit_format','sha','worktree','symlink','ancestry'):
            with self.subTest(scenario=scenario),self.assertRaises((ValueError,subprocess.CalledProcessError)):
                self.invoke(scenario)


class BuilderRefTests(unittest.TestCase):
    def setUp(self):
        import subprocess
        import prepare_release_descendant as builder
        self.builder=builder;self.temp=tempfile.TemporaryDirectory(prefix='t1-builder-ref-synthetic-');self.repo=Path(self.temp.name)/'repo';self.repo.mkdir()
        self.git=lambda *a:subprocess.check_output(['git','-C',str(self.repo),*a],text=True).strip()
        self.git('init','-q');self.git('config','user.name','Synthetic');self.git('config','user.email','synthetic@example.invalid')
        (self.repo/'protected').write_text('common');self.git('add','.');self.git('commit','-qm','common');common=self.git('rev-parse','HEAD')
        self.git('checkout','-qb','private-case');(self.repo/'private-only').write_text('keep-private');self.git('add','.');self.git('commit','-qm','private base');self.base=self.git('rev-parse','HEAD')
        self.git('update-ref',builder.PRIVATE_REF,self.base)
        self.git('checkout','-qb','public-case',common);mac=self.repo/driver.MAC_SUMMARY_PATH;mac.parent.mkdir(parents=True);mac.write_text('{}')
        (self.repo/'unrelated').write_text('public only');self.git('add','.');self.git('commit','-qm','public source');self.source=self.git('rev-parse','HEAD')
        self.pin=patch.object(builder,'PRIVATE_COMMIT',self.base);self.pin.start()
    def tearDown(self):self.pin.stop();self.temp.cleanup()
    def build(self,name='refs/private/fresh'):
        return self.builder.build_descendant(self.repo,self.source,name)
    def test_divergent_source_preserves_both_exact_parents_and_private_tree(self):
        import subprocess
        self.assertEqual(subprocess.run(['git','-C',str(self.repo),'merge-base','--is-ancestor',self.base,self.source]).returncode,1)
        index=(self.repo/'.git/index').read_bytes();r=self.build()
        self.assertEqual(self.git('rev-list','--parents','-n','1',r['commit']).split()[1:],[self.base,self.source])
        self.assertEqual(self.git('show',r['commit']+':private-only'),'keep-private')
        self.assertEqual(self.git('rev-parse',self.builder.PRIVATE_REF),self.base)
        self.assertEqual((self.repo/'.git/index').read_bytes(),index);self.assertEqual(self.git('rev-parse','HEAD'),self.source)
    def test_nonprivate_and_protection_ref_targets_are_rejected(self):
        for name in ('refs/heads/unsafe',self.builder.PRIVATE_REF):
            with self.subTest(name=name),self.assertRaises(ValueError):self.build(name)
        self.assertEqual(self.git('rev-parse',self.builder.PRIVATE_REF),self.base)
    def test_existing_ref_is_never_overwritten(self):
        import subprocess
        self.git('update-ref','refs/private/existing',self.base)
        with self.assertRaises(subprocess.CalledProcessError):self.build('refs/private/existing')
        self.assertEqual(self.git('rev-parse','refs/private/existing'),self.base)
        self.assertEqual(self.git('rev-parse',self.builder.PRIVATE_REF),self.base)
    def test_changed_protection_ref_before_build_is_rejected(self):
        self.git('update-ref',self.builder.PRIVATE_REF,self.source)
        with self.assertRaises(ValueError):self.build()
        # Refusal must occur before creating the descendant ref; an after-only
        # check also raises, but has already written this ref (BP4/BP9).
        import subprocess
        absent=subprocess.run(['git','-C',str(self.repo),'show-ref','--verify','--quiet','refs/private/fresh'])
        self.assertEqual(absent.returncode,1)
    def test_changed_protection_ref_after_build_is_detected(self):
        original=self.builder.subprocess.check_output
        def fault(argv,**kwargs):
            out=original(argv,**kwargs)
            if 'update-ref' in argv and 'refs/private/fresh' in argv:
                original(['git','-C',str(self.repo),'update-ref',self.builder.PRIVATE_REF,self.source],text=True)
            return out
        with patch.object(self.builder.subprocess,'check_output',side_effect=fault),self.assertRaises(ValueError):self.build()
    def test_symlink_blob_at_allowed_path_is_refused(self):
        p=self.repo/driver.MAC_SUMMARY_PATH;p.unlink();p.symlink_to('synthetic-target')
        self.git('add','.');self.git('commit','-qm','symlink metadata');self.source=self.git('rev-parse','HEAD')
        with self.assertRaises(ValueError):self.build()
    def test_dirty_checkout_refused(self):
        (self.repo/'dirty').write_text('x')
        with self.assertRaises(ValueError):self.build()
    def test_source_without_allowed_metadata_refused(self):
        self.source=self.git('rev-parse',self.source+'^')
        with self.assertRaises(ValueError):self.build()


if __name__ == '__main__':
    unittest.main()
