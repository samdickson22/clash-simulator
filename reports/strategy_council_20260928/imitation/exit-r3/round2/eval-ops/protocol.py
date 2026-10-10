"""Pure metadata rules shared by execution, qualification and reduction."""
ARMS=('R3c','R3d','R3e')
BASES={'descriptive':(4503602507370496,4503602517370496),'stage2':(4503602407370496,4503602417370496)}
def order(arms,index):
    assert arms and len(arms)==len(set(arms))
    k=index%len(arms);return arms[k:]+arms[:k]
def arm_list(lane,stage1=None):
    if lane=='descriptive':return ['K0','R3a']
    assert lane=='stage2' and stage1 and set(stage1)==set(ARMS)
    assert all(v['stage1_complete'] for v in stage1.values())
    return ['K0']+[a for a in ARMS if stage1[a]['survives']]
def decision(lane,upper):
    assert lane in BASES
    passed=upper<0
    return dict(paired_gate_passed=passed,survives=passed and lane=='stage2',never_adoptable=lane=='descriptive',adoption_eligible=passed and lane=='stage2',kill_reason=None if passed else 'upper paired95%CI(lossStudent-lossK0)>=0')
def stage(lane,smoke):return 'k0-'+lane+('-smoke' if smoke else '')
