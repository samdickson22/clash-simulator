"""Focused standalone regressions, run only on an authorized fleet worker."""
import json
from pathlib import Path
import numpy as np
from labels_v4 import BodyLabels
from pixel_cache import PixelCache,encode,decompress


def main():
    root=Path(__file__).resolve().parents[5]
    labels=BodyLabels(root/'gamedata.json',Path(__file__).parents[1]/'body-catalog.json')
    # Mixed group: parent GoblinGang hint cannot label SpearGoblin as Goblin.
    cards=json.loads((root/'gamedata.json').read_text())['items']['spells']
    byname={r['name']:r['id'] for r in cards}
    ids=labels.candidates
    assert labels.identity(dict(card_id=byname['HogRider'],max_hp=1697))[0]=='HogRider'
    assert labels.identity(dict(card_id=byname['RoyalDelivery'],max_hp=547))[0]=='DeliveryRecruit'
    assert labels.identity(dict(card_id=byname['HogRider'],max_hp=999999))[0] is None
    assert labels.identity(dict(card_id=byname['HogRider'],max_hp=None))[0] is None
    o=dict(native_id=1,owner=0,card_id=byname['HogRider'],x=5000,y=5000,hp=1697,max_hp=1697,
           body_name='SpearGoblin',metadata_tick=900,visible_hint='visible',deploying=False)
    r=dict(nativeObjectId=1,owner=0,cardId=o['card_id'],x=5000,y=5000,hp=1697,maxHp=1697,
           visibilityState='visible',phaseRuntime=dict(deployRemainingMs=0),dataGlobalId=34000021)
    rows=[dict(tick=10,objects=[o]),dict(tick=11,objects=[o])]
    clean=labels.clean(rows,[dict(tick=11,objects=[r])])
    assert clean[0]['objects'][0]['body_name']=='HogRider'
    assert clean[0]['objects'][0]['visible_hint'] is None
    assert clean[1]['objects'][0]['visible_hint']=='visible'
    mismatch=labels.clean(rows,[dict(tick=11,objects=[dict(r,owner=1)])])
    assert mismatch[1]['objects'][0]['visible_hint'] is None
    repeated=labels.clean(rows,[dict(tick=11,objects=[r]),dict(tick=11,objects=[dict(r,visibilityState='hidden')])])
    assert repeated[1]['objects'][0]['visible_hint'] is None
    assert o['body_name']=='SpearGoblin' and o['metadata_tick']==900
    x=np.random.default_rng(42).integers(0,256,(16,7123),dtype=np.uint8)
    assert np.array_equal(decompress(encode(x),x.shape),x)
    x[:]=42;assert np.array_equal(decompress(encode(x),x.shape),x)
    try:PixelCache('/nonexistent',[dict(split='heldout')])
    except ValueError as e:assert 'Heldout' in str(e)
    else:raise AssertionError('Heldout admitted')
    from clasher.vision.l1_v4 import birth_maps
    birth=dict(identity='SpearGoblin',owner=0,x=3.,y=5.)
    source=dict(card='GoblinHut_Rework',side=0,x=3.,y=5.,time=0)
    assert birth_maps([birth],[source],100).sum()==0
    print(json.dumps(dict(pass_=True,checks=14,heldout_opened=False)),flush=True)


if __name__=='__main__':main()
