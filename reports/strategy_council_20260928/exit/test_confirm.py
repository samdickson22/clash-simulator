"""No-game checks of preregistered schedules, pairing and gate boundaries."""
import unittest
from unittest.mock import patch
import confirm as c
from confirm_seed_audit import proposed

class ConfirmationTests(unittest.TestCase):
    def test_schedules(self):
        reserved={s for seeds in proposed().values() for s in seeds}
        all_seeds=set()
        for it,total,h2h_count,holdout,hog in [(1,640,256,128,64),(2,256,128,64,0),(3,256,128,64,0)]:
            specs=list(c.specs(it));self.assertEqual(len(specs),total)
            self.assertEqual(len({c.evaluate.identifier(s) for s in specs}),total)
            h=[s for s in specs if s['mode']=='h2h'];self.assertEqual(len(h),h2h_count)
            self.assertEqual(sum(s['role']=='hog26' for s in h),86 if it==1 else 44)
            for a,b in zip(h[::2],h[1::2]):
                self.assertEqual(a['game']//2,b['game']//2);self.assertEqual(a['role'],b['role'])
            for role,n in [('holdout',holdout),('hog26',hog)]:
                for name in ('initial','student'):
                    self.assertEqual(sum(s['role']==role and s['which']==name and s['mode']=='scripts' for s in specs),n)
            seeds={s['seed']+(s['game']//2)*1009 for s in specs}
            self.assertFalse(seeds&all_seeds);self.assertTrue(seeds<=reserved);all_seeds|=seeds
            self.assertEqual(len(seeds),h2h_count//2+holdout//2+hog//2)

    def test_gate_boundaries(self):
        def gate(i,score=.55,low=.501,drop=.05,upper=.099):return c.gates(i,dict(rate=score,ci95=[low,.9]),dict(rate=drop,ci95=[-.1,upper]))['accepted']
        self.assertTrue(gate(1));self.assertFalse(gate(1,score=.549))
        self.assertFalse(gate(1,low=.5));self.assertFalse(gate(1,upper=.1))
        self.assertFalse(gate(1,drop=.050001));self.assertTrue(gate(2,score=.5,low=.451,upper=.5))
        self.assertFalse(gate(2,low=.45));self.assertFalse(gate(3,drop=.051))

    def test_previous_proposer(self):
        self.assertEqual(c.checkpoints(1)['initial'],c.CHECKPOINT)
        for i in (2,3):self.assertEqual(c.checkpoints(i)['initial'],c.checkpoints(i-1)['student'])

    def test_fixed_world_decks(self):
        class Env:
            def reset(self,**kwargs):self.kwargs=kwargs
        class Ctx:
            def __init__(self):self.e={0:Env(),1:Env()}
            def envs(self,*args):return self.e
            def pools(self,role):return ('candidate','training')
        ctx=Ctx()
        for role,second in [('holdout','training'),('hog26','candidate')]:
            with patch.object(c.cl_eval,'_sample_paired_ordered_decks',return_value=[['A'],['B']]) as sample:
                x,dx=c.reset_pair(ctx,role,42,0,symmetric=True)
                y,dy=c.reset_pair(ctx,role,42,1,symmetric=True)
                self.assertEqual(dx,dy);self.assertEqual(x.kwargs,y.kwargs)
                sample.assert_called_with('candidate',second,matchup_seed=42)
        with patch.object(c,'reset',return_value='original') as reset:
            self.assertEqual(c.reset_pair(ctx,'holdout',42,1,symmetric=False),'original')
            reset.assert_called_once_with(ctx,'holdout',42,1)

    def test_pair_bootstrap(self):
        self.assertEqual(c.summary([1,0]*128)['ci95'],[.5,.5])
        self.assertEqual(c.summary([-.5,.5]*64)['ci95'],[0.,0.])

if __name__=='__main__':unittest.main()
