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
        self.assertEqual(a.observe(h(1.61),1.61)['state'],'pending')
        self.assertEqual(a.observe(h(1.77),1.77)['attempt'],2)
        self.assertEqual(a.effective(h(1.78))[0],0)
        self.assertEqual(a.observe(h(2.58),2.58)['state'],'failed')
        self.assertEqual(a.submit('Hog',4,(4,24),h(2.6),2.6)['reason'],'hold')
    def test_remap_freshness_and_false_positive(self):
        a=Actuator();h=Hud(1,('Ice','Hog','Log','Cannon'),7,'Musketeer')
        self.assertEqual(a.submit('Hog',4,(4,24),h,1)['slot'],1)
        self.assertEqual(a.observe(Hud(1.2,('Ice','Musketeer','Log','Cannon'),7),1.2)['state'],'pending')
        self.assertEqual(a.observe(Hud(.9,('Ice','Musketeer','Log','Cannon'),3),1.3)['state'],'pending')
if __name__=='__main__':unittest.main()
