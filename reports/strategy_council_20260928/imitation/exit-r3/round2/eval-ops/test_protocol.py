import unittest
from protocol import arm_list,decision,order,BASES
class ProtocolTest(unittest.TestCase):
    def test_descriptive_never_adopt_even_clear_win(self):
        r=decision('descriptive',-.05);self.assertTrue(r['paired_gate_passed']);self.assertFalse(r['survives']);self.assertFalse(r['adoption_eligible']);self.assertTrue(r['never_adoptable'])
    def test_stage2_boundary_kills(self):
        self.assertFalse(decision('stage2',0)['survives']);self.assertTrue(decision('stage2',-.00001)['survives'])
    def test_no_killed_round2_arms(self):
        d={a:dict(stage1_complete=True,survives=a=='R3d') for a in ('R3c','R3d','R3e')};self.assertEqual(arm_list('stage2',d),['K0','R3d']);d['R3c']['stage1_complete']=False
        with self.assertRaises(AssertionError):arm_list('stage2',d)
    def test_complete_rotation(self):
        a=['K0','R3c','R3d'];self.assertEqual([order(a,i) for i in range(3)],[a,['R3c','R3d','K0'],['R3d','K0','R3c']]);self.assertEqual(a,['K0','R3c','R3d'])
    def test_reserved_reporting_and_smoke(self):
        self.assertEqual(BASES['descriptive'],(4503602507370496,4503602517370496));self.assertEqual(BASES['stage2'],(4503602407370496,4503602417370496))
if __name__=='__main__':unittest.main()
