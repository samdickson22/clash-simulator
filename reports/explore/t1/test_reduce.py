import numpy as np
from reduce import stratified_bootstrap,interval

def test_cell_stratification_keeps_population_weights_and_paired_arms():
 # Fixed outcomes per stratum; resampling must not alter the stratum weights.
 m=np.array([[0,1]]*4+[[1,0]]*2,float)
 b=stratified_bootstrap(m,[0]*4+[1]*2,100,np.random.default_rng(5))
 np.testing.assert_array_equal(b[:,0],np.full(100,1/3))
 np.testing.assert_array_equal(b.sum(1),np.ones(100))
 assert interval(b[:,0],.975)==[1/3,1/3]


def test_integer_exact_inclusive_boundary_and_bonferroni():
 from fractions import Fraction
 from reduce import exact_interval,pack_exact,upper,BONFERRONI
 assert BONFERRONI==Fraction(59,60)
 for count,n,threshold in [(60,600,10),(120,2400,5),(-240,2400,-10),(960,2400,40)]:
  values=np.full(10000,count,dtype=np.int64)
  bounds=exact_interval(values,BONFERRONI,n)
  record={'exact':{'ci':pack_exact(bounds)}}
  assert upper(record,'ci')==threshold and upper(record,'ci')<=threshold
 # Rational interpolation falls exactly between two integer count differences.
 assert exact_interval(np.array([0,2]),Fraction(1,2),100)==[Fraction(1,2),Fraction(3,2)]
