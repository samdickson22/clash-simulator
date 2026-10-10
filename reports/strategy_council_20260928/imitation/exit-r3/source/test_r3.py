import unittest
import numpy as np
import torch
from .student import root_indices, root_loss, advantage_loss, advantage_targets
from imitation.exit_r1.student import teacher_loss
from .network import ModelConfig, SetPolicy, AdvantagePolicy
from imitation.model.network import SetPolicy as R2Policy

class R3Tests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1);torch.manual_seed(123)
    def fixture(self):
        o={k:torch.randn(*shape,requires_grad=True) for k,shape in
            [('gate',(3,3)),('card',(3,4)),('tile',(3,4,576))]}
        o.update(gate_mask=torch.ones(3,3,dtype=torch.bool),card_mask=torch.ones(3,4,dtype=torch.bool),tile_mask=torch.ones(3,4,576,dtype=torch.bool))
        y=dict(root_actions=torch.tensor([[2304,1,2400],[2304,580,2305],[2304,5,2304]]),
            root_scores=torch.tensor([[.01,.02,.012],[.03,.04,.035],[.05,.01,0.]],dtype=torch.float64),
            root_valid=torch.tensor([[True]*3,[True]*3,[True,True,False]]),
            action=torch.tensor([1,580,2304]),weight=torch.ones(3),supervised=torch.ones(3,dtype=torch.bool))
        return o,y
    def test_off_loss_gradient_adam_equals_r2(self):
        o,y=self.fixture(); z={k:v.detach().clone().requires_grad_(True) if v.is_floating_point() else v.clone() for k,v in o.items()}
        opt=torch.optim.AdamW([v for v in o.values() if v.requires_grad],lr=3e-4)
        other=torch.optim.AdamW([v for v in z.values() if v.requires_grad],lr=3e-4)
        a=root_loss(o,y);b=teacher_loss(z,y,.003,1.,0.)
        self.assertTrue(torch.equal(a,b));a.backward();b.backward()
        for k in ('gate','card','tile'):self.assertTrue(torch.equal(o[k].grad,z[k].grad))
        opt.step();other.step()
        for k in ('gate','card','tile'):self.assertTrue(torch.equal(o[k],z[k]))
    def test_root_filter(self):
        a=dict(teacher_root=np.array([1,1,1,1,0,1]),teacher_wait_kind=np.array([0,1,2,3,0,0]),
            expert_action_supervision_valid=np.array([1,1,1,1,1,0]),root_offsets=np.arange(7))
        np.testing.assert_array_equal(root_indices(a),[0])
    def test_advantage_masks_and_baseline(self):
        o,y=self.fixture();o.update(advantage_play=torch.zeros(3,4,576,requires_grad=True),advantage_wait=torch.zeros(3,2,requires_grad=True))
        target=advantage_targets(y);self.assertTrue(torch.equal(target[:,0],torch.zeros(3)))
        a=advantage_loss(o,y);y['root_scores'][2,2]=1000
        self.assertTrue(torch.equal(a,advantage_loss(o,y)));a.backward()
        self.assertEqual(float(o['advantage_play'].grad[2,0,0]),0.)
        y['root_valid'][0,0]=False
        with self.assertRaises(ValueError):advantage_targets(y)
    def test_aux_global_denominator_microbatch(self):
        o,y=self.fixture();o.update(advantage_play=torch.randn(3,4,576),advantage_wait=torch.randn(3,2))
        whole=advantage_loss(o,y);den=int(y['root_valid'].sum())
        parts=sum(advantage_loss({k:v[i:i+1] for k,v in o.items()},{k:v[i:i+1] for k,v in y.items()},den) for i in range(3))
        torch.testing.assert_close(parts,whole)
    def test_off_network_equals_r2_and_head_shapes(self):
        c=ModelConfig(width=24,heads=6,layers=1,ffn=48,tile_width=16,dropout=0.)
        assets=(torch.zeros(360,57),torch.zeros(576,12),torch.ones(360))
        ref=R2Policy(c,*assets).eval();new=SetPolicy(c,*assets).eval();new.load_state_dict(ref.state_dict())
        b=dict(ids=torch.ones(2,5,dtype=torch.long),types=torch.ones(2,5,dtype=torch.long),numeric=torch.zeros(2,5,24),valid=torch.ones(2,5,dtype=torch.bool),action_mask=torch.ones(2,2306,dtype=torch.bool))
        empty=torch.empty(0,dtype=torch.long);a=ref(b,empty);z=new(b,empty)
        for k in a:self.assertTrue(torch.equal(a[k],z[k]))
        h=AdvantagePolicy(c,*assets).eval();missing,extra=h.load_state_dict(ref.state_dict(),strict=False)
        self.assertEqual(len(missing),6);self.assertFalse(extra)
        out=h(b,empty);self.assertEqual(out['advantage_play'].shape,(2,4,576));self.assertEqual(out['advantage_wait'].shape,(2,2))

if __name__=='__main__':unittest.main()
