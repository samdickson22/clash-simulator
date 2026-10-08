"""Small synthetic hardlink-view checks, executed only on a fleet host."""
import argparse
import json
from pathlib import Path
from stage_engineering_view_v4 import stage_view,FILES,sha


def main(root):
    root.mkdir();hub=root/'hub';hub.mkdir();members={};pins={};checks=0
    def check(v):
        nonlocal checks
        assert v;checks+=1
    def rejects(fn):
        nonlocal checks
        try:fn()
        except (ValueError,FileExistsError):checks+=1
        else:raise AssertionError('Invalid view accepted')
    for seed,split in ((1,'train'),(2,'validation'),(3,'heldout')):
        ep='v4-phase-a-'+str(seed);folder=hub/ep;folder.mkdir();members[seed]=dict(split=split,decks=['fixture'])
        receipt=dict(episode=ep,seed=seed,split=split,decks=['fixture'],frames=1,files={})
        # Heldout has no payload files: refusal must happen before payload reads.
        if split!='heldout':
            for name in FILES[1:]:
                (folder/name).write_bytes((ep+name).encode());receipt['files'][name]=sha(folder/name)
        (folder/'receipt.json').write_text(json.dumps(receipt));pins[ep]=sha(folder/'receipt.json')
    expected={e:d for e,d in pins.items() if e!='v4-phase-a-3'}
    result=stage_view(hub,root/'valid',expected,members)
    check(result['matches']==2 and result['frames']==2)
    check(result['complete_population'] is False and result['engineering_only'] is True)
    check(result['heldout_payloads_opened'] is False and result['receipt_sha256']==expected)
    for ep in expected:
        check(all((hub/ep/n).stat().st_ino==(root/'valid'/ep/n).stat().st_ino for n in FILES))
    rejects(lambda:stage_view(hub,root/'valid',expected,members))
    rejects(lambda:stage_view(hub,root/'heldout',{'v4-phase-a-3':pins['v4-phase-a-3']},members))
    rejects(lambda:stage_view(hub,root/'empty',{},members))
    rejects(lambda:stage_view(hub,root/'escape',{'../escape':'a'*64},members))
    rejects(lambda:stage_view(hub,root/'receipt-changed',{'v4-phase-a-1':'a'*64},members))
    members[1]['split']='heldout'
    rejects(lambda:stage_view(hub,root/'membership-changed',expected,members));members[1]['split']='train'
    path=hub/'v4-phase-a-1/video.mp4';saved=path.read_bytes();path.write_bytes(b'changed')
    rejects(lambda:stage_view(hub,root/'payload-changed',expected,members));path.write_bytes(saved)
    print(json.dumps(dict(checks=checks,passed=True,synthetic_only=True,heldout_payloads_opened=False)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    main(p.parse_args().output)
