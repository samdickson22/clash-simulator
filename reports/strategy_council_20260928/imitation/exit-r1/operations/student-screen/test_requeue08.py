"""Identity recovery must retain terminal cases and reject seed substitution."""
import unittest
from requeue08 import unfinished
from imitation.exit_r1.screen import BASES

class Recover08(unittest.TestCase):
    def test_requeue_only_unfinished(self):
        tasks=[['fallback','S-teacher',i] for i in range(3)]
        record=dict(mode='fallback',arm='S-teacher',index=1,terminal=True,
                    freeze_sha256='sha',seed=BASES['fallback']+1,seat=1)
        self.assertEqual(unfinished(tasks,[record],'sha',BASES),[tasks[0],tasks[2]])
    def test_reject_seed_and_duplicate(self):
        tasks=[['fallback','S-teacher',0]]
        record=dict(mode='fallback',arm='S-teacher',index=0,terminal=True,
                    freeze_sha256='sha',seed=BASES['fallback'],seat=0)
        with self.assertRaises(AssertionError):unfinished(tasks,[dict(record,seed=0)],'sha',BASES)
        with self.assertRaises(AssertionError):unfinished(tasks,[record,record],'sha',BASES)
