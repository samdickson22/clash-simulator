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
    pins={name:driver.sha(here/name) for name in driver.PINS}
    ledger=here/'receipts/blind-ledger-final-op7-r3.json';ledger.write_text('{"events":[]}')
    side={'utc':'old','schema':'synthetic','sealed':True,'blocks':[{'id':'s0'}]}
    sidepath=here/'receipts/PC4/ssh-sensitivity-pc4-landed.json';sidepath.write_text(json.dumps(side))
    release=base/'release.json';release.write_text(json.dumps({'reason':reason,'mac_summary_path':'summary.json','amendment_1_prerelease':{'synthetic':True}}))
    r5=base/'r5.json';r5.write_text(json.dumps({'amendment_1_prerelease':{'synthetic':True}}))
    cp=base/'copy.json';cp.write_text(json.dumps(dict(destination=str(root),exit_code=0,complete_proofs=3072,verified_game_files=24576,verified_hub_ack=1100,game_parse_or_summary=False,complete_proof_set_sha256='d0f010695064c0b5d397ce8f24afede30a679a571a989daa4e058c1571c23fe0')))
    subprocess.run(['git','init','-q',str(repo)],check=True)
    subprocess.run(['git','-C',str(repo),'add','.'],check=True)
    subprocess.run(['git','-C',str(repo),'-c','user.name=Synthetic','-c','user.email=synthetic@example.invalid','commit','-qm','synthetic fixture'],check=True)
    commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    subprocess.run(['git','-C',str(repo),'update-ref',driver.PRIVATE_REF,commit],check=True)
    original_run=subprocess.run;original_git=driver.git
    cwd=here
    opts=dict(CANONICAL=repo,BLOCK_ROOT=root,PRIVATE=private,PYTHON=sys.executable,PRIVATE_COMMIT=commit,PINS=pins,BLIND_SHA=driver.sha(ledger),SIDECAR_SHA=driver.sha(sidepath),R5_SHA=driver.sha(r5),COPY_SHA=driver.sha(cp),SCRATCH=scratch)
    checks=[];calls=[]
    def makecheck(tag):
        d=scratch/('t1-release-recheck-'+tag);d.mkdir();(d/'check.json').write_text('{}');checks.append(str(d))
    def health(*args):
        calls.append('health')
        if scenario=='audit':(root/'games/x').read_bytes()
        return {**side,'utc':'new'}
    def barrier(*args):calls.append('barrier');makecheck('parent')
    def mocked_run(argv,**kw):
        if scenario=='ancestry' and argv[0]=='git' and '--is-ancestor' in argv:
            raise subprocess.CalledProcessError(1,argv)
        if len(argv)>2 and str(argv[2]).endswith('/reduce.py'):
            calls.append('reducer')
            output=private/'once/reduce.json'
            expected=[sys.executable,'-B',str(here/'reduce.py'),'--root',str(root),'--release',str(release),'--ledger',str(ledger),'--out',str(output)]
            if reason=='committed_mac_summary':expected+=['--mac-summary',str(repo/'summary.json')]
            if argv!=expected:raise AssertionError('literal reducer argv differs')
            if kw.get('start_new_session') is not True:raise AssertionError('missing child session')
            if any(k.startswith('PYTHON') for k in kw['env']):raise AssertionError('Python environment leaked')
            emitted=output.with_name(output.name+'.ssh-sensitivity-ledger.json');emitted.write_text(json.dumps(side))
            value={k:{'ledger_sha256':driver.sha(emitted)} for k in ('ssh_sensitivity','apt_sensitivity','ssh_or_apt_sensitivity')}
            output.write_text(json.dumps(value));kw['stdout'].write('SYNTHETIC SECRET')
            if scenario!='fresh':makecheck('child')
            return types.SimpleNamespace(returncode=0)
        return original_run(argv,**kw)
    def special_git(*args):
        if scenario=='code_pin' and args[0] in ('status','diff'):return ''
        if scenario=='private_ref' and args==('rev-parse',driver.PRIVATE_REF):return 'wrong'
        if scenario=='remote' and args[0]=='for-each-ref':return 'refs/remotes/synthetic'
        if scenario=='record_dirty' and args[0]=='status' and 'reducer' in calls:return 'dirty'
        return original_git(*args)
    if scenario=='dirty':(repo/'dirty').write_text('synthetic')
    if scenario=='ignored':
        (repo/'.git/info/exclude').write_text('ignored\n');(repo/'ignored').write_text('synthetic')
    if scenario=='descendant':
        (repo/'new-unapproved').write_text('x');original_run(['git','-C',str(repo),'add','.'],check=True)
        original_run(['git','-C',str(repo),'-c','user.name=Synthetic','-c','user.email=synthetic@example.invalid','commit','-qm','forbidden descendant'],check=True)
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
    argv=[str(here/'driver.py'),'--release',str(release),'--release-sha256',hashlib.sha256(json.dumps({'reason':reason,'mac_summary_path':'summary.json','amendment_1_prerelease':{'synthetic':True}}).encode()).hexdigest(),'--r5',str(r5),'--copy-receipt',str(cp),'--private-name','once']
    if scenario=='private_name':argv[-1]='../unsafe'
    if scenario=='early_audit':argv[argv.index('--release')+1]=str(root/'games/x')
    modules={n:types.ModuleType(n) for n in ('common','ssh_sensitivity','barrier')}
    modules['common'].ROOT=modules_root;modules['ssh_sensitivity'].health_ledger=health;modules['barrier'].outcome_release=barrier
    stdout=io.StringIO();os.chdir(cwd)
    original_flags=sys.flags
    class FlagsProxy:
        def __getattr__(self,name):
            if name=='dont_write_bytecode' and scenario=='no_flags':return 0
            return getattr(original_flags,name)
    with patch.multiple(driver,**opts),patch.dict(sys.modules,modules),patch.object(driver,'git',special_git),patch.object(sys,'argv',argv),patch.object(sys,'orig_argv',options),patch.object(sys,'flags',FlagsProxy()),patch.object(sys,'version_info',version),patch.object(driver.importlib.metadata,'version',return_value='wrong' if scenario=='numpy' else '2.2.6'),patch.object(subprocess,'run',mocked_run),patch.dict(os.environ,{'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':'synthetic-shadow','PYTHONWARNINGS':'error'}),contextlib.redirect_stdout(stdout):
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
        for scenario in ('version','no_B','no_flags','executable','numpy','cwd','dirty','ignored','private_ref','ancestry','remote','descendant','code_pin','release_pin','r5_pin','r5_envelope','blind_pin','sidecar_pin','copy_pin','c2_destination','c2_root','root_import','private_mode','private_name','early_audit'):
            with self.subTest(scenario=scenario):
                result,health=self.case(scenario)
                self.assertEqual(result['rc'],1);self.assertFalse(health['passes'])
                self.assertIsNone(result['mode']);self.assertNotIn('reducer',result['calls'])
                self.assertEqual(set(health),{'passes','stage','exception_type','no_result_reported','driver_sha256','outputs_locked'})

    def test_main_audit_rejects_synthetic_game_read_before_barrier(self):
        result,health=self.case('audit')
        self.assertEqual(result['rc'],1);self.assertEqual(result['calls'],['health']);self.assertIsNone(result['mode'])
        self.assertEqual(health['stage'],'pre_guard')

    def test_main_record_failures_lock_owned_outputs(self):
        for scenario in ('fresh','record_dirty'):
            with self.subTest(scenario=scenario):
                result,health=self.case(scenario)
                self.assertEqual(result['rc'],1);self.assertEqual(result['mode'],0)
                self.assertTrue(health['outputs_locked']);self.assertEqual(health['stage'],'preflight_or_record')

    def test_exact_execution_pin_names_and_empty_allowlist(self):
        names='apt_budget barrier check_reference common cpu_accounting host_audit idle_services owned_supervisor parent_source_seed perception_confirmation reduce release_reference schedule ssh_budget ssh_sensitivity ssh_transport system_bus'.split()
        self.assertEqual(set(driver.PINS),{n+'.py' for n in names}|{'plan.json'})
        self.assertTrue(all(len(value)==64 for value in driver.PINS.values()))
        self.assertEqual(driver.DESCENDANT_ALLOWLIST,frozenset())


if __name__ == '__main__':
    unittest.main()
