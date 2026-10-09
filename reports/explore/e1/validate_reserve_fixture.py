"""Light standard-library check of the public crown-tower regression fixture."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from reserve import filter_candidates

class MaskedRows:
    def __init__(self, rows): self.rows=rows
    def __getitem__(self, mask): return [row for row,keep in zip(self.rows,mask) if keep]


def main():
    enemy=[0.]*32;enemy[0],enemy[1],enemy[3],enemy[4],enemy[9]=.25,18/32,1.,1.,1.
    building=[0.]*32;building[0],building[1],building[2],building[5],building[9]=.25,13/32,1.,1.,1.
    obs=SimpleNamespace(global_features=[0.]*5+[.6],hand_ids=[2]*4,entity_features=MaskedRows([enemy,building]),
        entity_mask=[True,True],entity_ids=MaskedRows([2,3]))
    packet=SimpleNamespace(observation=obs)
    catalog=dict(token_names=['pad','unknown','Knight'],cards={'Knight':dict(cost=3)},
        bodies={'3':dict(name='building_body:InfernoTower',tower=True)})
    candidates=[4+18*14,2304,2400,2401,2402]
    assert filter_candidates(candidates,packet,catalog,5,enabled=False) is candidates
    actual=filter_candidates(candidates,packet,catalog,5,enabled=True)
    assert actual==candidates[1:],actual
    print(json.dumps(dict(passed=True,checks=2,fixture='enemy still beyond bridge; own InfernoTower is not a crown tower',
        expected=candidates[1:],actual=actual,reserve_source_sha256=hashlib.sha256((Path(__file__).parent/'reserve.py').read_bytes()).hexdigest(),
        note='Standard-library masked-row fixture; complete13-test pytest suite awaits a free authorized host slot.')))

if __name__=='__main__':main()
