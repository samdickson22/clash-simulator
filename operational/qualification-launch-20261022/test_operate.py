"""CPU-only adversarial fixtures. Never inspect current jobs or call GPU/engine tools."""
import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock

import operate as O

TESTS = Path('/mpac/sdicks02/jobs/clasher/rl-qualification-launch-20261022/cpu-tests')


def row(data):
    return dict(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))


class Fixtures(unittest.TestCase):
    def setUp(self):
        TESTS.mkdir(exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix='fixture-', dir=TESTS))
        # Preserve every attempt for independent review, including failing fixtures.
        self.home = self.root/'package'
        self.home.mkdir()
        for key, value in [('JOBS', self.root), ('HOME', self.home), ('DRIVER', self.home/'driver'),
                           ('READY', self.root/'ready')]:
            p = patch.object(O, key, value)
            p.start()
            self.addCleanup(p.stop)

    def put(self, name, obj):
        p = self.root/'receipts'/name
        p.parent.mkdir(exist_ok=True)
        data = O.encoded(obj) if not isinstance(obj, bytes) else obj
        p.write_bytes(data)
        return dict(path=str(p), sha256=row(data)['sha256'])

    def authorities(self):
        report = self.put('review.txt', b'CPU TEST FIXTURE ONLY')
        r49 = self.put('r49.txt', b'Narrow source eligibility, no operational authority')
        measurement = self.put('maxshape.json', {'status': 'pass'})
        physical = self.put('physical.json', dict(status='pass', scope='full-cuda-process', size='M',
            dtype='float64', anchor_sha256='b'*64, peak_process_bytes=12*2**30))
        gate = self.put('qualification.json', {'gates': {'independent_sol_high': {'evidence': report}}})
        precision = self.put('precision.json', {'parity_evidence': {'M': report, 'S100': report}})
        config = dict(host='127x09', size='M', workers=32, qualification_only=True, precision='float64',
            runtime=str(O.READY/'runtime'), actor_source=str(O.READY/'actor_source'),
            runtime_manifest={'path': str(self.root/'joint'), 'sha256': 'c'*64},
            anchor={'path': str(self.root/'anchor'), 'sha256': 'b'*64},
            precision_registration=precision, qualification_gate_receipt=gate,
            immutable_science={'seed': 2026102101, 'updates': 32},
            gpu_admission=dict(measurement=measurement, process_measurement=physical,
                               peak_process_bytes=12*2**30, peak_reserved_bytes=10*2**30))
        final = self.put('final.json', config)
        inv = dict(source_commit='f'*40, source_sha256='e'*64, r49_sha256=r49['sha256'],
                   joint_sha256='c'*64, inputs={}, source_files={}, prepared_config_values={'127x09': copy.deepcopy(config)})
        release = self.put('release.json', dict(schema='qualification-r40-release-v1', status='released',
            host='127x09', source_commit=inv['source_commit'], source_sha256=inv['source_sha256'],
            final_config=final, explicit_per_host_release=True, actual_measurement=True,
            exact_owned_tree_reaped=True, full_gpu_free=True, physical_measurement=physical,
            utc='2026-10-22T00:00:00Z'))
        extra_refs = [report, r49, measurement, physical, gate, precision, final, release]
        extras = [dict(x, bytes=Path(x['path']).stat().st_size) for x in extra_refs]
        review = self.put('operational-review.json', dict(schema='qualification-operational-review-v1', status='GO',
            scope='separate-six-hour-qualification', model='gpt-6.1-sol', effort='high', independent=True,
            host='127x09', source_commit=inv['source_commit'], source_sha256=inv['source_sha256'],
            final_config=final, package_sha256='a'*64, release=release, r49=r49, report=report,
            inventory_sha256=O.digest(inv), extra_files_sha256=O.digest(extras), phases=['source', 'inputs', 'soak']))
        c = dict(schema='qualification-operation-v1', host='127x09', source_commit=inv['source_commit'],
            source_sha256=inv['source_sha256'], package_sha256='a'*64, final_config=final,
            release=release, operational_review=review, r49=r49, extra_files=extras+[
                dict(review, bytes=Path(review['path']).stat().st_size)],
            out=str(O.HOME/'hosts/127x09/soak'), supervisor={'path': str(O.SUPERVISOR), 'sha256': O.SUPERVISOR_SHA},
            job_names={'source': 'qual-fe6-source', 'inputs': 'qual-fe6-inputs', 'soak': 'qual-fe6-soak'})
        return c, inv, config

    def replace_ref_json(self, c, key, update):
        obj = O.read_json(c[key]['path'])
        update(obj)
        Path(c[key]['path']).write_bytes(O.encoded(obj))
        c[key]['sha256'] = O.sha(c[key]['path'])

    def test_no_overwrite_and_matching_file_idempotence(self):
        src, dst = self.root/'src', self.home/'tree/data'
        src.write_bytes(b'pinned')
        O.copy_exact(src, dst, row(b'pinned'))
        O.copy_exact(src, dst, row(b'pinned'))
        dst.write_bytes(b'sentinel')
        with self.assertRaisesRegex(ValueError, 'hash changed'):
            O.copy_exact(src, dst, row(b'pinned'))
        self.assertEqual(dst.read_bytes(), b'sentinel')

    def test_paths_links_and_special_files_fail_closed(self):
        src = self.root/'src'
        src.write_bytes(b'x')
        for target in (str(self.home)+'/../escape', '/tmp/outside', str(self.home)+'//escape'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                O.copy_exact(src, target, row(b'x'))
        (self.home/'link').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            O.copy_exact(src, self.home/'link/escape', row(b'x'))
        (self.home/'file-link').symlink_to(src)
        with self.assertRaises(OSError):
            O.copy_exact(src, self.home/'file-link', row(b'x'))
        fifo = self.root/'fifo'
        os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError, 'regular file'):
            O.sha(fifo)

    def test_source_change_during_copy_is_retained_as_failed_partial(self):
        src, dst = self.root/'src', self.home/'partial'
        src.write_bytes(b'a'*(5 << 20))
        expected = row(src.read_bytes())
        calls = [0]
        def race():
            calls[0] += 1
            if calls[0] == 3:  # first copy block, after prevalidation
                src.write_bytes(b'z'*(5 << 20))
        with self.assertRaisesRegex(ValueError, 'source changed'):
            O.copy_exact(src, dst, expected, race)
        self.assertTrue(dst.exists())

    def test_write_new_is_exclusive(self):
        path = self.home/'receipt.json'
        O.write_new(path, {'status': 'fixture'})
        with self.assertRaises(FileExistsError):
            O.write_new(path, {'status': 'overwrite'})

    def test_duplicate_json_and_zero_pin_rejected(self):
        p = self.root/'duplicate.json'
        p.write_bytes(b'{"status":"GO","status":"NO-GO"}')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            O.read_json(p)
        with self.assertRaisesRegex(ValueError, 'nonzero'):
            O.ref({'path': str(p), 'sha256': '0'*64})
        for data in (b'{"x":1e9999}', b'{"x":NaN}', b'{"x":'+b'1'*1025+b'}'):
            p.write_bytes(data)
            with self.assertRaises(ValueError):
                O.read_json(p)

    def test_contract_valid_and_complete_authority_closure(self):
        c, inv, _ = self.authorities()
        O.validate_contract(c, inv, 'a'*64, '127x09')
        self.assertEqual(O.check_authority(c, inv)['host'], '127x09')
        # Constructing a valid external contract is possible without a hash cycle.
        incoming = self.home/'incoming'
        for rel, dst, r in O.payload_rows(inv, c, 'inputs'):
            O.copy_exact(dst, incoming/rel, r)
        self.assertEqual(O.check_authority(c, inv, O.payload_lookup(incoming, c, inv))['size'], 'M')

    def test_missing_release_and_changed_config(self):
        c, inv, _ = self.authorities()
        Path(c['release']['path']).unlink()
        with self.assertRaises(FileNotFoundError):
            O.check_authority(c, inv)
        c, inv, _ = self.authorities()
        Path(c['final_config']['path']).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'pin changed'):
            O.check_authority(c, inv)

    def test_changed_source_package_host_and_review_are_rejected(self):
        for key, value in [('source_commit', '1'*40), ('source_sha256', '2'*64),
                           ('package_sha256', '3'*64), ('host', '127x12')]:
            c, inv, _ = self.authorities()
            c[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                O.validate_contract(c, inv, 'a'*64, '127x09')
        c, inv, _ = self.authorities()
        self.replace_ref_json(c, 'operational_review', lambda x: x.update(independent=False))
        with self.assertRaisesRegex(ValueError, 'operational review'):
            O.check_authority(c, inv)

    def test_release_claims_are_all_required(self):
        for flag in ('explicit_per_host_release', 'actual_measurement', 'exact_owned_tree_reaped', 'full_gpu_free'):
            c, inv, _ = self.authorities()
            self.replace_ref_json(c, 'release', lambda x: x.update({flag: False}))
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, 'physical release'):
                O.check_authority(c, inv)

    def test_extras_cannot_overwrite_code_prepared_tree_or_inputs(self):
        c, inv, _ = self.authorities()
        for path in (str(self.home/'operate.py'), str(self.root/'rl-input-roots-20261022/prepared-attempt2/new'),
                     str(self.root/'lease-20261022/127x09/HALT'),
                     str(self.root/'lease-1316-extension-20261022/r40-physical-0912/result.json')):
            bad = copy.deepcopy(c)
            bad['extra_files'].append(dict(path=path, sha256='1'*64, bytes=10))
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'overlaps'):
                O.validate_contract(bad, inv, 'a'*64, '127x09')
        inv['inputs'][c['final_config']['path']] = row(b'x')
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            O.validate_contract(c, inv, 'a'*64, '127x09')

    def test_final_science_change_rejected_even_with_rebound_authority(self):
        c, inv, _ = self.authorities()
        inv['prepared_config_values']['127x09']['immutable_science']['updates'] = 33
        self.replace_ref_json(c, 'operational_review', lambda x: x.update(inventory_sha256=O.digest(inv)))
        with self.assertRaisesRegex(ValueError, 'science/inputs'):
            O.check_authority(c, inv)

    def test_unlisted_and_changed_payload_receipts_rejected(self):
        c, inv, _ = self.authorities()
        lookup = O.payload_lookup(self.home/'incoming', c, inv)
        with self.assertRaisesRegex(ValueError, 'not explicitly supplied'):
            lookup(dict(path=str(self.root/'unknown'), sha256='1'*64))
        for rel, dst, r in O.payload_rows(inv, c, 'inputs'):
            O.copy_exact(dst, self.home/'incoming'/rel, r)
        Path(lookup(c['final_config'])).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'hash changed'):
            lookup(c['final_config'])

    def test_original_402_measurement_can_resolve_in_payload(self):
        c, inv, _ = self.authorities()
        item = c['extra_files'].pop(2)
        inv['inputs'][item['path']] = {k: item[k] for k in ('sha256', 'bytes')}
        for rel, dst, r in O.payload_rows(inv, c, 'inputs'):
            O.copy_exact(dst, self.home/'incoming'/rel, r)
        lookup = O.payload_lookup(self.home/'incoming', c, inv)
        self.assertEqual(O.sha(lookup({k: item[k] for k in ('path', 'sha256')})), item['sha256'])

    def test_full_source_includes_tests_and_rejects_extra_python(self):
        files = {'bot/__init__.py': b'', 'bot/pretrain_v1/a.py': b'x=1\n',
                 'bot/pretrain_v1/tests/test_a.py': b'# test\n', 'bot/pretrain_v1/catalog/catalog.json': b'{}'}
        for name, data in files.items():
            p = O.DRIVER/name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        refs = {n: row(v) for n, v in files.items()}
        inv = dict(source_files=refs, source_sha256=O.digest({n: v['sha256'] for n, v in refs.items()
                    if n.startswith('bot/pretrain_v1/') and n.endswith('.py')}))
        O.verify_source(inv)
        (O.DRIVER/'bot/pretrain_v1/extra.py').write_text('')
        with self.assertRaisesRegex(ValueError, 'extra/missing'):
            O.verify_source(inv)
        (O.DRIVER/'bot/pretrain_v1/extra.py').unlink()
        (O.DRIVER/'bot/pretrain_v1/tests/test_a.py').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'hash changed'):
            O.verify_source(inv)

    def test_ready_trees_reject_extra_changed_and_linked_files(self):
        config, manifest = {}, {}
        for key, location in (('files', 'runtime'), ('source_files', 'actor_source')):
            p = O.READY/location/'module.py'
            p.parent.mkdir(parents=True)
            p.write_bytes(b'pinned ready source')
            config[location] = str(p.parent)
            manifest[key] = {'module.py': O.sha(p)}
        config['runtime_manifest'] = self.put('joint.json', manifest)
        inv = {'joint_sha256': config['runtime_manifest']['sha256']}
        with patch.object(O, 'READY_COUNTS', {'files': 1, 'source_files': 1}):
            O.verify_ready(config, inv)
            extra = O.READY/'actor_source/untracked.py'
            extra.write_bytes(b'fallback source')
            with self.assertRaisesRegex(ValueError, 'extra/missing'):
                O.verify_ready(config, inv)
            extra.unlink()
            p = O.READY/'runtime/module.py'
            p.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'ready source changed'):
                O.verify_ready(config, inv)
            p.unlink()
            p.symlink_to(O.READY/'actor_source/module.py')
            with self.assertRaisesRegex(ValueError, 'contains link'):
                O.verify_ready(config, inv)

    def lease_fixture(self):
        now = O.utc('2026-10-22T22:00:00Z')
        lease = dict(project='clasher', coordinator_thread='test-thread', granted_by='test-parent',
            start_utc='2026-10-22T20:00:00Z', expected_end_utc='2026-10-25T07:53:00Z',
            reclaim=False, refused=False, status='active', max_workers=96, pss_cap_gb=64)
        S = O.r37()  # Module load only. No scans, telemetry, admission or live state calls.
        S.LEASE_DIR, S.STATE_ROOT = str(self.root/'leases'), str(self.root/'state')
        Path(S.LEASE_DIR).mkdir()
        leasepath = Path(S.LEASE_DIR)/'127x09.json'
        leasepath.write_bytes(O.encoded(lease))
        state = Path(S.STATE_ROOT)/'127x09'
        state.mkdir(parents=True)
        watcher = dict(pid=3363731, start=245569826, boot='test-boot')
        (state/'supervisor.json').write_bytes(O.encoded(watcher))
        status = dict(status='watching', reason=None, utc='2026-10-22T22:00:00Z', boot='test-boot',
            observed_lease=dict(valid=True, observed_at=now, sha256=O.sha(leasepath)),
            lease_identity=S.lease_identity(lease))
        (state/'status.json').write_bytes(O.encoded(status))
        S.boot_id = lambda: 'test-boot'
        S.alive = lambda pid, start: (pid, start) == (3363731, 245569826)
        return S, lease, leasepath, state, status, now

    def test_active_lease_reopened_by_path_and_refused_or_reclaim_stops(self):
        S, lease, path, state, status, now = self.lease_fixture()
        O.check_lease(S, '127x09', 24000, now)
        for key in ('reclaim', 'refused'):
            replacement = path.with_name('replacement')
            replacement.write_bytes(O.encoded(dict(lease, **{key: True})))
            os.replace(replacement, path)  # Independent arbitrary writer, no cooperative lock.
            with self.assertRaisesRegex(ValueError, 'reclaim/refused'):
                O.check_lease(S, '127x09', 24000, now)

    def test_stale_observation_changed_watcher_and_short_horizon(self):
        S, lease, path, state, status, now = self.lease_fixture()
        with self.assertRaisesRegex(ValueError, 'stale/ending'):
            O.check_lease(S, '127x09', 10, now+61)
        with self.assertRaisesRegex(ValueError, 'horizon'):
            O.check_lease(S, '127x09', 7*86400, now)
        S.alive = lambda *_: False
        with self.assertRaisesRegex(ValueError, 'watcher identity'):
            O.check_lease(S, '127x09', 10, now)

    def test_missing_lease_is_not_an_admission(self):
        S, lease, path, state, status, now = self.lease_fixture()
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            O.check_lease(S, '127x09', 10, now)

    def test_r37_unreadable_300_second_window_and_latched_refusal(self):
        S, lease, path, state, status, now = self.lease_fixture()
        st = SimpleNamespace(dir=str(state), h='127x09', requests=lambda: [], request_issues={})
        S.now = lambda: now
        sv = S.Supervisor(st, str(path))
        self.assertIsNotNone(sv.observe_lease())
        path.write_bytes(b'partial arbitrary writer')
        self.assertIsNone(sv.observe_lease())
        S.now = lambda: now+300
        self.assertIsNone(sv.observe_lease())
        self.assertIsNone(sv.ending)
        S.now = lambda: now+301
        self.assertIsNone(sv.observe_lease())
        self.assertEqual(sv.ending, 'lease unreadable')
        other = S.Supervisor(st, str(path))
        path.write_bytes(O.encoded(dict(lease, refused=True, status=None)))
        self.assertIsNone(other.observe_lease())  # Malformed schema cannot conceal the trigger.
        self.assertEqual(other.ending, 'refused')
        path.write_bytes(O.encoded(lease))
        other.observe_lease()
        self.assertEqual(other.ending, 'refused')

    def test_resource_caps_count_all_processes_and_pss_not_only_learner(self):
        procs = {i: dict(nice=10, clasher=True) for i in range(64)}
        S = SimpleNamespace(scan=lambda: procs, is_clasher=lambda p: p['clasher'],
            pss_bytes=lambda pid: 1 << 30, host_load=lambda: (64 << 30, 1))
        O.check_resources(S, 64, 64)
        for kwargs in ({'reserve_procs': 1}, {'reserve_pss': 1}):
            with self.assertRaises(ValueError):
                O.check_resources(S, 64, 64, **kwargs)
        procs[0]['nice'] = 0
        with self.assertRaisesRegex(ValueError, 'mem/load/nice'):
            O.check_resources(S, 64, 64)
        procs[0]['nice'] = 10
        S.host_load = lambda: (31 << 30, 1)
        with self.assertRaisesRegex(ValueError, 'mem/load/nice'):
            O.check_resources(S, 64, 64)
        S.host_load = lambda: (64 << 30, 91)
        with self.assertRaisesRegex(ValueError, 'mem/load/nice'):
            O.check_resources(S, 64, 64)

    def test_whole_tree_cleanup_includes_detached_token_and_descendants(self):
        S = O.r37()
        me = os.getpid()
        token = 'a'*32
        def proc(ppid, sid, start, marker=False):
            return dict(ppid=ppid, sid=sid, start=start, nice=10, cwd='', cmd=b'',
                        env=('CLASHER_LEASE_JOB='+token).encode() if marker else b'')
        procs = {me: proc(1, me, 1), 700001: proc(me, me, 2),
                 700002: proc(700001, 700002, 3), 700003: proc(1, 700003, 4, True),
                 700004: proc(1, 700004, 5)}
        S.scan = lambda: dict(procs)
        S.boot_id = lambda: 'fixture'
        S.proc_stat = lambda pid: None if pid not in procs else ('S', procs[pid]['ppid'],
                     procs[pid]['sid'], 10, procs[pid]['start'])
        signalled = []
        def exact(pid, start, sig):
            self.assertEqual(start, procs[pid]['start'])
            signalled.append((pid, sig))
            del procs[pid]
        S.signal_exact = exact
        job = O.Job.__new__(O.Job)
        job.S, job.children = S, []
        job.record = dict(pid=me, start=1, token=token, boot='fixture', procs=[[me, 1]])
        job.cleanup()
        self.assertEqual({pid for pid, _ in signalled}, {700001, 700002, 700003})
        self.assertIn(700004, procs)
        self.assertIn(me, procs)

    def test_stuck_cleanup_escalates_only_exact_owned_identities_within_bound(self):
        job = O.Job.__new__(O.Job)
        child = dict(start=123)
        job.children, job.record = [], {'procs': []}
        live, signals = {700001: child}, []
        job.members = lambda: dict(live)
        def exact(pid, start, sig):
            signals.append((pid, start, sig))
            if sig == signal.SIGKILL:
                live.pop(pid)
        job.S = SimpleNamespace(proc_stat=lambda _: None, signal_exact=exact)
        clock = [0.0]
        with patch.object(O.time, 'monotonic', lambda: clock[0]), patch.object(O.time, 'sleep',
                lambda seconds: clock.__setitem__(0, clock[0]+seconds)):
            job.cleanup()
        self.assertTrue(any(sig == signal.SIGKILL for _, _, sig in signals))
        self.assertLess(clock[0], 11)
        self.assertTrue(all((pid, start) == (700001, 123) for pid, start, _ in signals))

    def test_cpu_child_failure_and_timeout_use_bounded_owned_cleanup(self):
        # Launch only these known disposable CPU children. No /proc scan of current jobs.
        S = O.r37()
        job = O.Job.__new__(O.Job)
        job.children, job.tick = [], lambda: None
        job.S = SimpleNamespace(proc_stat=S.proc_stat, signal_exact=S.signal_exact)
        job.record = {'procs': []}
        def members():
            out = {}
            for child in job.children:
                st = S.proc_stat(child.pid)
                if st is not None and st[0] not in 'ZX':
                    out[child.pid] = {'start': st[4]}
            return out
        job.members = members
        with self.assertRaisesRegex(ValueError, 'child failed'):
            job.run([sys.executable, '-B', '-c', 'raise SystemExit(3)'], os.environ.copy(), 3)
        with self.assertRaisesRegex(ValueError, 'deadline'):
            job.run([sys.executable, '-B', '-c', 'import time; time.sleep(30)'], os.environ.copy(), .05)
        job.cleanup()
        self.assertTrue(all(p.poll() is not None for p in job.children))

    def test_failed_readiness_receipt_cannot_authorize_soak(self):
        c, inv, _ = self.authorities()
        p = O.receipt_path(c, 'inputs')
        O.write_new(p, dict(status='failed', host='127x09', phase='inputs'))
        with self.assertRaisesRegex(ValueError, 'receipt mismatch'):
            O.verify_receipt(c, inv, 'inputs')

    def test_next_phase_requires_prior_root_gone_and_no_whole_tree_survivors(self):
        c, inv, _ = self.authorities()
        record = dict(state='running', token='a'*32, boot='fixture')
        path = self.root/'state/127x09/jobs'/ (c['job_names']['source']+'.json')
        path.parent.mkdir(parents=True)
        path.write_bytes(O.encoded(record))
        S = SimpleNamespace(STATE_ROOT=str(self.root/'state'), boot_id=lambda: 'fixture', scan=lambda: {},
                            owned=Mock(return_value={}))
        with patch.object(O, 'verify_receipt', return_value={'lease_token': 'a'*32}):
            with self.assertRaisesRegex(ValueError, 'not R37 gone'):
                O.phase_done(S, c, inv, 'source')
            record['state'] = 'gone'
            path.write_bytes(O.encoded(record))
            S.owned.return_value = {700001: {'start': 123}}
            with self.assertRaisesRegex(ValueError, 'survivors'):
                O.phase_done(S, c, inv, 'source')
            S.owned.return_value = {}
            O.phase_done(S, c, inv, 'source')

    def test_readiness_failure_keeps_attempt_without_success_or_soak(self):
        c, inv, config = self.authorities()
        job = SimpleNamespace(record={'token': 'a'*32}, started=O.time.monotonic(), tick=Mock(),
                              cleanup=Mock(), peak_procs=1, peak_pss=1)
        def failed_probe(argv, env, seconds, result):
            O.write_new(result, {'source_sha256': inv['source_sha256'], 'cuda_initialized': True,
                                  'audit': {'status': 'NO-GO'}})
        job.run = Mock(side_effect=failed_probe)
        with patch.object(O, 'r37', return_value=SimpleNamespace(EXIT_MARGIN=600)), \
             patch.object(O, 'check_lease'), patch.object(O, 'Job', return_value=job), \
             patch.object(O, 'check_authority', return_value=config), patch.object(O, 'payload_rows', return_value=[]), \
             patch.object(O, 'phase_done'), patch.object(O, 'verify_source'), patch.object(O, 'verify_ready'), \
             patch.object(O.signal, 'signal'), patch.object(O.signal, 'setitimer'), \
             patch.object(O.ctypes, 'CDLL', return_value=SimpleNamespace(prctl=lambda *_: 0)):
            with self.assertRaisesRegex(ValueError, 'CPU readiness failure'):
                O.run_job(c, inv, 'inputs', self.home/'incoming')
        self.assertFalse(O.receipt_path(c, 'inputs').exists())
        self.assertTrue((self.home/'hosts/127x09/inputs.attempt.json').exists())
        self.assertEqual(job.run.call_count, 1)
        job.cleanup.assert_called_once_with(cooperative=0)

    def test_owned_staging_budget_is_enforced_separately_from_global_caps(self):
        job = O.Job.__new__(O.Job)
        job.started, job.last, job.limit, job.stopping = O.time.monotonic(), 0, 300, False
        job.stop_at, job.stop_file = O.time.time()+1000, self.home/'none.stop'
        job.c, job.phase, job.peak_procs, job.peak_pss = {'host': '127x09'}, 'source', 0, 0
        job.members = lambda: {i: {} for i in range(4)}
        job.S = SimpleNamespace(pss_bytes=lambda _: 1)
        with patch.object(O, 'check_lease', return_value=(0, 96, 64)), patch.object(O, 'check_resources'):
            with self.assertRaisesRegex(ValueError, 'owned job'):
                job.tick()
            job.members = lambda: {1: {}}
            job.S.pss_bytes = lambda _: 5 << 30
            with self.assertRaisesRegex(ValueError, 'owned job'):
                job.tick()

    def test_env_preserves_lease_and_device_and_sets_thread_one(self):
        inherited = dict(CLASHER_LEASE_JOB='a'*32, CLASHER_LEASE_STOP_FILE='/fixture/test.stop',
            CLASHER_LEASE_STOP_BY_UTC='2026-10-24T00:00:00Z', CUDA_VISIBLE_DEVICES='GPU-fixture',
            PYTHONPATH='/unreviewed', CLASHER_ROOT='/old', OMP_NUM_THREADS='128')
        with patch.dict(os.environ, inherited):
            cpu, gpu = O.environment(True), O.environment(False)
        for k in ('CLASHER_LEASE_JOB', 'CLASHER_LEASE_STOP_FILE', 'CLASHER_LEASE_STOP_BY_UTC'):
            self.assertEqual(gpu[k], inherited[k])
        self.assertEqual(gpu['CUDA_VISIBLE_DEVICES'], 'GPU-fixture')
        self.assertEqual(cpu['CUDA_VISIBLE_DEVICES'], '')
        self.assertNotIn('PYTHONPATH', gpu)
        self.assertNotIn('CLASHER_ROOT', gpu)
        self.assertTrue(all(gpu[k] == '1' for k in O.THREADS))


class FrozenInventory(unittest.TestCase):
    def test_exact_reviewed_source_aggregate_and_402_paths(self):
        inv = O.read_json(O.HERE/'inventory.json')
        self.assertEqual(inv['source_commit'], 'fe6d64214200679372f337bb37b33606f5c9997d')
        py = {n: r['sha256'] for n, r in inv['source_files'].items()
              if n.startswith('bot/pretrain_v1/') and n.endswith('.py')}
        self.assertEqual(len(py), 83)
        self.assertEqual(O.digest(py), 'ff71c87aa81d069f2574dcb30aff0df988a56a7a20d7b925a96f1441c669dd0e')
        self.assertTrue(any('/tests/' in n for n in py))
        self.assertEqual(len(inv['source_files']), 96)
        source = Path('/mpac/sdicks02/repos/clasher-pv1-input-roots-20261022')
        for name, frozen in inv['source_files'].items():
            O.verify(source/name, frozen)
        self.assertEqual(len(inv['inputs']), 402)
        for path in inv['inputs']:
            self.assertTrue(path.startswith('/mpac/sdicks02/jobs/clasher/rl-input-roots-20261022/prepared-attempt2/files/'))
        self.assertEqual({k: x['host'] for k, x in inv['prepared_config_values'].items()},
                         {'127x09': '127x09', '127x12': '127x12'})
        for ref in inv['prepared_configs']:
            self.assertEqual(O.sha(ref['path']), ref['sha256'])
            config = O.read_json(ref['path'])
            self.assertEqual(config, inv['prepared_config_values'][config['host']])


if __name__ == '__main__':
    unittest.main(verbosity=2)
