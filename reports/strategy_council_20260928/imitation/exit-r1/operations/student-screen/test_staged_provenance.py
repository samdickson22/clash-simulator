"""Metadata-only checks: preserve results and reject mismatched stage inputs."""
import copy
import unittest
from canonicalize_stages import canonical_record
from imitation.exit_r1.screen import BASES,COUNTS

class StageProvenance(unittest.TestCase):
    def setUp(self):
        self.stage=dict(plan_sha256='plan',plan='/plan',seed_audit='/audit',native='/native',
            seed_bases=BASES,counts=COUNTS,files={'/init':'init-sha','/native':'native-sha'},checkpoints={'init':'/init'})
        self.final=copy.deepcopy(self.stage);self.final['checkpoints']['S-human']='/human'
        self.final['files']['/human']='human-sha'
        self.raw=dict(mode='fallback',arm='init',index=0,seed=BASES['fallback'],seat=0,
            terminal=True,freeze_sha256='stage-sha',loss=1.0,win=0.0,draw=False,
            stats=[{'deadlines':[{'completed':2,'wall_seconds':0.19}]}],command_sha256='command')
    def test_preserves_every_scientific_result(self):
        result=canonical_record(self.raw,self.stage,'stage-sha',self.final,'final-sha','raw-sha')
        for key,value in self.raw.items():
            if key!='freeze_sha256':self.assertEqual(result[key],value)
        self.assertEqual(self.raw['freeze_sha256'],'stage-sha')
        self.assertEqual(result['stage_case_sha256'],'raw-sha')
    def test_rejects_changed_runtime_sha(self):
        bad=copy.deepcopy(self.stage);bad['files']['/native']='tampered'
        with self.assertRaises(AssertionError):canonical_record(self.raw,bad,'stage-sha',self.final,'final-sha','raw-sha')
    def test_rejects_wrong_checkpoint(self):
        bad=copy.deepcopy(self.stage);bad['checkpoints']['init']='/different-init'
        with self.assertRaises(AssertionError):canonical_record(self.raw,bad,'stage-sha',self.final,'final-sha','raw-sha')
    def test_rejects_seed_schedule_change(self):
        bad=copy.deepcopy(self.raw);bad['seed']+=1
        with self.assertRaises(AssertionError):canonical_record(bad,self.stage,'stage-sha',self.final,'final-sha','raw-sha')

if __name__=='__main__':unittest.main()
