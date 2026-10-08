"""Synthetic bounded-plan rejection tests, no pixels or jobs."""
from copy import deepcopy
import json
from validation_batch_v4 import batch_cells, batch_deadline

def main():
    good=dict(schema='clasher.v4.validation-batch.v1',cells=[dict(epoch=1,threshold=.5,body_threshold=.1)])
    assert batch_cells(good)==good['cells'];checks=1
    def reject(bad):
        nonlocal checks
        try:batch_cells(bad)
        except ValueError:checks+=1
        else:raise AssertionError('Invalid batch accepted')
    for key,value in [('epoch',True),('epoch',0),('epoch',25),('threshold',.55),('body_threshold',True),('body_threshold',1)]:
        bad=deepcopy(good);bad['cells'][0][key]=value;reject(bad)
    for rows in ([],good['cells']*2,good['cells']*10,['bad']):
        bad=deepcopy(good);bad['cells']=rows;reject(bad)
    bad=deepcopy(good);bad['cells'][0]['split']='heldout';reject(bad)
    bad=deepcopy(good);bad['schema']='heldout';reject(bad)
    assert batch_deadline(0,10000)==2700;checks+=1
    assert batch_deadline(8100,10000)==8380;checks+=1
    try:batch_deadline(8200,10000)
    except ValueError:checks+=1
    else:raise AssertionError('Late launch accepted')
    assert batch_deadline(0,10000,1000)==970;checks+=1
    for service in (200,float('nan'),float('inf')):
        try:batch_deadline(0,10000,service)
        except ValueError:checks+=1
        else:raise AssertionError('Expired/invalid service accepted')
    print(json.dumps(dict(checks=checks,passed=True,synthetic_only=True,heldout_payloads_opened=False)))

if __name__=='__main__':main()
