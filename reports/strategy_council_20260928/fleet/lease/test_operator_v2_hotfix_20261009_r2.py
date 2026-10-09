import importlib.util
import json
from pathlib import Path
import signal
import socket
from unittest.mock import patch
import unittest

assert socket.gethostname().split('.')[0] == '127x01'
def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
t = module('tests', 'test_watch_v2.py')
# Exercise operator selection of an old revision with the current isolated
# driver. Actual immutable r1 code was also tested on 127x01; see the r1
# scheduled-path and operator validation receipts beside this test.
t.DRIVER = t.DRIVER.replace('spec.loader.exec_module(w)\n',
    "spec.loader.exec_module(w); w.REVISION='v2-hotfix-20261008-r1'\n")
operator = module('operator_helper', 'stop_wrapped_job_v2_hotfix_20261009_r2.py')

class OperatorTests(t.ProcessTests):
    # Run only the additional operator tests below, not the inherited r1 suite.
    def test_operator_stops_r1_group_without_signalling_supervisor(self):
        code = '''import os,signal,time,json
from pathlib import Path
role='parent'
if os.fork()==0:role='child'
signal.signal(signal.SIGTERM,signal.SIG_IGN)
Path('jobs/'+role+'.ready.json').write_text(json.dumps({'pid':os.getpid()}))
while True:time.sleep(.02)
'''
        proc = self.launch('operator-r1',code=code,processes=3)
        identities = [self.wait_file(role+'.ready.json') for role in ('parent','child')]
        self.wait_file('operator-r1.state.json')
        with patch.object(operator.w,'BASE',self.base), patch.object(operator.w,'HOST','127x15'):
            manifest = operator.capture()
            self.assertEqual(len(manifest['jobs']),1)
            operator.stop(manifest,.15)
        receipt = self.finish(proc,'operator-r1','fail')
        self.assertEqual(receipt['exit_code'],-signal.SIGKILL)
        for i in identities:self.assertFalse(Path('/proc',str(i['pid'])).exists())
        self.assertEqual(json.loads((self.base/'jobs/aggregate-v2.json').read_text())['jobs'],{})

    def test_operator_reused_identity_does_not_signal_any_process(self):
        manifest = dict(host=operator.w.HOST, jobs=[dict(label='reused',supervisor_pid=100,
            supervisor_start='old',child_pid=101,child_start='old',known={'101':'old'})])
        rows = {100:(0,'new',0,'S',10,100,100),101:(100,'new',0,'S',10,101,101)}
        with patch.object(operator.w,'processes',return_value=rows), \
                patch.object(operator.w.os,'killpg') as group, patch.object(operator.w.os,'kill') as kill:
            operator.stop(manifest,0)
            group.assert_not_called();kill.assert_not_called()

suite=unittest.TestSuite(OperatorTests(n) for n in (
    'test_operator_stops_r1_group_without_signalling_supervisor',
    'test_operator_reused_identity_does_not_signal_any_process'))
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
