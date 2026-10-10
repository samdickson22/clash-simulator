"""Target semantics and off-equals-r1 optimizer regression for the X3 flag."""
import copy
import unittest
from unittest.mock import patch
import torch
from imitation.model.synthetic import model, batch
from imitation.model.network import ModelConfig
from . import student, train


def r1_targets(y, temperature, score_zscore=False):
    assert not score_zscore
    return torch.softmax((y['root_scores'].double()/temperature).masked_fill(
        ~y['root_valid'],-torch.inf),-1).float()


class TargetsR2Tests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        torch.manual_seed(1001)

    def test_off_equals_r1_targets_loss_gradients_and_update(self):
        b,y=batch(6)
        y.update(root_actions=torch.tensor([[0,2304,2401]]*6),
            root_scores=torch.tensor([[.003,0.,.001]]*6,dtype=torch.float64),
            root_valid=torch.ones(6,3,dtype=torch.bool),outcome=torch.zeros(6))
        m=model(ModelConfig(width=48,heads=6,layers=1,ffn=96,dropout=0))
        reference=copy.deepcopy(m)
        opts=[torch.optim.AdamW(x.parameters(),lr=3e-4) for x in (m,reference)]
        self.assertTrue(torch.equal(student.teacher_targets(y,.1),r1_targets(y,.1)))
        actual=train.step(m,opts[0],None,(b,y),1.,2,torch.device('cpu'),.1,4.,0.)
        with patch.object(student,'teacher_targets',r1_targets),patch.object(train,'teacher_targets',r1_targets):
            expected=train.step(reference,opts[1],None,(b,y),1.,2,torch.device('cpu'),.1,4.,0.)
        self.assertEqual(actual,expected)
        for k,v in m.state_dict().items():
            self.assertTrue(torch.equal(v,reference.state_dict()[k]),k)
        for p,q in zip(m.parameters(),reference.parameters()):
            if p.grad is not None:self.assertTrue(torch.equal(p.grad,q.grad))
            for k,v in opts[0].state[p].items():
                w=opts[1].state[q][k]
                self.assertTrue(torch.equal(v,w) if torch.is_tensor(v) else v==w)

    def test_zscore_valid_only_scale_shift_invariance_and_degenerate_roots(self):
        y=dict(root_scores=torch.tensor([[1.,2.,999.],[7.,7.,99.],[3.,99.,99.]],dtype=torch.float64),
            root_valid=torch.tensor([[True,True,False],[True,True,False],[True,False,False]]))
        q=student.teacher_targets(y,.5,True)
        shifted=dict(y,root_scores=y['root_scores']*3+100)
        self.assertTrue(torch.equal(q,student.teacher_targets(shifted,.5,True)))
        self.assertTrue(torch.equal(q[1],torch.tensor([.5,.5,0.])))
        self.assertTrue(torch.equal(q[2],torch.tensor([1.,0.,0.])))
        self.assertTrue(torch.allclose(q[0,:2],torch.softmax(torch.tensor([-2.,2.]),0)))

    def test_sharp_targets_split_exact_ties_and_zscore_global_denominators(self):
        y=dict(root_scores=torch.tensor([[.009,.009,0.]],dtype=torch.float64),
            root_valid=torch.ones(1,3,dtype=torch.bool))
        self.assertTrue(torch.equal(student.teacher_targets(y,1e-4)[0,:2],torch.tensor([.5,.5])))
        b,y=batch(6)
        y.update(root_actions=torch.tensor([[0,2304,2401]]*6),
            root_scores=torch.tensor([[.002,0.,.001],[.02,0.,.01]]*3,dtype=torch.float64),
            root_valid=torch.ones(6,3,dtype=torch.bool),outcome=torch.zeros(6))
        m=model(ModelConfig(width=48,heads=6,layers=1,ffn=96,dropout=0))
        o=m(b,torch.empty(0,dtype=torch.long))
        q=student.teacher_targets(y,.5,True)
        w=y['weight'].float()*y['supervised'].float()
        den=(float(w.sum()),float((w*(q*(y['root_actions']<2304)).sum(-1)).sum()))
        full=student.teacher_loss(o,y,.5,1.,score_zscore=True)
        partial=sum(student.teacher_loss({k:v[i:i+2] for k,v in o.items()},
            {k:v[i:i+2] for k,v in y.items()},.5,1.,denominators=den,score_zscore=True)
            for i in range(0,6,2))
        self.assertTrue(torch.allclose(full,partial,atol=1e-6))


if __name__=='__main__':unittest.main()
