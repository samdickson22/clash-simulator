import hashlib,json,os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import guard_regret04 as g

class Tests(unittest.TestCase):
    def test_receipt_pressure_and_slot(self):
        with tempfile.TemporaryDirectory(dir='/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r1/tmp') as d:
            j=Path(d);a=j/'REGRET04-AUTHORITY.json';a.write_text('{}')
            (j/'REGRET04-ADMITTED.json').write_text(json.dumps(dict(host='127x04',regret_only=True,authority_sha256=hashlib.sha256(a.read_bytes()).hexdigest())))
            with patch.object(g.socket,'gethostname',return_value='127x04'),patch.object(g.os,'getpriority',return_value=19),patch.object(g.os,'sched_getscheduler',return_value=os.SCHED_OTHER),patch.object(g.os,'sched_getaffinity',return_value={19}),patch.object(g,'conflicts',return_value=[]),patch.object(g,'full_pressure',return_value=0.):
                self.assertTrue(g.allowed(j,manager=True));self.assertFalse(g.allowed(j))
                h=j/'REGRET04-HEARTBEAT.json';h.write_text(json.dumps(dict(allowed=True,checked_epoch=time.time())))
                self.assertTrue(g.allowed(j))
                with patch.object(g,'full_pressure',return_value=10.01):self.assertFalse(g.allowed(j,manager=True))
                for core in (0,11,47,52,116,118,126):
                    with patch.object(g.os,'sched_getaffinity',return_value={core}):self.assertFalse(g.allowed(j,manager=True))
                with patch.object(g.os,'getpriority',return_value=10):self.assertFalse(g.allowed(j,manager=True))
                h.write_text(json.dumps(dict(allowed=True,checked_epoch=time.time()-7)));self.assertFalse(g.allowed(j))
                with patch.object(g.time,'time',return_value=g.DEADLINE):self.assertFalse(g.allowed(j,manager=True))
                with patch.object(g,'conflicts',return_value=[123]):self.assertFalse(g.allowed(j,manager=True))
                (j/'REGRET04.STOP').touch();self.assertFalse(g.allowed(j,manager=True))
if __name__=='__main__':unittest.main()
