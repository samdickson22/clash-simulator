import unittest
from actuator import Actuator,Hud

class ActuatorTest(unittest.TestCase):
    def test_stale_double_spend_and_confirm(self):
        a=Actuator();h=Hud(1.,('Hog','Ice','Log','Cannon'),4.,'Musketeer')
        self.assertEqual(a.submit('Hog',4,(4.5,24.5),h,1.)['state'],'tap')
        self.assertEqual(a.effective(h)[0],0)
        self.assertEqual(a.effective(h)[1][0],'Musketeer')
        self.assertEqual(a.submit('Hog',4,(4.5,24.5),h,1.02)['reason'],'pending')
        self.assertEqual(a.observe(h,1.02)['state'],'pending')
        self.assertEqual(a.observe(Hud(1.3,('Musketeer','Ice','Log','Cannon'),0),1.3)['state'],'accepted')
        self.assertEqual(a.submit('Ice',1,(4,24),h,1.3)['reason'],'stale')
    def test_one_elixir_card_requires_a_real_spend(self):
        a=Actuator();h=Hud(1,('Skeletons','Ice','Log','Cannon'),2,'Hog')
        a.submit('Skeletons',1,(4.5,20.5),h,1)
        self.assertEqual(a.observe(Hud(1.2,('Hog','Ice','Log','Cannon'),2),1.2)['state'],'pending')
        self.assertEqual(a.observe(Hud(1.3,('Hog','Ice','Log','Cannon'),1),1.3)['state'],'accepted')
    def test_retry_once_and_hold(self):
        a=Actuator();h=lambda t:Hud(t,('Hog','Ice','Log','Cannon'),4.,'Musketeer')
        a.submit('Hog',4,(4,24),h(1),1)
        deadline=1+a.verify_seconds
        self.assertEqual(a.observe(h(1.8),1.8)['state'],'pending')
        self.assertEqual(a.observe(h(deadline),deadline)['state'],'pending')
        retry=deadline+.16
        self.assertEqual(a.observe(h(retry),retry)['attempt'],2)
        self.assertEqual(a.effective(h(retry+.01))[0],0)
        end=retry+a.verify_seconds+.201
        self.assertEqual(a.observe(h(end),end)['state'],'failed')
        self.assertEqual(a.submit('Hog',4,(4,24),h(end+.01),end+.01)['reason'],'hold')
    def test_backend_config_and_deadline_rollback(self):
        import json,tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'timing.json'
            path.write_text(json.dumps({'backends':{'fixture':{'p99_ms':1234}}}))
            a=Actuator(backend='fixture',timing_path=path)
            self.assertAlmostEqual(a.verify_seconds,1.834)
        h=Hud(1,('Hog','Ice','Log','Cannon'),4,'Musketeer')
        a.submit('Hog',4,(4,24),h,1)
        deadline=1+a.verify_seconds
        self.assertEqual(a.observe(h,deadline+.199)['state'],'pending')
        self.assertEqual(a.effective(h)[0],0)
        self.assertEqual(a.observe(h,deadline+.201)['state'],'failed')
        self.assertEqual(a.effective(h)[0],4)
    def test_retry_requires_present_affordable_fresh_card(self):
        for hand,elixir,stale in [(('Ice','Log','Cannon','Musketeer'),4,False),
                                  (('Hog','Ice','Log','Cannon'),3,False),
                                  (('Hog','Ice','Log','Cannon'),4,True)]:
            a=Actuator();h=Hud(1,('Hog','Ice','Log','Cannon'),4,'Musketeer')
            a.submit('Hog',4,(4,24),h,1)
            now=1+a.verify_seconds+.16
            after=Hud(1 if stale else now,hand,elixir)
            self.assertEqual(a.observe(after,now)['state'],'pending')
            self.assertEqual(a.pending.attempts,1)
    def test_native_delay_does_not_trigger_early_retry(self):
        a=Actuator();h=Hud(1,('Hog','Ice','Log','Cannon'),4,'Musketeer')
        a.submit('Hog',4,(4,24),h,1)
        for now in [1.61,1.77,1.81,2.1]:
            self.assertEqual(a.observe(Hud(now,h.hand,4),now)['state'],'pending')
        self.assertEqual(a.observe(Hud(2.15,('Musketeer','Ice','Log','Cannon'),0),2.15)['state'],'accepted')
    def test_remap_freshness_and_false_positive(self):
        a=Actuator();h=Hud(1,('Ice','Hog','Log','Cannon'),7,'Musketeer')
        self.assertEqual(a.submit('Hog',4,(4,24),h,1)['slot'],1)
        self.assertEqual(a.observe(Hud(1.2,('Ice','Musketeer','Log','Cannon'),7),1.2)['state'],'pending')
        self.assertEqual(a.observe(Hud(.9,('Ice','Musketeer','Log','Cannon'),3),1.3)['state'],'pending')
if __name__=='__main__':unittest.main()
