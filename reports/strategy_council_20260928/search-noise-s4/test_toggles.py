import unittest
import numpy as np
from cells import configuration
from hybrid import Hybrid
class Fake:
    elixir=8.
    def __init__(self,value):self.value=value
    def sample(self,rng):return dict(elixir=self.value+rng.random(),hand=[self.value]*4,cycle=[self.value]*4,refill=self.value)
class Tests(unittest.TestCase):
    def test_endpoints_and_rng(self):
        for a,b in ((False,False),(True,True)):
            h=Hybrid(Fake(1),Fake(2),a,b,3);x=np.random.default_rng(4);y=np.random.default_rng(4)
            self.assertEqual(h.sample(x),(h.exact if a else h.legacy).sample(y));self.assertEqual(x.random(),y.random())
        self.assertEqual(configuration()['tracker'],'legacy');self.assertEqual(configuration(True,True)['tracker'],'exact')
    def test_component_isolation(self):
        for a,b in ((True,False),(False,True)):
            h=Hybrid(Fake(1),Fake(2),a,b,3);rng=np.random.default_rng(4);baseline=h.legacy.sample(np.random.default_rng(4));sample=h.sample(rng)
            if a:
                self.assertEqual(sample['elixir'],8.)
                for key in ('hand','cycle','refill'):self.assertEqual(sample[key],baseline[key])
            else:
                self.assertEqual(sample['elixir'],baseline['elixir'])
                for key in ('hand','cycle','refill'):self.assertEqual(sample[key],h.exact.sample(np.random.default_rng(3))[key])
if __name__=='__main__':unittest.main()
