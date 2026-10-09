import json
import os
from pathlib import Path
import tempfile
import unittest
import numpy as np
import torch
from .pack import pack
from .rows import sha,write_json
from .screen import ARMS,BASES,COUNTS,verify_freeze,reduce_games
from .screen_metrics import diagnostics,paired_interval,decide
from .student import TeacherStore


class ScreenTests(unittest.TestCase):
    def test_all_wait_collapse_and_ci_kills(self):
        teacher=np.array([0,1,2304,2304])
        collapse=diagnostics(teacher,np.zeros(4),np.ones(4))
        favorable=paired_interval(np.zeros(600),np.ones(600))
        self.assertEqual(len(decide(collapse,favorable)['kill_reasons']),2)
        good=diagnostics(teacher,np.array([1.,1.,0.,0.]),np.array([0.,0.,1.,1.]))
        self.assertTrue(decide(good,favorable)['survives'])
        equal=paired_interval(np.ones(600),np.ones(600))
        self.assertFalse(decide(good,equal)['survives'])
        excessive=dict(good,student_wait_rate=.76)
        self.assertIn('WAIT rate exceeds 1.5 times teacher',decide(excessive,favorable)['kill_reasons'])
        self.assertEqual(favorable,paired_interval(np.zeros(600),np.ones(600)))

    def test_reporting_requires_complete_audit_and_immutable_inputs(self):
        with tempfile.TemporaryDirectory(dir='/mpac/sdicks02') as tmp:
            root=Path(tmp);plan=root/'plan.md';plan.write_text('test plan')
            audit=root/'audit.json';freeze=root/'freeze.json'
            seeds=[BASES[k]+i for k in COUNTS for i in range(COUNTS[k])]
            write_json(audit,dict(passed=True,proposed=seeds))
            f=dict(seed_audit=str(audit),files={str(plan):sha(plan),str(audit):sha(audit)})
            write_json(freeze,f);verify_freeze(freeze,sha(freeze))
            plan.write_text('changed')
            with self.assertRaisesRegex(ValueError,'frozen input changed'):verify_freeze(freeze,sha(freeze))
            f['files'][str(plan)]=sha(plan);write_json(audit,dict(passed=True,proposed=seeds[:-1]))
            f['files'][str(audit)]=sha(audit);write_json(freeze,f)
            with self.assertRaisesRegex(ValueError,'entire screen'):verify_freeze(freeze,sha(freeze))

    def test_reducer_requires_paired_seed_identity_and_common_freeze(self):
        with tempfile.TemporaryDirectory(dir='/mpac/sdicks02') as tmp:
            root=Path(tmp);counts=dict(h2h=2,fallback=2)
            diag={arm:dict(play_recall=.9,teacher_wait_rate=.5,student_wait_rate=.5,freeze_sha256='pin') for arm in ARMS}
            for mode in counts:
                for arm in (*ARMS,'init') if mode=='fallback' else ARMS:
                    for i in range(counts[mode]):
                        write_json(root/f'{mode}-{arm}-{i:04d}.json',dict(mode=mode,arm=arm,index=i,
                            seed=BASES[mode]+i,terminal=True,loss=float(arm=='init'),win=float(arm!='init'),
                            draw=False,freeze_sha256='pin'))
            results=reduce_games(root,diag,counts,freeze_sha256='pin')
            self.assertTrue(all(r['survives'] for r in results.values()))
            path=root/'fallback-S-mix-0000.json';r=json.loads(path.read_text());r['seed']+=1;write_json(path,r)
            with self.assertRaisesRegex(ValueError,'case identity'):reduce_games(root,diag,counts,freeze_sha256='pin')
            r['seed']-=1;r['freeze_sha256']='other';write_json(path,r)
            with self.assertRaisesRegex(ValueError,'execution freeze'):reduce_games(root,diag,counts,freeze_sha256='pin')

    @unittest.skipUnless(os.environ.get('EXIT_R1_TEST_GAMES'),'needs two real sealed teacher games')
    def test_real_v6_pack_preserves_batch_ragged_scores_and_boundaries(self):
        games=[Path(x) for x in os.environ['EXIT_R1_TEST_GAMES'].split(':')]
        assets=os.environ['EXIT_R1_TEST_ASSETS']
        import shutil
        with tempfile.TemporaryDirectory(dir='/mpac/sdicks02') as tmp:
            root=Path(tmp);sources=root/'sources';sources.mkdir()
            for i,g in enumerate(games): (sources/f'game-{i:09d}').symlink_to(g,target_is_directory=True)
            out=root/'packed';seal=pack([sources],out)
            self.assertTrue(seal['complete']);merged=TeacherStore(out,assets)
            offset=0
            for episode,game in enumerate(games):
                source=TeacherStore(game,assets)
                ix=np.array([0,len(source)//2,len(source)-1]);a,y=source.batch(ix);b,z=merged.batch(ix+offset)
                for k in a:self.assertTrue(torch.equal(a[k],b[k]),k)
                for k in ('action','root_actions','root_scores','root_valid','outcome','supervised'):
                    self.assertTrue(torch.equal(y[k],z[k]),k)
                np.testing.assert_array_equal(merged.arrays['episode_ids'][offset:offset+len(source)],episode)
                offset+=len(source)
            self.assertEqual(len(merged),offset)
            np.testing.assert_array_equal(merged.arrays['row_ids'],np.arange(offset))
            with self.assertRaisesRegex(ValueError,'fresh output'):pack([sources],out)
            altered=out/'train/root_scores.npy'
            with altered.open('r+b') as f:f.seek(-1,2);f.write(b'X')
            with self.assertRaisesRegex(ValueError,'SHA mismatch'):TeacherStore(out,assets)


if __name__=='__main__':unittest.main()
