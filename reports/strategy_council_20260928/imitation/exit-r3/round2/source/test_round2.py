import unittest
import torch
from . import test_r3
from .student import teacher_targets,teacher_loss
from imitation.exit_r1.student import teacher_loss as r2_loss

class Round2Tests(test_r3.R3Tests):
    def test_softer_targets_and_off_loss_gradient(self):
        o,y=self.fixture();q=teacher_targets(y,.01)
        expected=torch.softmax((y['root_scores'].float()/.01).masked_fill(~y['root_valid'],-torch.inf),-1)
        torch.testing.assert_close(q,expected)
        torch.testing.assert_close(q.sum(-1),torch.ones(3));self.assertEqual(float(q[2,2]),0.)
        self.assertLess(float(q[0].max()),float(teacher_targets(y,.003)[0].max()))
        z={k:v.detach().clone().requires_grad_(True) if v.is_floating_point() else v.clone() for k,v in o.items()}
        a=teacher_loss(o,y,.01,1.,0.);b=r2_loss(z,y,.01,1.,0.)
        self.assertTrue(torch.equal(a,b));a.backward();b.backward()
        for k in ('gate','card','tile'):self.assertTrue(torch.equal(o[k].grad,z[k].grad))
if __name__=='__main__':unittest.main()
